"""
KAVACH — Incident/Prevention report builder
============================================

Regenerates the auto incident report as Markdown and a branded PDF, purely
from the deterministic engines (no network, no LLM). Run from repo root:

    cd backend && pip install -r requirements.txt
    pip install markdown xhtml2pdf          # report-only extras
    cd .. && python reports/build_report.py [scenario_id]

Outputs land next to this file:
    reports/KAVACH_Incident_Prevention_Report.md
    reports/KAVACH_Incident_Prevention_Report.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

# make `app` importable from the repo's backend/ package
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.risk.report import generate_markdown  # noqa: E402

CSS = """
@page { size: A4; margin: 1.7cm 1.8cm 1.9cm 1.8cm;
  @frame footer { -pdf-frame-content: footerContent; bottom: 0.8cm;
    margin-left: 1.8cm; margin-right: 1.8cm; height: 1cm; } }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1c2333; line-height: 1.5; }
h1 { font-size: 21pt; color: #0f2f52; margin: 0 0 2px 0; letter-spacing: 0.5px; }
h2 { font-size: 13.5pt; color: #12639c; border-bottom: 1.5px solid #29b6f6; padding-bottom: 3px; margin: 20px 0 8px 0; }
h3 { font-size: 11.5pt; color: #12639c; margin: 14px 0 5px 0; }
p { margin: 6px 0; }
strong { color: #0f2f52; }
blockquote { background: #eef6fc; border-left: 3px solid #29b6f6; margin: 10px 0; padding: 8px 12px; color: #33475b; font-size: 9pt; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9pt; }
th { background: #12639c; color: #ffffff; text-align: left; padding: 6px 9px; border: 0.5px solid #12639c; }
td { padding: 5px 9px; border: 0.5px solid #cdd7e5; }
tr:nth-child(even) td { background: #f4f8fc; }
li { margin: 3px 0; }
em { color: #5a6b82; }
.footer { color: #8a97ab; font-size: 7.5pt; text-align: center; border-top: 0.5px solid #cdd7e5; padding-top: 4px; }
"""


def build(scenario_id: str = "vizag_replay") -> None:
    import markdown
    from xhtml2pdf import pisa

    md_text = generate_markdown(scenario_id)
    (Path(__file__).parent / "KAVACH_Incident_Prevention_Report.md").write_text(
        md_text, encoding="utf-8")

    body = markdown.markdown(md_text, extensions=["tables", "sane_lists"])
    html = (f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
            f'{body}<div id="footerContent" class="footer">KAVACH — The digital '
            "armour for zero-harm industrial operations · Synthetic composite · "
            "Page <pdf:pagenumber> of <pdf:pagecount></div></body></html>")
    out = Path(__file__).parent / "KAVACH_Incident_Prevention_Report.pdf"
    with open(out, "wb") as fh:
        res = pisa.CreatePDF(html, dest=fh)
    print(f"{'OK' if not res.err else 'ERROR'}: wrote {out}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "vizag_replay")
