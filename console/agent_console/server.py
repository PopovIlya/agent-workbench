"""FastAPI app for the Agents tab (read-only). Binds 127.0.0.1 only.

Main goal: serve the static UI and JSON endpoints over the local index.
Does not: write anything except two tiny local state changes (mark a flag "checked"), and it has
NO Data-tab endpoints yet (Step 3). It never returns prompt/tool text unless asked, and then redacted.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import compare, config, ctq_api, gold, queries
from .autoscore import AutoScorer
from .pricing import Pricing
from .store import Store

STATIC = Path(__file__).resolve().parents[1] / "static"
INGEST_EVERY_S = 30
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class ShowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part: str = Field(max_length=200, pattern=r"^(prompt|final|description|tool:[A-Za-z0-9_#:./~-]{1,160})$")


class CheckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(max_length=200)
    flag: str = Field(max_length=60)


class VerdictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str = Field(max_length=60, pattern=gold.TICKET_RE)
    verdict: Literal["accepted", "accepted_after_rework", "rejected"]
    note: str = Field(default="", max_length=gold.NOTE_MAX)
    roles: list[str] = Field(default_factory=list, max_length=30)


class DefectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str = Field(max_length=60, pattern=gold.TICKET_RE)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    roles: list[str] = Field(min_length=1, max_length=30)
    note: str = Field(default="", max_length=gold.NOTE_MAX)


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(max_length=200)
    flag: Literal["deception"]
    decision: Literal["confirm", "dismiss"]


def _roles_ok(roles: list[str]) -> list[str]:
    import re
    bad = [r for r in roles if not re.fullmatch(gold.ROLE_RE, r)]
    if bad:
        raise HTTPException(422, "Invalid request.")
    return list(dict.fromkeys(roles))


def create_app(store: Store | None = None, pricing: Pricing | None = None, port: int | None = None, auto_ingest: bool = False) -> FastAPI:
    port = port or config.PORT
    st = store or Store()
    pr = pricing or Pricing.load(config.pricing_path())
    app = FastAPI(title="Agent console", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.pricing = st, pr
    ctq_api.register(app, st, pr)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # The default 422 body echoes the input; a password field must never come back in a response.
        return JSONResponse({"detail": "Invalid request."}, status_code=422)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", "testserver"}

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get("host", "") not in allowed_hosts:  # DNS-rebinding guard
            return JSONResponse({"detail": "Not found."}, status_code=404)
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}", "http://testserver"}:
                return JSONResponse({"detail": "Forbidden."}, status_code=403)
            if not request.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse({"detail": "Unsupported."}, status_code=415)
        resp: Response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            resp.headers[k] = v
        return resp

    if auto_ingest:
        AutoScorer(st).attach()   # scores new or changed runs after each rescan, at most once a minute

        def loop() -> None:
            while True:
                st.rescan(min_interval=0)  # new session files and appended lines, every 30 s
                time.sleep(INGEST_EVERY_S)
        threading.Thread(target=loop, daemon=True, name="rescan-loop").start()

    @app.get("/health")
    def health():
        return {"ok": True, "app": "agent-console"}

    @app.get("/api/status")
    def status():
        return {**queries.freshness(st), "pricing_empty": pr.empty}

    @app.post("/api/rescan")
    def rescan(wait: bool = False):
        """Called by the page on every load. Starts a background rescan (at most one at a time, not more often than
        every 5 s) so new or changed session files show up without waiting for the 30 s loop."""
        started = st.rescan(wait=wait, min_interval=5.0)
        return {"started": started, **queries.freshness(st)}

    @app.get("/api/runs/{run_id:path}")
    def run(run_id: str):
        d = queries.run_detail(st, pr, run_id)
        if d is None:
            raise HTTPException(404, "Not found.")
        return d

    @app.post("/api/show/{run_id:path}")
    def show(run_id: str, body: ShowBody):
        d = queries.show_text(st, run_id, body.part)
        if d is None:
            raise HTTPException(404, "Not found.")
        return d

    @app.post("/api/flags/check")
    def flag_check(body: CheckBody):
        if not queries.check_flag(st, body.run_id, body.flag):
            raise HTTPException(404, "Not found.")
        return {"ok": True}

    @app.post("/api/verdict")
    def verdict(body: VerdictBody):
        """Your verdict on a ticket. Appended to ~/.agent-console/verdicts.jsonl; the latest line per ticket wins."""
        _ticket_known(body.ticket)
        rec = gold.append("verdicts.jsonl", {"ticket": body.ticket, "verdict": body.verdict, "note": body.note.strip(), "roles": _roles_ok(body.roles)})
        st.flag_epoch = getattr(st, "flag_epoch", 0) + 1
        return {"ok": True, "verdict": rec}

    @app.post("/api/defect")
    def defect(body: DefectBody):
        """A defect found after "done". Appended to ~/.agent-console/defects.jsonl; it feeds the gate-escape checks."""
        _ticket_known(body.ticket)
        try:
            from datetime import date as _date
            _date.fromisoformat(body.date)
        except ValueError:
            raise HTTPException(422, "Invalid request.") from None
        rec = gold.append("defects.jsonl", {"ticket": body.ticket, "date": body.date, "roles": _roles_ok(body.roles), "note": body.note.strip()})
        st.flag_epoch = getattr(st, "flag_epoch", 0) + 1
        return {"ok": True, "defect": rec}

    @app.post("/api/flags/decide")
    def flag_decide(body: DecideBody):
        """Confirm or dismiss a suspected deception. A confirmed one is a hard limit (S = 0); either way it leaves "Needs a person"."""
        if not queries.check_flag(st, body.run_id, body.flag):
            raise HTTPException(404, "Not found.")
        rec = gold.append("flag_decisions.jsonl", {"run_id": body.run_id, "flag": body.flag, "decision": body.decision})
        st.flag_epoch = getattr(st, "flag_epoch", 0) + 1
        return {"ok": True, "decision": rec}

    def _ticket_known(key: str) -> None:
        db = st.reader()
        try:
            if not db.execute("SELECT 1 FROM runs WHERE ticket_eff=? OR ticket=? LIMIT 1", (key, key)).fetchone():
                raise HTTPException(404, "Not found.")
        finally:
            db.close()

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    @app.get("/compare")
    def compare_page(a: str | None = None, b: str | None = None):
        """Two tickets side by side, server-rendered (CON-027). Read-only; unknown key 404, missing key 422."""
        if not a or not b:
            return HTMLResponse(compare.render_error("Both ticket keys are needed: /compare?a=<KEY>&b=<KEY>."), status_code=422)
        try:
            res = compare.compare(st, pr, a, b)
        except compare.UnknownKey as e:
            return HTMLResponse(compare.render_error("Unknown ticket key: " + ", ".join(e.keys)), status_code=404)
        return HTMLResponse(compare.render_html(res))

    @app.get("/static/{name}")
    def static(name: str):
        f = (STATIC / name).resolve()
        if STATIC.resolve() not in f.parents or not f.is_file():
            raise HTTPException(404, "Not found.")
        return FileResponse(f)

    return app


def main() -> None:
    port = config.PORT
    host = config.HOST
    if host not in ("127.0.0.1",):
        sys.exit("Refusing to bind anything but 127.0.0.1.")
    pid_file = config.home() / "console.pid"
    pid_file.write_text(str(os.getpid()))

    def cleanup(*_: object) -> None:
        try:
            if pid_file.read_text().strip() == str(os.getpid()):
                pid_file.unlink()
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    app = create_app(port=port, auto_ingest=True)
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
