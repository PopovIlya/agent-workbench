"""The /compare page as server-rendered HTML (EXP1-R22C): the table (200) and the error pages (404, 422, 503).

Main goal: one complete document per answer, built from the comparison tree with every value escaped.
Does: use the rows of compare_format (one formatter for page and CLI text), link /static/compare.css.
Does not: carry a script, a style tag or attribute, a form, a link to another comparison, or any log text (CON-033, CON-034, CON-035).
"""

from __future__ import annotations

from html import escape

from . import compare_format as fmt

UPDATING = "The console is updating its index. Reload this page later."
BUILDING = UPDATING


def _e(v: str) -> str:
    return escape(v, quote=True)


def _doc(inner: str) -> str:
    return ('<!doctype html>\n<html lang="en">\n'
            '<head><meta charset="utf-8"><title>Ticket comparison</title><link rel="stylesheet" href="/static/compare.css"></head>\n'
            f'<body><h1>Ticket comparison</h1>\n{inner}\n</body></html>\n')


def _error(inner: str) -> str:
    return _doc(f'<p class="error">{inner}</p>')


def render(tree: dict) -> str:
    """200: one table, a row per figure."""
    head = ('<thead><tr><th scope="col">' + _e(fmt.HEADINGS[0]) + '</th>'
            f'<th scope="col" class="a">{_e(tree["a"]["key"])}</th><th scope="col" class="b">{_e(tree["b"]["key"])}</th>'
            f'<th scope="col" class="d">{_e(fmt.HEADINGS[1])}</th></tr></thead>')
    body = "\n".join(
        f'<tr data-row="{_e(r.id)}"><th scope="row">{_e(r.label)}</th><td class="a">{_e(r.a)}</td><td class="b">{_e(r.b)}</td>'
        f'<td class="d"><span class="diff">{_e(r.diff)}</span> (<span class="ratio">{_e(r.ratio)}</span>)</td></tr>'
        for r in fmt.rows(tree))
    return _doc(f'<table class="compare">\n{head}\n<tbody>\n{body}\n</tbody>\n</table>')


def missing_page(names: list[str]) -> str:
    """422: a or b missing, empty or only spaces; names the missing parameter(s)."""
    codes = ", ".join(f"<code>{_e(n)}</code>" for n in names)
    return _error(f"Missing parameter{'s' if len(names) > 1 else ''}: {codes}.")


def building_page() -> str:
    """503: the console is updating its index (any scan, the first one included); no key, no figure."""
    return _error(UPDATING)


def error_page() -> str:
    """500: the comparison could not be read; no detail."""
    return _error("The comparison could not be built. Try again later.")


def unknown_page(keys: list[str]) -> str:
    """404: names the unknown key(s), escaped."""
    codes = ", ".join(f"<code>{_e(k)}</code>" for k in keys)
    return _error(f"Unknown ticket key{'s' if len(keys) > 1 else ''}: {codes}.")
