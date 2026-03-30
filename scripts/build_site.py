#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape, unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
CONFIG_DIR = ROOT / "config"
OVERRIDES_PATH = CONFIG_DIR / "overrides.json"

USER_AGENT = "ofac-georestriction-site-builder/1.0 (+https://github.com/)"

OFAC_PROGRAMS_URL = "https://ofac.treasury.gov/sanctions-programs-and-country-information"
OFAC_COUNTRY_FAQ_URL = (
    "https://ofac.treasury.gov/sanctions-programs-and-country-information/"
    "where-is-ofacs-country-list-what-countries-do-i-need-to-worry-about-in-terms-of-us-sanctions"
)
OFAC_SANCTIONS_SEARCH_URL = "https://sanctionssearch.ofac.treas.gov/"
UN_LIST_PAGE_URL = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
UN_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
EU_REGIMES_URL = "https://data.europa.eu/apps/eusanctionstracker/regimes/"
UK_PAGE_URL = "https://www.gov.uk/government/publications/the-uk-sanctions-list"
UK_XML_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.xml"

DISCLAIMER = (
    "This feed is an operational, country-code-oriented GeoIP artifact derived from public "
    "sanctions sources. It is provided for informational purposes only, is not legal advice, "
    "and is not a substitute for sanctions screening, export-control review, or advice from "
    "qualified counsel. Country-level blocking is necessarily coarse: many sanctions programs "
    "are targeted at specific people, entities, sectors, or regions rather than an entire "
    "country. OFAC explicitly states that it does not maintain a single list of countries with "
    "which U.S. persons cannot do business. Use this feed carefully and verify obligations "
    "against the underlying authorities."
)

HEURISTIC_RULES = {
    "ofac_broad_country": {
        "points": 3,
        "description": "Country is part of the OFAC broad-country baseline.",
    },
    "ofac_present": {
        "points": 2,
        "description": "Country has an OFAC country/program signal.",
    },
    "multi_authority_2_plus": {
        "points": 1,
        "description": "Country is present in at least two authorities.",
    },
    "multi_authority_3_plus": {
        "points": 2,
        "description": "Country is present in at least three authorities.",
    },
    "un_present": {
        "points": 1,
        "description": "Country is present in a UN sanctions committee program.",
    },
}

HEURISTIC_THRESHOLD = 5

COUNTRY_NAMES = {
    "AF": "Afghanistan",
    "BA": "Bosnia and Herzegovina",
    "BY": "Belarus",
    "CD": "Democratic Republic of the Congo",
    "CF": "Central African Republic",
    "CU": "Cuba",
    "ET": "Ethiopia",
    "GN": "Guinea",
    "GT": "Guatemala",
    "GW": "Guinea-Bissau",
    "HK": "Hong Kong",
    "HT": "Haiti",
    "IQ": "Iraq",
    "IR": "Iran",
    "KP": "North Korea",
    "LB": "Lebanon",
    "LY": "Libya",
    "MD": "Moldova",
    "ML": "Mali",
    "MM": "Myanmar",
    "NI": "Nicaragua",
    "RU": "Russia",
    "SD": "Sudan",
    "SO": "Somalia",
    "SS": "South Sudan",
    "SY": "Syria",
    "TN": "Tunisia",
    "UA": "Ukraine",
    "VE": "Venezuela",
    "YE": "Yemen",
}

OFAC_PROGRAM_TO_CODE = {
    "Afghanistan-Related Sanctions": "AF",
    "Belarus Sanctions": "BY",
    "Burma-Related Sanctions": "MM",
    "Central African Republic Sanctions": "CF",
    "Cuba Sanctions": "CU",
    "Democratic Republic of the Congo-Related Sanctions": "CD",
    "Ethiopia-Related Sanctions": "ET",
    "Hong Kong-Related Sanctions": "HK",
    "Iran Sanctions": "IR",
    "Iraq-Related Sanctions": "IQ",
    "Lebanon-Related Sanctions": "LB",
    "Libya Sanctions": "LY",
    "Mali-Related Sanctions": "ML",
    "Nicaragua-related Sanctions": "NI",
    "North Korea Sanctions": "KP",
    "Promoting Accountability for Assad and Regional Stabilization Sanctions (PAARSS)": "SY",
    "Russia-related Sanctions": "RU",
    "Russian Harmful Foreign Activities Sanctions": "RU",
    "Somalia Sanctions": "SO",
    "South Sudan-Related Sanctions": "SS",
    "Sudan and Darfur Sanctions": "SD",
    "Ukraine-/Russia-related Sanctions": "RU",
    "Venezuela-Related Sanctions": "VE",
    "Yemen-related Sanctions": "YE",
}

