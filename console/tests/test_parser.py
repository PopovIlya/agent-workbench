"""Parser: every field the console relies on (DESIGN.md section 1.2)."""

import json

from agent_console import parser
from conftest import PROJECT, api_error, assistant, tool_result, tool_use, usage, user_prompt, write_jsonl


def parse(tmp_path, records):
    p = tmp_path / PROJECT / "S1.jsonl"
    write_jsonl(p, records)
    return parser.parse_file(p)


def kinds(events, k):
    return [e for e in events if e.kind == k]


def test_message_fields_model_usage_and_cache_split(tmp_path):
    ev, _ = parse(tmp_path, [assistant("m1", model="claude-sonnet-5-5", requested="us.anthropic.claude-sonnet-5-5",
                                       u=usage(3, 4, 5, 7, w5=2, w1=5))])
    m = kinds(ev, "message")[0].data
    assert (m["model"], m["requested_model"]) == ("claude-sonnet-5-5", "us.anthropic.claude-sonnet-5-5")
    assert (m["input"], m["output"], m["cache_read"], m["cache_w5m"], m["cache_w1h"]) == (3, 4, 5, 2, 5)


def test_cache_write_without_split_counts_as_5m(tmp_path):
    u = {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 9}
    ev, _ = parse(tmp_path, [assistant("m1", u=u)])
    assert kinds(ev, "message")[0].data["cache_w5m"] == 9


def test_subagent_spawn_fields_and_ticket_hint(tmp_path):
    blk = [tool_use("t1", "Agent", subagent_type="builder", description="Build PROJ-60015 thing", prompt="x", model="sonnet", run_in_background=True)]
    ev, _ = parse(tmp_path, [assistant("m1", blocks=blk)])
    t = kinds(ev, "tool_use")[0].data
    assert (t["name"], t["subagent_type"], t["spawn_model"], t["background"], t["ticket"]) == ("Agent", "builder", "sonnet", 1, "PROJ-60015")


def test_ticket_from_prompt_when_description_has_none(tmp_path):
    blk = [tool_use("t1", "Agent", subagent_type="x", description="none", prompt="please do TEAM-3000 now")]
    ev, _ = parse(tmp_path, [assistant("m1", blocks=blk)])
    assert kinds(ev, "tool_use")[0].data["ticket"] == "TEAM-3000"


def test_edit_write_read_paths_and_bash_write_paths(tmp_path):
    blk = [tool_use("a", "Edit", file_path="/r/a.py", old_string="x", new_string="y"), tool_use("b", "Write", file_path="/r/b.md", content="c"),
           tool_use("c", "Read", file_path="/r/c.md"), tool_use("d", "Bash", command="echo hi > /r/out.txt && sed -i '' 's/a/b/' /r/s.txt; ls 2>/dev/null"),
           tool_use("e", "Bash", command="cat x | tee -a /r/t.log")]
    ev, _ = parse(tmp_path, [assistant("m1", blocks=blk)])
    got = {(e.data["name"], e.data["path"]) for e in kinds(ev, "tool_use")}
    assert {("Edit", "/r/a.py"), ("Write", "/r/b.md"), ("Read", "/r/c.md"), ("Bash-write", "/r/out.txt"),
            ("Bash-write", "/r/s.txt"), ("Bash-write", "/r/t.log")} <= got
    assert not any(p == "/dev/null" for _, p in got)


def test_tool_result_error_flag(tmp_path):
    ev, _ = parse(tmp_path, [tool_result("t1", err=True), tool_result("t2", err=False)])
    assert [(e.data["tool_use_id"], e.data["is_error"]) for e in kinds(ev, "tool_result")] == [("t1", 1), ("t2", 0)]


def test_api_errors_are_categories_never_text(tmp_path):
    recs = [api_error(1, status=403), api_error(2, status=None, message="Failed to resolve AWS credentials: Token is expired. SSO"),
            api_error(3, status=None, message="Request timed out."),
            assistant("e1", model="<synthetic>", isApiErrorMessage=True, error="authentication_failed", apiErrorStatus=403)]
    ev, _ = parse(tmp_path, recs)
    cats = [e.data["category"] for e in kinds(ev, "api_error")]
    assert cats == ["aws_403", "credentials_expired", "network", "aws_403"]
    assert "arn:aws" not in json.dumps([e.data for e in ev])
    assert not kinds(ev, "message")  # the synthetic stub is not a model message


def test_reject_marker_and_text_flags(tmp_path):
    ev, _ = parse(tmp_path, [assistant("m1", blocks=[{"type": "text", "text": "REJECT: missing test"}])])
    d = kinds(ev, "message")[0].data
    assert d["says_reject"] == 1 and d["has_text"] == 1


