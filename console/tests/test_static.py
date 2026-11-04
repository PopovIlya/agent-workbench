"""The strict CSP (default-src 'self') is kept: no inline script or style, no style attribute in markup, nothing loaded from another origin."""

import re
from pathlib import Path

from agent_console import server

STATIC = Path(server.STATIC)
FILES = sorted(p for p in STATIC.iterdir() if p.suffix in (".html", ".js", ".css"))
SVG_NS = "http://www.w3.org/2000/svg"      # a namespace name, never fetched


def test_static_files_are_found():
    assert {"index.html", "app.js", "ctq.css", "ctq-lib.js", "style.css"} <= {p.name for p in FILES}


def test_html_has_no_inline_script_style_or_style_attribute():
    for p in (x for x in FILES if x.suffix == ".html"):
        html = p.read_text()
        assert not re.search(r"<style", html, re.I), p.name
        assert not re.search(r"\sstyle\s*=", html, re.I), p.name
        for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.I | re.S):
            assert re.search(r'\bsrc="/static/[\w.-]+\.js"', m.group(1)) and not m.group(2).strip(), (p.name, m.group(0)[:80])


def test_scripts_never_write_a_style_attribute_or_markup():
    for p in (x for x in FILES if x.suffix == ".js"):
        js = p.read_text()
        assert not re.search(r"setAttribute\(\s*[\"']style[\"']", js), p.name        # el.style.width = ... (CSSOM) is allowed, a style attribute is not
        assert not re.search(r"[\"']style[\"']\s*:", js), p.name
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert bad not in js, (p.name, bad)


def test_nothing_in_static_loads_another_origin():
    for p in FILES:
        text = p.read_text().replace(SVG_NS, "")
        assert not re.search(r"https?://", text), (p.name, re.search(r".{30}https?://.{30}", text))
        assert not re.search(r"(?:src|href)\s*=\s*[\"']//", text), p.name
        assert "@import" not in text and not re.search(r"url\(\s*[\"']?(?!/static/|#|data:)", text), p.name