OFAC_BROAD_COUNTRY_CODES = {"CU", "IR", "KP", "SY"}

EU_REGIME_TO_CODE = {
    "AFG": "AF",
    "BLR": "BY",
    "CAF": "CF",
    "COD": "CD",
    "GIN": "GN",
    "GTM": "GT",
    "HTI": "HT",
    "IRN": "IR",
    "IRQ": "IQ",
    "LBY": "LY",
    "MDA": "MD",
    "MLI": "ML",
    "MMR": "MM",
    "NIC": "NI",
    "PRK": "KP",
    "RUS": "RU",
    "RUSDA": "RU",
    "SDN": "SD",
    "SDNZ": "SD",
    "SOM": "SO",
    "SSD": "SS",
    "SYR": "SY",
    "TUN": "TN",
    "UKR": "UA",
    "VEN": "VE",
    "YEM": "YE",
}

UK_REGIME_TO_CODE = {
    "The Afghanistan (Sanctions) (EU Exit) Regulations 2020": "AF",
    "The Bosnia and Herzegovina (Sanctions) (EU Exit) Regulations 2020": "BA",
    "The Central African Republic (Sanctions) (EU Exit) Regulations 2020": "CF",
    "The Democratic People's Republic of Korea (Sanctions) (EU Exit) Regulations 2019": "KP",
    "The Democratic Republic of the Congo (Sanctions) (EU Exit) Regulations 2019": "CD",
    "The Guinea (Sanctions) (EU Exit) Regulations 2019": "GN",
    "The Haiti (Sanctions) Regulations 2022": "HT",
    "The Iran (Sanctions) (Nuclear) (EU Exit) Regulations 2019": "IR",
    "The Iran (Sanctions) Regulations 2023": "IR",
    "The Iraq (Sanctions) (EU Exit) Regulations 2020": "IQ",
    "The Libya (Sanctions) (EU Exit) Regulations 2020": "LY",
    "The Mali (Sanctions) (EU Exit) Regulations 2020": "ML",
    "The Myanmar (Sanctions) Regulations 2021": "MM",
    "The Nicaragua (Sanctions) (EU Exit) Regulations 2020": "NI",
    "The Republic of Belarus (Sanctions) (EU Exit) Regulations 2019": "BY",
    "The Republic of Guinea-Bissau (Sanctions) (EU Exit) Regulations 2019": "GW",
    "The Russia (Sanctions) (EU Exit) Regulations 2019": "RU",
    "The Somalia (Sanctions) (EU Exit) Regulations 2020": "SO",
    "The South Sudan (Sanctions) (EU Exit) Regulations 2019": "SS",
    "The Sudan (Sanctions) (EU Exit) Regulations 2020": "SD",
    "The Syria (Sanctions) (EU Exit) Regulations 2019": "SY",
    "The Venezuela (Sanctions) (EU Exit) Regulations 2019": "VE",
    "The Yemen (Sanctions) (EU Exit) Regulations 2020": "YE",
}

UN_PREFIX_TO_COUNTRY = {
    "CD": ("CD", "Democratic Republic of the Congo"),
    "CF": ("CF", "Central African Republic"),
    "GB": ("GW", "Guinea-Bissau"),
    "HT": ("HT", "Haiti"),
    "IQ": ("IQ", "Iraq"),
    "IR": ("IR", "Iran"),
    "KP": ("KP", "North Korea"),
    "LY": ("LY", "Libya"),
    "SD": ("SD", "Sudan"),
    "SO": ("SO", "Somalia"),
    "SS": ("SS", "South Sudan"),
    "YE": ("YE", "Yemen"),
}

