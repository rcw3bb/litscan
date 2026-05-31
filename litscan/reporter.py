"""Report generation for litscan: JSON and HTML output writers.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import html as _html
import json
from datetime import datetime
from pathlib import Path

from . import __version__
from .scanner import LiteralGroup, ScanReport

_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f5f7fa;
    color: #2c3e50;
    padding: 2em;
  }
  header {
    background: #1a3a5c;
    color: #ffffff;
    border-radius: 8px;
    padding: 1.2em 1.8em;
    margin-bottom: 1.5em;
  }
  header h1 { font-size: 1.6em; font-weight: 700; letter-spacing: 0.02em; }
  header p  { font-size: 0.9em; margin-top: 0.3em; opacity: 0.85; }
  .summary {
    font-size: 0.9em;
    color: #555;
    margin-bottom: 1em;
  }
  .table-wrap { overflow-x: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
  table {
    border-collapse: collapse;
    width: 100%;
    background: #ffffff;
    font-size: 0.88em;
  }
  thead tr { background: #1a3a5c; color: #ffffff; }
  th {
    padding: 0.75em 1em;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }
  th.sortable { cursor: pointer; user-select: none; }
  th.sortable:hover { background: #254e80; }
  th.sortable .sort-icon { margin-left: 0.4em; font-size: 0.8em; }
  th.sortable.asc .sort-icon::after { content: '\\25b2'; }
  th.sortable.desc .sort-icon::after { content: '\\25bc'; }
  th.sortable:not(.asc):not(.desc) .sort-icon::after { content: '\\21c5'; opacity: 0.6; }
  .filter-row th { background: #1a3a5c; padding: 0.3em 1em 0.5em; }
  .filter-row input {
    width: 100%;
    padding: 0.3em 0.5em;
    border: 1px solid #3d6b9e;
    border-radius: 4px;
    background: #1e4575;
    color: #fff;
    font-size: 0.85em;
    outline: none;
  }
  .filter-row input::placeholder { color: #aac4e8; }
  .filter-row input:focus { border-color: #7eb3e8; background: #255085; }
  td {
    padding: 0.6em 1em;
    border-bottom: 1px solid #e8ecf0;
    vertical-align: top;
  }
  tbody tr.alt-row { background: #f0f4f8; }
  tbody tr:hover { background: #dde9f7; }
  td.row-num { text-align: right; color: #7f8c8d; font-variant-numeric: tabular-nums; width: 3em; }
  td.count    { text-align: center; font-weight: 600; color: #1a3a5c; width: 5em; }
  td.literal  code {
    background: #eef2f7;
    border-radius: 3px;
    padding: 0.1em 0.4em;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 0.95em;
    word-break: break-all;
  }
  td.literal code .truncated {
    color: #999;
    font-style: italic;
    cursor: help;
    user-select: none;
  }
  td.locations { font-family: 'Consolas', 'Courier New', monospace; font-size: 0.82em; color: #555; word-break: break-all; }
  footer { margin-top: 1.5em; font-size: 0.8em; color: #aaa; text-align: center; }
"""


