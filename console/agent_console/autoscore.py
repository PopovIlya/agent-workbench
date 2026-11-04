"""Score the role tasks by itself after a rescan, so the Agents tab has S, flags and the trend without anyone running the CLI.

After each finished rescan the scorer looks at a cheap fingerprint of the indexed sub-agent runs. If it differs from the one
that was last scored (a new or changed run), it runs `agent-score` incrementally (`agent_scoring.agent_score.run_scoring`: runs already
scored and unchanged are skipped) into the score log, at most once per `min_interval` seconds. The result is shown in the page
header next to the last rescan (`last_score_ok`).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import config

MIN_INTERVAL_S = 60.0


def _ensure_scoring() -> None:
    """agent_scoring sits next to agent_console in console/."""
    here = Path(__file__).resolve().parents[1]
    if (here / "agent_scoring").is_dir() and str(here) not in sys.path:
        sys.path.insert(0, str(here))


SCORE_WINDOW_DAYS = 42      # scorer v2 keeps the last six weeks scored, so the history is comparable


def default_run(store: Any) -> dict[str, Any]:
    """Score with scorer v2. The judge is only read here (its stored answers and its calibration); this code never switches it on or calls it."""
    _ensure_scoring()
    from datetime import timedelta
    from agent_scoring import agent_score_v2, judge
    home = config.home()
    cfg = judge.load_config(home)
    cal_file = config.home() / "calibration.json"
    try:
        cal = json.loads(cal_file.read_text())
    except (OSError, ValueError):
        cal = {}
    since = (datetime.now(timezone.utc) - timedelta(days=SCORE_WINDOW_DAYS)).strftime("%Y-%m-%d")
    return agent_score_v2.run_scoring_v2(config.repo_root(), scores_path=config.scores_path(), since=since, roles_ref=config.roles_ref(), store=store, state=home,
                                         judge_results=judge.judge_results(home), judge_calibrated=judge.is_calibrated(cal, cfg))


class AutoScorer:
    def __init__(self, store: Any, run: Callable[[Any], dict[str, Any]] | None = None, min_interval: float = MIN_INTERVAL_S,
                 clock: Callable[[], float] = time.time):
        self.store, self.run, self.min_interval, self.clock = store, run or default_run, min_interval, clock
        self.fingerprint: tuple | None = None   # of the state that was last scored
        self.last_started = float("-inf")
        self._busy = threading.Lock()
        store.progress.setdefault("last_score_ok", None)

    def attach(self) -> None:
        """Run after every finished rescan, in its own thread so the rescan thread is never held up."""
        self.store.after_scan = lambda: threading.Thread(target=self.tick, daemon=True, name="autoscore").start()

    def current_fingerprint(self) -> tuple:
        db = self.store.reader()
        try:
            runs = db.execute("SELECT count(*), coalesce(sum(rounds), 0), coalesce(max(end_ts), ''), coalesce(sum(output), 0) "
                              "FROM runs WHERE kind='sub'").fetchone()
            flags = db.execute("SELECT count(*) FROM flags").fetchone()[0]
        finally:
            db.close()
        return (*tuple(runs), flags)

    def tick(self) -> bool:
        """Score if the indexed runs changed since the last scoring and the interval has passed. Returns True if it ran."""
        if self.store.progress.get("error") or self.store.progress.get("state") == "indexing":
            return False
        if not self._busy.acquire(blocking=False):
            return False
        try:
            fp = self.current_fingerprint()
            if fp == self.fingerprint or self.clock() - self.last_started < self.min_interval:
                return False
            self.last_started = self.clock()
            try:
                res = self.run(self.store)
            except BaseException as e:  # noqa: BLE001 - keep the console alive; shown in the header, no details leak
                self.store.progress.update(score_error=type(e).__name__)
                return False   # fingerprint unchanged: tried again after the interval
            self.fingerprint = fp
            self.store.progress.update(last_score_ok=datetime.now(timezone.utc).isoformat(), score_written=res.get("written", 0),
                                       score_error=None)
            return True
        finally:
            self._busy.release()