def test_ticket_in_user_prompt_only_the_key_is_kept(tmp_path):
    text = "start PROJ-60033 with the secret pass" + "word=hunter22"
    ev, _ = parse(tmp_path, [user_prompt(text)])
    d = kinds(ev, "user_prompt")[0].data
    assert d == {"ticket": "PROJ-60033", "lead": None, "origin": None, "prev_ts": None, "chars": len(text)}   # a length, never the text


def test_cost_state(tmp_path):
    ev, _ = parse(tmp_path, [{"type": "cost-state", "sessionId": "S1", "totalCostUSD": 1.5, "modelUsage": {}}])
    assert kinds(ev, "cost_state")[0].data["total_cost_usd"] == 1.5


def test_incremental_offset_and_partial_line(tmp_path):
    p = tmp_path / PROJECT / "S1.jsonl"
    write_jsonl(p, [assistant("m1"), assistant("m2")])
    ev1, off1 = parser.parse_file(p)
    assert len(kinds(ev1, "message")) == 2 and off1 == p.stat().st_size
    with open(p, "a") as fh:
        fh.write(json.dumps(assistant("m3")) + "\n" + '{"type":"assistant","mess')  # a record still being written
    ev2, off2 = parser.parse_file(p, off1)
    assert [e.data["msg_id"] for e in kinds(ev2, "message")] == ["m3"]
    with open(p, "a") as fh:
        fh.write('age":{"id":"m4","usage":{}}}\n')
    ev3, _ = parser.parse_file(p, off2)
    assert [e.data["msg_id"] for e in kinds(ev3, "message")] == ["m4"]  # the completed line is parsed once, not lost


def test_classify_paths(tmp_path):
    main = parser.classify(tmp_path / PROJECT / "abc.jsonl")
    sub = parser.classify(tmp_path / PROJECT / "abc" / "subagents" / "agent-xyz.jsonl")
    assert (main.kind, main.run_id) == ("main", "abc") and (sub.kind, sub.run_id) == ("sub", "abc:xyz")
    assert parser.classify(tmp_path / PROJECT / "abc" / "subagents" / "agent-xyz.meta.json") is None


def test_read_record_by_offset(tmp_path):
    ev, _ = parse(tmp_path, [assistant("m1"), assistant("m2")])
    off = kinds(ev, "message")[1].off
    rec = parser.read_record(tmp_path / PROJECT / "S1.jsonl", off)
    assert rec["message"]["id"] == "m2"


def test_leading_key_in_prompt_and_spawn_description(tmp_path):
    blk = [tool_use("t1", "Agent", subagent_type="builder", description="[PROJ-60015] build it", prompt="x"),
           tool_use("t2", "Agent", subagent_type="builder", description="build PROJ-60015 it", prompt="x")]
    ev, _ = parse(tmp_path, [user_prompt("PROJ-6000037 go"), user_prompt("[TEAM-3000] start"), user_prompt("see PROJ-3006"), assistant("m1", blocks=blk)])
    leads = [e.data["lead"] for e in kinds(ev, "user_prompt")]
    assert leads == [None, "TEAM-3000", None]  # 7 digits is not a key; "see PROJ-3006" is not leading
    t = {e.data["id"]: e.data for e in kinds(ev, "tool_use")}
    assert (t["t1"]["ticket"], t["t1"]["ticket_src"]) == ("PROJ-60015", "lead") and (t["t2"]["ticket"], t["t2"]["ticket_src"]) == ("PROJ-60015", "text")


def test_git_commands_give_a_key_but_not_their_text(tmp_path):
    blk = [tool_use("g1", "Bash", command="cd /r && git checkout -b PROJ-60036-fix-thing && git commit -m 'PROJ-60036: x'"),
           tool_use("g2", "Bash", command="echo PROJ-60096 not a git command"), tool_use("g3", "Bash", command="git status")]
    ev, _ = parse(tmp_path, [assistant("m1", blocks=blk)])
    t = {e.data["id"]: e.data for e in kinds(ev, "tool_use")}
    assert (t["g1"]["ticket"], t["g1"]["ticket_src"]) == ("PROJ-60036", "git")
    assert t["g2"]["ticket"] is None and t["g3"]["ticket"] is None
    assert "checkout" not in json.dumps([e.data for e in ev])


def test_dev_tcp_redirect_is_a_port_probe_not_a_file_write(tmp_path):
    ev, _ = parse(tmp_path, [assistant("m1", blocks=[tool_use("a", "Bash", command="timeout 3 bash -c 'echo > /dev/tcp/db.example.test/27017' && echo up > /r/out.txt")])])
    paths = [e.data["path"] for e in kinds(ev, "tool_use") if e.data["name"] == "Bash-write"]
    assert paths == ["/r/out.txt"]