def _write_json(groups: list[LiteralGroup], path: Path, run_date: str) -> None:
    """Write literal groups as a JSON file."""
    report: ScanReport = {
        "application": "litscan",
        "version": __version__,
        "run-date": run_date,
        "findings": groups,
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


_TRUNCATED_MARKER = '<span class="truncated" title="Multiline literal \u2014 only first line shown">\u2026</span>'


def _literal_display(literal: str) -> str:
    """Return HTML for the first line of *literal* with a truncation marker when multiline.

    Author: Ron Webb
    Since: 1.0.0
    """
    first_line, _, rest = literal.partition("\n")
    display = _html.escape(first_line, quote=False)
    if rest:
        display += _TRUNCATED_MARKER
    return display


def _build_html(groups: list[LiteralGroup], run_date: str) -> str:
    """Build an HTML report string for the given literal groups."""
    total = sum(g["count"] for g in groups)
    unique = len(groups)

    rows: list[str] = []
    for idx, group in enumerate(groups, start=1):
        literal_display = _literal_display(group["literal"])
        literal_attr = _html.escape(group["literal"], quote=True)
        count = group["count"]
        locations = "<br>".join(_html.escape(f, quote=False) for f in group["files"])
        alt = " alt-row" if idx % 2 == 0 else ""
        rows.append(
            f'      <tr class="data-row{alt}"'
            f' data-idx="{idx}"'
            f' data-literal="{literal_attr}"'
            f' data-count="{count}">'
            f'<td class="row-num">{idx}</td>'
            f'<td class="literal"><code>{literal_display}</code></td>'
            f'<td class="count">{count}</td>'
            f'<td class="locations">{locations}</td>'
            f"</tr>"
        )
    rows_html = "\n".join(rows)
    script = (
        "<script>\n"
        "(function () {\n"
        "  var sortCol = -1, sortDir = 1;\n"
        "\n"
        "  function sortBy(col) {\n"
        "    if (sortCol === col) { sortDir = -sortDir; }\n"
        "    else { sortCol = col; sortDir = 1; }\n"
        "    applySort();\n"
        "  }\n"
        "\n"
        "  function applySort() {\n"
        "    var tbody = document.querySelector('tbody');\n"
        "    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));\n"
        "    rows.sort(function (a, b) {\n"
        "      var va, vb;\n"
        "      if (sortCol === 0) {\n"
        "        va = a.dataset.literal.toLowerCase();\n"
        "        vb = b.dataset.literal.toLowerCase();\n"
        "      } else if (sortCol === 1) {\n"
        "        va = parseInt(a.dataset.count, 10);\n"
        "        vb = parseInt(b.dataset.count, 10);\n"
        "      } else { return 0; }\n"
        "      if (va < vb) return -sortDir;\n"
        "      if (va > vb) return sortDir;\n"
        "      return 0;\n"
        "    });\n"
        "    rows.forEach(function (r) { tbody.appendChild(r); });\n"
        "    updateNumbers();\n"
        "    restripe();\n"
        "    updateSortIcons();\n"
        "  }\n"
        "\n"
        "  function updateSortIcons() {\n"
        "    var ths = document.querySelectorAll('thead tr:first-child th.sortable');\n"
        "    ths.forEach(function (th, i) {\n"
        "      th.classList.remove('asc', 'desc');\n"
        "      if (i === sortCol) { th.classList.add(sortDir === 1 ? 'asc' : 'desc'); }\n"
        "    });\n"
        "  }\n"
        "\n"
        "  function matchCount(count, filter) {\n"
        "    var m = filter.match(/^(>=|<=|>|<|=)?(\\d+)$/);\n"
        "    if (!m) return true;\n"
        "    var op = m[1] || '=', val = parseInt(m[2], 10);\n"
        "    if (op === '>') return count > val;\n"
        "    if (op === '<') return count < val;\n"
        "    if (op === '>=') return count >= val;\n"
        "    if (op === '<=') return count <= val;\n"
        "    return count === val;\n"
        "  }\n"
        "\n"
        "  function applyFilter() {\n"
        "    var litFilter = document.getElementById('filter-literal').value.toLowerCase();\n"
        "    var cntFilter = document.getElementById('filter-count').value.trim();\n"
        "    var tbody = document.querySelector('tbody');\n"
        "    tbody.querySelectorAll('tr').forEach(function (row) {\n"
        "      var litMatch = !litFilter || row.dataset.literal.toLowerCase().indexOf(litFilter) !== -1;\n"
        "      var cntMatch = !cntFilter || matchCount(parseInt(row.dataset.count, 10), cntFilter);\n"
        "      row.style.display = (litMatch && cntMatch) ? '' : 'none';\n"
        "    });\n"
        "    updateNumbers();\n"
        "    restripe();\n"
        "  }\n"
        "\n"
        "  function updateNumbers() {\n"
        "    var num = 1;\n"
        "    document.querySelectorAll('tbody tr').forEach(function (row) {\n"
        "      if (row.style.display !== 'none') {\n"
        "        row.querySelector('.row-num').textContent = num++;\n"
        "      }\n"
        "    });\n"
        "  }\n"
        "\n"
        "  function restripe() {\n"
        "    var num = 0;\n"
        "    document.querySelectorAll('tbody tr').forEach(function (row) {\n"
        "      if (row.style.display !== 'none') {\n"
        "        num++;\n"
        "        row.classList.toggle('alt-row', num % 2 === 0);\n"
        "      }\n"
        "    });\n"
        "  }\n"
        "\n"
        "  window.litscanSortBy = sortBy;\n"
        "  window.litscanFilter = applyFilter;\n"
        "})();\n"
        "</script>\n"
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>LitScan {__version__} Report</title>\n"
        "  <style>\n"
        f"{_CSS}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <header>\n"
        f"    <h1>LitScan {__version__} Report</h1>\n"
        f"    <p>Date Run: {run_date}</p>\n"
        "  </header>\n"
        f'  <p class="summary">Found {total} literals &mdash; {unique} unique</p>\n'
        '  <div class="table-wrap">\n'
        "  <table>\n"
        "    <thead>\n"
        "      <tr>"
        "<th>#</th>"
        '<th class="sortable" onclick="litscanSortBy(0)">Literal<span class="sort-icon"></span></th>'
        '<th class="sortable" onclick="litscanSortBy(1)">Count<span class="sort-icon"></span></th>'
        "<th>Locations</th>"
        "</tr>\n"
        '      <tr class="filter-row">'
        "<th></th>"
        '<th><input type="text" id="filter-literal" placeholder="Filter literal\u2026" oninput="litscanFilter()"></th>'
        '<th><input type="text" id="filter-count" placeholder="e.g. &gt;5" oninput="litscanFilter()"></th>'
        "<th></th>"
        "</tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        f"{rows_html}\n"
        "    </tbody>\n"
        "  </table>\n"
        "  </div>\n"
        f"  <footer>Generated by LitScan {__version__}</footer>\n"
        f"{script}"
        "</body>\n"
        "</html>\n"
    )


def _write_html(groups: list[LiteralGroup], path: Path, run_date: str) -> None:
    """Write literal groups as an HTML report file."""
    path.write_text(_build_html(groups, run_date), encoding="utf-8")


def write_outputs(
    groups: list[LiteralGroup],
    output_dir: Path,
    stem: str,
    fmt: str,
) -> list[Path]:
    """Write output files according to the requested format.

    Returns the list of paths written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now().strftime(_DATE_FORMAT)
    written: list[Path] = []
    if fmt in ("json", "all"):
        json_path = output_dir / f"{stem}.json"
        _write_json(groups, json_path, run_date)
        written.append(json_path)
    if fmt in ("html", "all"):
        html_path = output_dir / f"{stem}.html"
        _write_html(groups, html_path, run_date)
        written.append(html_path)
    return written
