"""HTTP side of the cost / time / quality pages: /api/ctq/*. Read-only. Every endpoint takes the same period, scope and filters."""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from . import autoscore, config, ctq, ctq_pages as pages
from .pricing import Pricing
from .queries import SCOPES, SCORE_BAR
from .store import Store


def register(app: FastAPI, st: Store, pr: Pricing) -> None:
    def ctx(frm: str | None, to: str | None, scope: str, proj: str, q: str) -> pages.Ctx:
        if scope not in SCOPES:
            raise HTTPException(422, "Invalid scope.")
        d = ctq.get_data(st, pr)
        try:
            per = ctq.resolve_period(d, frm or None, to or None)
        except ValueError:
            raise HTTPException(422, "Invalid period.") from None
        return pages.Ctx(st, pr, d, per, scope, proj.strip()[:60], q.strip()[:60])

    Frm, To = Query(None, alias="from"), Query(None, alias="to")

    def judge_info() -> dict[str, Any]:
        """The judge for the S tooltip: is it on, and how well does it agree with the person (kappa). Read only: nothing here can switch it on."""
        from agent_scoring import judge as J
        cfg = J.load_config(config.home())
        try:
            cal = json.loads((config.home() / "calibration.json").read_text())
        except (OSError, ValueError):
            cal = {}
        return {"on": J.is_on(cfg), "n": cal.get("n"), "kappa": cal.get("kappa"), "weight_active": J.is_calibrated(cal, cfg), "needs_n": J.CALIBRATION_MIN_N, "needs_kappa": J.CALIBRATION_MIN_KAPPA}

    @app.get("/api/ctq/meta")
    def meta() -> dict[str, Any]:
        autoscore._ensure_scoring()
        return {"judge": judge_info(), "coverage_min": ctq.COVERAGE_MIN, "bar": SCORE_BAR, "stages": [{"name": n, "key": g, "roles": rs} for n, g, rs in ctq.STAGES], "role_order": ctq.ROLE_ORDER, "not_pipeline": list(ctq.NOT_PIPELINE),
                "weights": ctq.WEIGHTS, "tz": config.tz_name(), "min_scored": config.MIN_SCORED_FOR_VERDICT, "context_red_tokens": config.CONTEXT_RED_TOKENS,
                "gap_cut_s": config.GAP_CUT_S, "test_timeout_s": config.TEST_TIMEOUT_S, "parked_after_s": config.PARKED_AFTER_S, "blocked_after_s": config.BLOCKED_AFTER_S,
                "child_share": config.CHILD_SHARE, "shared_session_roles": config.SHARED_SESSION_ROLES, "nokey": ctq.NOKEY}

    @app.get("/api/ctq/filters")
    def filters(frm: str | None = Frm, to: str | None = To, scope: str = "project", proj: str = "") -> dict[str, Any]:
        return pages.filters(ctx(frm, to, scope, "", ""), proj)

    @app.get("/api/ctq/overview")
    def overview(frm: str | None = Frm, to: str | None = To, scope: str = "project", proj: str = "", q: str = "") -> dict[str, Any]:
        return pages.overview(ctx(frm, to, scope, proj, q))

    @app.get("/api/ctq/tickets")
    def tickets(frm: str | None = Frm, to: str | None = To, scope: str = "project", proj: str = "", q: str = "", sort: str = "cost", desc: bool = True,
                limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return pages.tickets(ctx(frm, to, scope, proj, q), sort, desc, limit, max(0, offset))

    @app.get("/api/ctq/tickets/{key:path}")
    def ticket(key: str, frm: str | None = Frm, to: str | None = To, scope: str = "project") -> dict[str, Any]:
        return pages.ticket_detail(ctx(frm, to, scope, "", ""), key)

    @app.get("/api/ctq/roles")
    def roles(frm: str | None = Frm, to: str | None = To, scope: str = "project", proj: str = "", q: str = "", matrix_limit: int = 30) -> dict[str, Any]:
        return pages.roles(ctx(frm, to, scope, proj, q), max(0, min(matrix_limit, 2000)))

    @app.get("/api/ctq/roles/{role}")
    def role(role: str, frm: str | None = Frm, to: str | None = To, scope: str = "project", proj: str = "", q: str = "", first_only: bool = False, ticket: str = "") -> dict[str, Any]:
        return pages.role_detail(ctx(frm, to, scope, proj, q), role, first_only, ticket.strip()[:60])

    @app.get("/api/ctq/sessions")
    def sessions(frm: str | None = Frm, to: str | None = To, scope: str = "project", proj: str = "", q: str = "", sort: str = "cost", desc: bool = True,
                 limit: int = 200) -> dict[str, Any]:
        return pages.sessions(ctx(frm, to, scope, proj, q), sort, desc, limit)
