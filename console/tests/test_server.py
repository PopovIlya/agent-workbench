"""HTTP surface: loopback guards, no write endpoints beyond two local state changes, redacted text on demand."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_console import config, server
from agent_console.pricing import Pricing
from agent_console.store import Store
from conftest import PROJECT, flat_routes, add_sub, assistant, tool_use, usage, user_prompt, write_jsonl


@pytest.fixture
def client(env):
    secret_prompt = "please use pass" + "word=Tr0ub4dor&3xyz and PROJ-60069"
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt(secret_prompt, t=1), assistant("m1", t=2, blocks=[tool_use("tA", "Agent", subagent_type="builder", description="PROJ-60069 build", prompt="p")])])
    add_sub(env.root, "S1", "a1", "builder", [user_prompt(secret_prompt, t=3, agent="a1", session="S1"),
                                              assistant("a1m", t=4, agent="a1", u=usage(10, 5), blocks=[tool_use("e1", "Edit", file_path="/work/worktrees/w/docs/a.md", old_string="a", new_string="b"),
                                                                                                        {"type": "text", "text": "done, token is ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"}])], "tA")
    store = Store()
    store.ingest()
    return TestClient(server.create_app(store=store, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")


def test_health_and_security_headers(client):
    r = client.get("/health")
    assert r.json() == {"ok": True, "app": "agent-console"}
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store" and "default-src 'self'" in r.headers["content-security-policy"]


def test_foreign_host_header_is_refused(client):
    assert client.get("/health", headers={"host": "evil.example.com"}).status_code == 404
    assert client.get("/health", headers={"host": "127.0.0.1:9999"}).status_code == 404


def test_post_requires_json_and_same_origin(client):
    assert client.post("/api/flags/check", content=b"x=1", headers={"content-type": "text/plain"}).status_code == 415
    assert client.post("/api/flags/check", json={"run_id": "a", "flag": "b"}, headers={"origin": "https://evil.example.com"}).status_code == 403
    assert client.post("/api/flags/check", json={"run_id": "S1:a1", "flag": "nope"}).status_code == 404


def test_extra_fields_rejected(client):
    assert client.post("/api/show/S1:a1", json={"part": "prompt", "extra": 1}).status_code == 422
    assert client.post("/api/show/S1:a1", json={"part": "rm -rf"}).status_code == 422


def test_no_write_endpoint_beyond_local_state_changes(client):
    posts = {r.path for r in flat_routes(client.app) if "POST" in r.methods}
    agents_posts = {"/api/show/{run_id:path}", "/api/flags/check", "/api/rescan",   # rescan only READS the logs
                    "/api/verdict", "/api/defect", "/api/flags/decide"}              # the person's verdicts, defect reports and deception decisions (~/.agent-console only)
    assert posts - agents_posts == set()   # nothing else writes
    assert not any(m in r.methods for r in flat_routes(client.app) for m in ("PUT", "PATCH", "DELETE"))


def test_show_text_is_redacted_and_on_request_only(client):
    detail = client.get("/api/runs/S1:a1").json()
    assert "Tr0ub4dor" not in json.dumps(detail) and "ghp_" not in json.dumps(detail)  # never in the metadata view
    assert set(detail["text_parts"]) == {"prompt", "final", "description"}
    for part in ("prompt", "final"):
        t = client.post("/api/show/S1:a1", json={"part": part}).json()
        assert t["redactions"] >= 1 and "[REDACTED:" in t["text"]
        assert "Tr0ub4dor" not in t["text"] and "a1B2c3D4e5F6" not in t["text"]
    assert "PROJ-60069" in client.post("/api/show/S1:a1", json={"part": "description"}).json()["text"]
    assert client.post("/api/show/NOPE", json={"part": "prompt"}).status_code == 404


def test_run_detail_files_touched_and_ticket(client):
    d = client.get("/api/runs/S1:a1").json()
    assert d["files_edited"] == [{"path": "docs/a.md", "tool": "Edit", "from_bash_command": False, "count": 1}]
    assert d["ticket"] == "PROJ-60069" and d["cost"]["cost_label"] == "cost unknown" and d["role"] == "builder"


def test_ctq_overview_tickets_roles_endpoints(client):
    o = client.get("/api/ctq/overview").json()
    assert o["kpis"]["runs"] == 2 and o["kpis"]["n_S"] == 0 and o["period"]["runs"] == 2
    assert [t["ticket"] for t in client.get("/api/ctq/tickets").json()["rows"]][0] == "PROJ-60069"
    assert client.get("/api/ctq/tickets/PROJ-60069").json()["runs"]
    names = {r["role"] for r in client.get("/api/ctq/roles").json()["rows"]}
    assert {"builder", "main"} <= names
    assert client.get("/api/ctq/roles/builder").json()["row"]["runs"] == 1
    assert client.get("/api/ctq/overview?scope=bad").status_code == 422


def test_old_page_endpoints_are_gone(client):
    for path in ("/api/overview", "/api/system", "/api/runs", "/api/roles", "/api/roles/builder", "/api/tickets", "/api/tickets/PROJ-60069", "/api/tokens", "/api/flags", "/api/scores", "/api/sources"):
        assert client.get(path).status_code == 404, path


def test_static_traversal_is_refused(client):
    assert client.get("/static/..%2fagent_console%2fserver.py").status_code in (404, 422)
    assert client.get("/static/nope.js").status_code == 404
    assert client.get("/static/app.js").status_code == 200 and client.get("/").status_code == 200


def test_ui_never_uses_innerhtml():
    src = "".join(p.read_text() for p in Path(server.STATIC).glob("*.js"))
    assert "innerHTML" not in src and "outerHTML" not in src and "document.write" not in src and "eval(" not in src
    assert "localStorage" not in src and "sessionStorage" not in src


def test_main_refuses_non_loopback_bind(monkeypatch):
    monkeypatch.setattr(config, "HOST", "0.0.0.0")
    with pytest.raises(SystemExit):
        server.main()


def test_the_pages_read_the_latest_revision_of_a_score(env, client):
    assert client.get("/api/ctq/roles/builder").json()["row"]["S"] is None
    lines = [{"task_id": "S1:a1", "ts": "2026-10-10T10:00:00Z", "rev": 1, "role": "builder", "S": 0.9, "criteria": {"follows": {"c": 1.0, "w": 0.1}}, "scored": True},
             {"task_id": "S1:a1", "ts": "2026-10-11T10:00:00Z", "rev": 2, "role": "builder", "S": 0.5, "criteria": {"follows": {"c": 0.0, "w": 0.1}}, "scored": True}]   # a rescore wins
    env.home.mkdir(exist_ok=True)
    (env.home / "scores.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
    row = client.get("/api/ctq/roles/builder").json()["row"]
    assert row["S"] == pytest.approx(0.5) and row["n_S"] == 1 and row["pass"]["follows"] == [0, 1]