UN_PREFIX_LABELS = {
    "CD": "1533 Committee (Democratic Republic of the Congo)",
    "CF": "2745 Committee (Central African Republic)",
    "GB": "2048 Committee (Guinea-Bissau)",
    "HT": "2653 Committee (Haiti)",
    "IQ": "1518 Committee (Iraq)",
    "IR": "1737 Committee (Iran)",
    "KP": "1718 Committee (DPRK)",
    "LY": "1970 Committee (Libya)",
    "SD": "1591 Committee (Sudan)",
    "SO": "2713 Committee (Somalia)",
    "SS": "2206 Committee (South Sudan)",
    "YE": "2140 Committee (Yemen)",
}


@dataclass(frozen=True)
class SourceHit:
    authority: str
    title: str
    url: str
    last_updated: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "authority": self.authority,
            "title": self.title,
            "url": self.url,
        }
        if self.last_updated:
            data["last_updated"] = self.last_updated
        if self.notes:
            data["notes"] = self.notes
        return data


class BuildError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_text(url: str, *, include_user_agent: bool = True) -> str:
    headers = {"User-Agent": USER_AGENT} if include_user_agent else {}
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        raise BuildError(f"failed to fetch {url}: {exc}") from exc


def fetch_bytes(url: str, *, include_user_agent: bool = True) -> bytes:
    headers = {"User-Agent": USER_AGENT} if include_user_agent else {}
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except (HTTPError, URLError) as exc:
        raise BuildError(f"failed to fetch {url}: {exc}") from exc


def load_overrides() -> dict[str, Any]:
    if not OVERRIDES_PATH.exists():
        raise BuildError(f"missing overrides file at {OVERRIDES_PATH}")

    data = json.loads(OVERRIDES_PATH.read_text())
    return {
        "manual_include_country_codes": sorted(
            {code.strip().upper() for code in data.get("manual_include_country_codes", []) if code}
        ),
        "manual_exclude_country_codes": sorted(
            {code.strip().upper() for code in data.get("manual_exclude_country_codes", []) if code}
        ),
        "notes_by_country_code": {
            code.strip().upper(): str(note).strip()
            for code, note in data.get("notes_by_country_code", {}).items()
            if code and str(note).strip()
        },
    }


def parse_ofac_hits() -> tuple[list[SourceHit], dict[str, Any]]:
    html = fetch_text(OFAC_PROGRAMS_URL)
    pattern = re.compile(
        r'<td[^>]*views-field-title[^>]*>\s*<a href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]+)</a>\s*</td>'
        r"\s*<td[^>]*views-field-field-release-date[^>]*>.*?<time datetime=\"(?P<datetime>[^\"]+)\"[^>]*>"
        r"(?P<label>[^<]+)</time>",
        re.S,
    )
    hits: list[SourceHit] = []
    seen: set[tuple[str, str]] = set()
    for match in pattern.finditer(html):
        title = unescape(match.group("title")).strip()
        country_code = OFAC_PROGRAM_TO_CODE.get(title)
        if not country_code:
            continue
        hit_key = (country_code, title)
        if hit_key in seen:
            continue
        seen.add(hit_key)
        hits.append(
            SourceHit(
                authority="OFAC",
                title=title,
                url=urljoin(OFAC_PROGRAMS_URL, match.group("href")),
                last_updated=match.group("datetime"),
                notes=(
                    "OFAC broad-country baseline" if country_code in OFAC_BROAD_COUNTRY_CODES else None
                ),
            )
        )
    metadata = {
        "source_url": OFAC_PROGRAMS_URL,
        "supporting_url": OFAC_COUNTRY_FAQ_URL,
        "country_search_url": OFAC_SANCTIONS_SEARCH_URL,
        "broad_country_codes": sorted(OFAC_BROAD_COUNTRY_CODES),
    }
    return hits, metadata


def parse_eu_hits() -> tuple[list[SourceHit], dict[str, Any]]:
    # The EU tracker returns a static HTML list without a custom user-agent,
    # but a JavaScript shell with one.
    html = fetch_text(EU_REGIMES_URL, include_user_agent=False)
    slugs = sorted(set(re.findall(r"/regimes/([A-Z0-9]+)", html)))
    hits: list[SourceHit] = []
    for slug in slugs:
        country_code = EU_REGIME_TO_CODE.get(slug)
        if not country_code:
            continue
        hits.append(
            SourceHit(
                authority="EU",
                title=f"EU sanctions regime {slug}",
                url=urljoin(EU_REGIMES_URL, slug),
            )
        )
    return hits, {"source_url": EU_REGIMES_URL}


