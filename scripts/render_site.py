from __future__ import annotations

from html import escape
from typing import Any


def render_index(
    payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    heuristic_threshold: int,
) -> str:
    effective_codes = payload["effective_geoip_block_country_codes"]
    effective_code_list = ", ".join(effective_codes) if effective_codes else "None"
    score_lookup = {
        item["country_code"]: item for item in evidence_payload.get("scores", [])
    }
    rows = []
    for country in payload["countries"]:
        authorities = ", ".join(country["authorities"])
        decision = "yes" if country["country_code"] in effective_codes else "no"
        score = score_lookup.get(country["country_code"], {}).get("score", 0)
        rows.append(
            "<tr>"
            f"<td>{escape(country['country_code'])}</td>"
            f"<td>{escape(country['country_name'])}</td>"
            f"<td>{escape(authorities)}</td>"
            f"<td>{escape(str(score))}</td>"
            f"<td>{escape(decision)}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)

    curation = evidence_payload["curation"]
    ai_mode = curation["mode"]
    ai_error = curation.get("ai_error")
    ai_model = curation.get("model", "unknown")
    ai_summary = curation.get("ai_summary")
    if not ai_summary:
        if ai_mode == "fallback" and ai_error:
            ai_summary = f"AI review was attempted with model {ai_model}, but failed: {ai_error}"
        elif ai_mode == "heuristic" and ai_error:
            ai_summary = ai_error
        else:
            ai_summary = "No AI review was used for this build."

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Sanctions-informed GeoIP decision-support data with inspectable evidence and limitations.">
    <title>Sanctions-Informed GeoIP Feed</title>
    <link rel="icon" href="./favicon.ico" sizes="any">
    <style>
      :root {{
        color-scheme: light;
        --bg: #f5f7f2;
        --panel: #ffffff;
        --ink: #142119;
        --muted: #516355;
        --line: #d7e0d5;
        --accent: #295135;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(41,81,53,0.08), transparent 38%),
          linear-gradient(180deg, #eef3ec 0%, var(--bg) 100%);
        color: var(--ink);
      }}
      main {{
        max-width: 960px;
        margin: 0 auto;
        padding: 40px 20px 72px;
      }}
      h1 {{
        font-size: clamp(2rem, 5vw, 3.4rem);
        line-height: 1;
        margin: 0 0 12px;
      }}
      p, li {{
        color: var(--muted);
        line-height: 1.6;
      }}
      .panel {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 20px;
        margin-top: 20px;
        box-shadow: 0 12px 30px rgba(20, 33, 25, 0.05);
      }}
      .notice {{
        background: #fffaf0;
        border-color: #d6b96b;
      }}
      .notice h2 {{
        margin-top: 0;
      }}
      .codes {{
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 1.1rem;
        color: var(--accent);
      }}
      a {{
        color: var(--accent);
      }}
      .table-scroll {{
        overflow-x: auto;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
      }}
      caption {{
        text-align: left;
        color: var(--muted);
        padding-bottom: 12px;
      }}
      th, td {{
        text-align: left;
        padding: 10px 8px;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }}
      th {{
        color: var(--ink);
      }}
      .small {{
        font-size: 0.92rem;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Sanctions-Informed GeoIP Feed</h1>
      <p>
        Decision-support JSON for coarse country-level GeoIP restrictions, refreshed from OFAC,
        EU, UK, and UN sources. This is not sanctions compliance automation.
      </p>

      <section class="panel notice">
        <h2>Limitations / Not legal advice</h2>
        <p>{escape(payload['disclaimer'])}</p>
      </section>

      <section class="panel">
        <p class="small"><strong>Generated:</strong> {escape(payload['generated_at'])}</p>
        <p class="small"><strong>Effective country codes:</strong></p>
        <p class="codes">{escape(effective_code_list)}</p>
        <p class="small">
          <a href="./countries.json">countries.json</a> ·
          <a href="./sanctions.json">sanctions.json</a> ·
          <a href="./evidence.json">evidence.json</a>
        </p>
      </section>

      <section class="panel">
        <h2>Curation</h2>
        <p class="small"><strong>Mode:</strong> {escape(ai_mode)}</p>
        <p class="small"><strong>Model:</strong> {escape(ai_model)}</p>
        <p class="small"><strong>Heuristic threshold:</strong> {heuristic_threshold}</p>
        <p>{escape(ai_summary)}</p>
      </section>

      <section class="panel">
        <h2>Countries</h2>
        <div class="table-scroll">
          <table>
            <caption>Country evidence, score, and effective blocking decision</caption>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Name</th>
                <th scope="col">Authorities</th>
                <th scope="col">Score</th>
                <th scope="col">Blocked</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>
      </section>

      <p class="small">
        <a href="https://github.com/jtgorny/ofac-georestriction">Source code and documentation</a>
        · <a href="https://github.com/jtgorny/ofac-georestriction/blob/main/LICENSE">Apache-2.0 license</a>
      </p>
    </main>
  </body>
</html>
"""
