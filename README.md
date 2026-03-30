# Office of Foreign Assets Control (OFAC) Geo Restriction Feed

This repository builds a tiny GitHub Pages site that publishes a JSON feed of country codes for coarse GeoIP blocking.

It is intentionally split into four layers:

1. `sanctioned_country_codes`: a country-level union inferred from OFAC, EU, UK, and UN country-specific sanctions regimes.
2. `heuristic_recommended_country_codes`: the deterministic score-based recommendation.
3. `ai_recommended_country_codes`: an advisory review produced by the optional OpenAI step.
4. `effective_geoip_block_country_codes`: the published block list after applying explicit manual overrides to the heuristic recommendation from [`config/overrides.json`](/Users/gornyj/projects/personal/ofac-georestriction/config/overrides.json).

This is not a sanctions compliance engine and does not replace legal review or entity screening.

## Outputs

The generator writes these public files into [`docs/`](/Users/gornyj/projects/personal/ofac-georestriction/docs):

- `index.html`: human-readable landing page
- `countries.json`: the smallest stable machine-readable payload
- `sanctions.json`: richer metadata, evidence, and disclaimer
- `evidence.json`: normalized source evidence and curation details

## Sources

Primary sources:

- OFAC sanctions programs and country information: [ofac.treasury.gov/sanctions-programs-and-country-information](https://ofac.treasury.gov/sanctions-programs-and-country-information)
- UN consolidated list page: [main.un.org/securitycouncil/en/content/un-sc-consolidated-list](https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list)
- UN consolidated XML: [scsanctions.un.org/resources/xml/en/consolidated.xml](https://scsanctions.un.org/resources/xml/en/consolidated.xml)
- EU sanctions tracker regimes: [data.europa.eu/apps/eusanctionstracker/regimes/](https://data.europa.eu/apps/eusanctionstracker/regimes/)
- UK sanctions list publication: [www.gov.uk/government/publications/the-uk-sanctions-list](https://www.gov.uk/government/publications/the-uk-sanctions-list)
- UK sanctions list XML: [sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml](https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml)

Supporting source:

- OFAC sanctions search: [sanctionssearch.ofac.treas.gov](https://sanctionssearch.ofac.treas.gov/)

The generator does not currently scrape the OFAC search UI because it is entity-oriented rather than a stable country-code feed. It is still listed in the published metadata as a supporting source.

## Heuristic

The default heuristic is intentionally conservative. It assigns points for these signals:

- `OFAC present`: 2 points
- `Present in 2+ authorities`: 1 point
- `Present in 3+ authorities`: 2 points
- `UN present`: 1 point
- `OFAC broad-country baseline`: 3 points

The default recommendation threshold is `5`.

This means a country is not recommended for country-wide GeoIP blocking merely because it appears in multiple sanctions authorities. The current threshold favors comprehensive or especially strong evidence while still making the scoring rationale inspectable in `evidence.json`.

## Local Usage

Run the generator:

```bash
python3 scripts/build_site.py
```

Optional AI-assisted curation:

```bash
OPENAI_API_KEY=... OPENAI_MODEL=gpt-5-mini python3 scripts/build_site.py
```

The AI step is advisory only. It does not control the effective GeoIP list. The generator always constrains the model output to country codes already supported by source evidence.

## Manual Overrides

Edit [`config/overrides.json`](/Users/gornyj/projects/personal/ofac-georestriction/config/overrides.json):

```json
{
  "manual_include_country_codes": ["RU"],
  "manual_exclude_country_codes": ["VE"],
  "notes_by_country_code": {
    "RU": "Business-approved operational block",
    "VE": "Active contract; do not block nationally"
  }
}
```

## GitHub Actions

Two workflows are included:

- [`update-sanctions.yml`](/Users/gornyj/projects/personal/ofac-georestriction/.github/workflows/update-sanctions.yml): scheduled daily refresh and automatic commit if generated files changed
- [`deploy-pages.yml`](/Users/gornyj/projects/personal/ofac-georestriction/.github/workflows/deploy-pages.yml): deploys the `docs/` folder to GitHub Pages on push to `main`

Required repository setup:

1. Enable GitHub Pages for the repository and choose `GitHub Actions` as the source.
2. Add `OPENAI_API_KEY` as a repository secret if you want AI-assisted review in CI.
3. Optionally add a repository variable `OPENAI_MODEL` to override the default model alias.

## Design Notes

- The site is static and framework-free.
- The public JSON is ISO 3166-1 alpha-2 oriented. Non-country or non-ISO territorial regimes are not emitted as country codes.
- The default heuristic is intentionally conservative to reduce false-positive country blocking, and its score breakdown is published so you can tune the threshold or weights later.
- The heuristic is the canonical decision path. The AI layer is published as decision support only.
- OFAC itself states that it does not maintain a single list of countries with which U.S. persons cannot do business, so the public feed includes an explicit disclaimer and should be treated as an operational artifact, not a legal determination.