def parse_uk_hits() -> tuple[list[SourceHit], dict[str, Any]]:
    xml_bytes = fetch_bytes(UK_XML_URL)
    root = ET.fromstring(xml_bytes)
    date_generated = root.findtext("DateGenerated")
    regime_names = sorted(
        {
            (designation.findtext("RegimeName") or "").strip()
            for designation in root.findall("Designation")
            if (designation.findtext("RegimeName") or "").strip()
        }
    )
    hits: list[SourceHit] = []
    for regime_name in regime_names:
        country_code = UK_REGIME_TO_CODE.get(regime_name)
        if not country_code:
            continue
        hits.append(
            SourceHit(
                authority="UK",
                title=regime_name,
                url=UK_XML_URL,
                last_updated=date_generated,
            )
        )
    return hits, {"publication_url": UK_PAGE_URL, "source_url": UK_XML_URL, "date_generated": date_generated}


def parse_un_hits() -> tuple[list[SourceHit], dict[str, Any]]:
    xml_bytes = fetch_bytes(UN_XML_URL)
    root = ET.fromstring(xml_bytes)
    date_generated = root.attrib.get("dateGenerated")
    prefixes: set[str] = set()
    for section_name in ("INDIVIDUALS", "ENTITIES"):
        section = root.find(section_name)
        if section is None:
            continue
        for node in section:
            reference_number = (node.findtext("REFERENCE_NUMBER") or "").strip()
            if len(reference_number) >= 2:
                prefixes.add(reference_number[:2])

    hits: list[SourceHit] = []
    for prefix in sorted(prefixes):
        mapping = UN_PREFIX_TO_COUNTRY.get(prefix)
        if not mapping:
            continue
        country_code, _ = mapping
        hits.append(
            SourceHit(
                authority="UN",
                title=UN_PREFIX_LABELS[prefix],
                url=UN_XML_URL,
                last_updated=date_generated,
            )
        )
    return hits, {"page_url": UN_LIST_PAGE_URL, "source_url": UN_XML_URL, "date_generated": date_generated}


def build_country_evidence(hits: list[SourceHit]) -> dict[str, dict[str, Any]]:
    countries: dict[str, dict[str, Any]] = {}
    for hit in hits:
        country_code = hit_to_country_code(hit)
        if country_code not in countries:
            countries[country_code] = {
                "country_code": country_code,
                "country_name": COUNTRY_NAMES.get(country_code, country_code),
                "sources": [],
                "authorities": set(),
            }
        countries[country_code]["sources"].append(hit.to_dict())
        countries[country_code]["authorities"].add(hit.authority)

    for country in countries.values():
        country["sources"] = sorted(
            country["sources"], key=lambda item: (item["authority"], item["title"], item["url"])
        )
        country["authorities"] = sorted(country["authorities"])
    return dict(sorted(countries.items()))


def compute_country_scores(countries: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    scorecards: dict[str, dict[str, Any]] = {}
    for country_code, country in countries.items():
        authorities = set(country["authorities"])
        triggers: list[dict[str, Any]] = []
        score = 0

        if country_code in OFAC_BROAD_COUNTRY_CODES:
            rule = HEURISTIC_RULES["ofac_broad_country"]
            triggers.append({"rule": "ofac_broad_country", **rule})
            score += rule["points"]

        if "OFAC" in authorities:
            rule = HEURISTIC_RULES["ofac_present"]
            triggers.append({"rule": "ofac_present", **rule})
            score += rule["points"]

        if len(authorities) >= 2:
            rule = HEURISTIC_RULES["multi_authority_2_plus"]
            triggers.append({"rule": "multi_authority_2_plus", **rule})
            score += rule["points"]

        if len(authorities) >= 3:
            rule = HEURISTIC_RULES["multi_authority_3_plus"]
            triggers.append({"rule": "multi_authority_3_plus", **rule})
            score += rule["points"]

        if "UN" in authorities:
            rule = HEURISTIC_RULES["un_present"]
            triggers.append({"rule": "un_present", **rule})
            score += rule["points"]

        scorecards[country_code] = {
            "country_code": country_code,
            "country_name": country["country_name"],
            "authority_count": len(authorities),
            "authorities": country["authorities"],
            "score": score,
            "triggers": triggers,
            "recommended_by_heuristic": score >= HEURISTIC_THRESHOLD,
        }
    return scorecards


def hit_to_country_code(hit: SourceHit) -> str:
    title = hit.title
    if hit.authority == "OFAC":
        return OFAC_PROGRAM_TO_CODE[title]
    if hit.authority == "EU":
        return EU_REGIME_TO_CODE[title.rsplit(" ", 1)[-1]]
    if hit.authority == "UK":
        return UK_REGIME_TO_CODE[title]
    if hit.authority == "UN":
        for prefix, (_, _) in UN_PREFIX_TO_COUNTRY.items():
            if UN_PREFIX_LABELS[prefix] == title:
                return UN_PREFIX_TO_COUNTRY[prefix][0]
    raise BuildError(f"cannot resolve country code for hit: {hit}")


def heuristic_recommendations(country_codes: set[str]) -> list[str]:
    raise NotImplementedError("use score-based heuristic evaluation")


def build_openai_payload(
    countries: dict[str, dict[str, Any]],
    overrides: dict[str, Any],
    heuristic_codes: list[str],
) -> dict[str, Any]:
    country_items = []
    for country in countries.values():
        country_items.append(
            {
                "country_code": country["country_code"],
                "country_name": country["country_name"],
                "authorities": country["authorities"],
                "sources": country["sources"],
            }
        )
    return {
        "purpose": "Publish a conservative country-code feed for coarse GeoIP blocking.",
        "non_goals": [
            "Do not treat targeted individual/entity sanctions as enough, by themselves, to block a whole country.",
            "Do not treat nationality or address fields on listed persons as enough, by themselves, to block a whole country.",
            "Prefer false negatives over false positives.",
        ],
        "heuristic_baseline_country_codes": heuristic_codes,
        "manual_include_country_codes": overrides["manual_include_country_codes"],
        "manual_exclude_country_codes": overrides["manual_exclude_country_codes"],
        "notes_by_country_code": overrides["notes_by_country_code"],
        "countries": country_items,
    }


def call_openai_curation(payload: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENAI_MODEL") or "gpt-5-mini"
    request_body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are reviewing public sanctions evidence to recommend a conservative "
                            "country-code list for coarse GeoIP blocking. Your job is not to produce a "
                            "compliance list of every sanctioned jurisdiction. Instead, only recommend "
                            "country codes when the evidence suggests country-level blocking is a defensible "
                            "operational control. Use only the provided evidence. Do not invent sources. "
                            "Do not output codes absent from the evidence. Respect explicit manual include "
                            "and exclude overrides as policy signals."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(payload, ensure_ascii=True),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "sanctions_geoip_curation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "recommended_country_codes": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "pattern": "^[A-Z]{2}$",
                            },
                        },
                        "needs_human_review": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "country_reviews": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "country_code": {
                                        "type": "string",
                                        "pattern": "^[A-Z]{2}$",
                                    },
                                    "decision": {
                                        "type": "string",
                                        "enum": ["block", "do_not_block", "manual_review"],
                                    },
                                    "confidence": {
                                        "type": "string",
                                        "enum": ["low", "medium", "high"],
                                    },
                                    "reason": {"type": "string"},
                                    "supporting_authorities": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": [
                                    "country_code",
                                    "decision",
                                    "confidence",
                                    "reason",
                                    "supporting_authorities",
                                ],
                            },
                        },
                    },
                    "required": [
                        "recommended_country_codes",
                        "needs_human_review",
                        "summary",
                        "country_reviews",
                    ],
                },
            }
        },
    }

    raw = json.dumps(request_body).encode("utf-8")
    request = Request(
        "https://api.openai.com/v1/responses",
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = ""
        try:
            body = exc.read().decode("utf-8", "replace").strip()
            if body:
                detail = f" | body: {body}"
        except Exception:
            pass
        raise BuildError(f"OpenAI curation request failed: {exc}{detail}") from exc
    except URLError as exc:
        raise BuildError(f"OpenAI curation request failed: {exc}") from exc

    text = extract_response_text(payload)
    if not text:
        raise BuildError("OpenAI curation response did not include structured text output")
    return json.loads(text)


def extract_response_text(response_json: dict[str, Any]) -> str:
    if isinstance(response_json.get("output_text"), str) and response_json["output_text"].strip():
        return response_json["output_text"].strip()

    for item in response_json.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def validate_ai_output(ai_output: dict[str, Any], allowed_codes: set[str]) -> dict[str, Any]:
    recommended = {
        code.strip().upper() for code in ai_output.get("recommended_country_codes", []) if code
    }
    invalid = sorted(recommended - allowed_codes)
    if invalid:
        raise BuildError(f"OpenAI recommended unsupported country codes: {', '.join(invalid)}")

    ai_output["recommended_country_codes"] = sorted(recommended)
    return ai_output


def build_outputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    overrides = load_overrides()
    ofac_hits, ofac_metadata = parse_ofac_hits()
    eu_hits, eu_metadata = parse_eu_hits()
    uk_hits, uk_metadata = parse_uk_hits()
    un_hits, un_metadata = parse_un_hits()

    all_hits = ofac_hits + eu_hits + uk_hits + un_hits
    countries = build_country_evidence(all_hits)
    source_union = sorted(countries.keys())
    invalid_manual_includes = sorted(
        code for code in overrides["manual_include_country_codes"] if code not in source_union
    )
    if invalid_manual_includes:
        raise BuildError(
            "manual_include_country_codes contains codes not supported by current source evidence: "
            + ", ".join(invalid_manual_includes)
        )
    scorecards = compute_country_scores(countries)
    heuristic_codes = sorted(
        code for code, scorecard in scorecards.items() if scorecard["recommended_by_heuristic"]
    )

    ai_mode = "disabled"
    ai_output: dict[str, Any] | None = None
    ai_error: str | None = None
    ai_model = os.getenv("OPENAI_MODEL") or "gpt-5-mini"
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        ai_mode = "openai"
        try:
            ai_payload = build_openai_payload(countries, overrides, heuristic_codes)
            ai_output = validate_ai_output(call_openai_curation(ai_payload) or {}, set(source_union))
        except BuildError as exc:
            ai_mode = "fallback"
            ai_error = str(exc)
            ai_output = None
    else:
        ai_mode = "heuristic"
        ai_error = "OPENAI_API_KEY was not present at runtime, so AI review was skipped."

    ai_recommended_codes = sorted(ai_output.get("recommended_country_codes", [])) if ai_output else []
    effective_codes = set(heuristic_codes)
    effective_codes.update(overrides["manual_include_country_codes"])
    effective_codes.difference_update(overrides["manual_exclude_country_codes"])
    effective_codes = sorted(code for code in effective_codes if code in source_union)

    for code in overrides["manual_exclude_country_codes"]:
        if code in effective_codes:
            effective_codes.remove(code)

    generated_at = now_iso()
    sanctions_payload = {
        "generated_at": generated_at,
        "disclaimer": DISCLAIMER,
        "sanctioned_country_codes": source_union,
        "heuristic_recommended_country_codes": heuristic_codes,
        "ai_recommended_country_codes": ai_recommended_codes,
        "effective_geoip_block_country_codes": effective_codes,
        "manual_include_country_codes": overrides["manual_include_country_codes"],
        "manual_exclude_country_codes": overrides["manual_exclude_country_codes"],
        "supporting_sources": [
            {"authority": "OFAC", "url": OFAC_SANCTIONS_SEARCH_URL, "notes": "Entity-oriented reference UI"},
        ],
        "sources": {
            "OFAC": ofac_metadata,
            "EU": eu_metadata,
            "UK": uk_metadata,
            "UN": un_metadata,
        },
        "heuristic": {
            "threshold": HEURISTIC_THRESHOLD,
            "rules": HEURISTIC_RULES,
        },
        "countries": list(countries.values()),
    }

    evidence_payload = {
        "generated_at": generated_at,
        "disclaimer": DISCLAIMER,
        "curation": {
            "mode": ai_mode,
            "model": ai_model,
            "heuristic_baseline_country_codes": heuristic_codes,
            "ai_recommended_country_codes": ai_recommended_codes,
            "heuristic_threshold": HEURISTIC_THRESHOLD,
            "heuristic_rules": HEURISTIC_RULES,
            "manual_include_country_codes": overrides["manual_include_country_codes"],
            "manual_exclude_country_codes": overrides["manual_exclude_country_codes"],
            "notes_by_country_code": overrides["notes_by_country_code"],
            "ai_summary": ai_output.get("summary") if ai_output else None,
            "ai_needs_human_review": ai_output.get("needs_human_review") if ai_output else None,
            "ai_country_reviews": ai_output.get("country_reviews", []) if ai_output else [],
            "ai_error": ai_error,
        },
        "countries": list(countries.values()),
        "scores": [scorecards[code] for code in sorted(scorecards.keys())],
    }

    countries_payload = {
        "generated_at": generated_at,
        "heuristic_recommended_country_codes": heuristic_codes,
        "ai_recommended_country_codes": ai_recommended_codes,
        "effective_geoip_block_country_codes": effective_codes,
        "sanctioned_country_codes": source_union,
        "heuristic_threshold": HEURISTIC_THRESHOLD,
        "disclaimer": DISCLAIMER,
    }
    return sanctions_payload, evidence_payload, countries_payload


def render_index(payload: dict[str, Any], evidence_payload: dict[str, Any]) -> str:
    effective_codes = payload["effective_geoip_block_country_codes"]
    effective_code_list = ", ".join(effective_codes) if effective_codes else "None"

    rows = []
    score_lookup = {
        item["country_code"]: item for item in evidence_payload.get("scores", [])
    }
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

    ai_mode = evidence_payload["curation"]["mode"]
    ai_error = evidence_payload["curation"].get("ai_error")
    ai_model = evidence_payload["curation"].get("model", "unknown")
    ai_summary = evidence_payload["curation"].get("ai_summary")
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
    <title>Sanctions GeoIP Feed</title>
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
      .codes {{
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 1.1rem;
        color: var(--accent);
      }}
      a {{
        color: var(--accent);
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
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
      <h1>Sanctions GeoIP Feed</h1>
      <p>
        Static JSON for country-code-oriented GeoIP blocking, refreshed from OFAC, EU, UK, and UN
        sanctions sources.
      </p>

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
        <h2>Disclaimer</h2>
        <p>{escape(payload['disclaimer'])}</p>
      </section>

      <section class="panel">
        <h2>Curation</h2>
        <p class="small"><strong>Mode:</strong> {escape(ai_mode)}</p>
        <p class="small"><strong>Model:</strong> {escape(ai_model)}</p>
        <p class="small"><strong>Heuristic threshold:</strong> {HEURISTIC_THRESHOLD}</p>
        <p>{escape(ai_summary)}</p>
      </section>

      <section class="panel">
        <h2>Countries</h2>
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Authorities</th>
              <th>Score</th>
              <th>Blocked</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </section>
    </main>
  </body>
</html>
"""


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    sanctions_payload, evidence_payload, countries_payload = build_outputs()
    write_json(DOCS_DIR / "sanctions.json", sanctions_payload)
    write_json(DOCS_DIR / "evidence.json", evidence_payload)
    write_json(DOCS_DIR / "countries.json", countries_payload)
    (DOCS_DIR / "index.html").write_text(render_index(sanctions_payload, evidence_payload))

    print(
        "AI curation mode:",
        evidence_payload["curation"]["mode"],
        "| model:",
        evidence_payload["curation"]["model"],
    )
    if evidence_payload["curation"].get("ai_error"):
        print("AI curation detail:", evidence_payload["curation"]["ai_error"])
    print(f"Wrote {DOCS_DIR / 'countries.json'}")
    print(f"Wrote {DOCS_DIR / 'sanctions.json'}")
    print(f"Wrote {DOCS_DIR / 'evidence.json'}")
    print(f"Wrote {DOCS_DIR / 'index.html'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
