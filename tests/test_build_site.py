from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_site  # noqa: E402
from render_site import render_index  # noqa: E402


class ConfigurationTests(unittest.TestCase):
    def test_default_model_has_single_named_source(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                build_site.configured_openai_model(),
                build_site.DEFAULT_OPENAI_MODEL,
            )

    def test_model_environment_override_is_trimmed(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MODEL": " custom-model "}, clear=True):
            self.assertEqual(build_site.configured_openai_model(), "custom-model")

    def test_overrides_reject_conflicting_codes(self) -> None:
        data = {
            "manual_include_country_codes": ["RU"],
            "manual_exclude_country_codes": ["ru"],
            "notes_by_country_code": {},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "overrides.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(build_site, "OVERRIDES_PATH", path):
                with self.assertRaisesRegex(build_site.BuildError, "both included and excluded"):
                    build_site.load_overrides()

    def test_overrides_reject_invalid_country_codes(self) -> None:
        data = {
            "manual_include_country_codes": ["RUS"],
            "manual_exclude_country_codes": [],
            "notes_by_country_code": {},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "overrides.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(build_site, "OVERRIDES_PATH", path):
                with self.assertRaisesRegex(build_site.BuildError, "invalid ISO alpha-2"):
                    build_site.load_overrides()


class CurationTests(unittest.TestCase):
    def test_fetch_retries_transient_network_errors(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        with patch.object(
            build_site,
            "urlopen",
            side_effect=[URLError("temporary failure"), response],
        ) as mocked_urlopen, patch.object(build_site.time, "sleep") as mocked_sleep:
            self.assertEqual(build_site.fetch_bytes("https://example.com"), b"ok")

        self.assertEqual(mocked_urlopen.call_count, 2)
        mocked_sleep.assert_called_once_with(1)

    def test_openai_http_error_does_not_publish_response_body(self) -> None:
        error = HTTPError(
            "https://api.openai.com/v1/responses",
            401,
            "Unauthorized",
            {},
            BytesIO(b'{"error":"sensitive provider detail"}'),
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only"}, clear=True), patch.object(
            build_site, "urlopen", side_effect=error
        ):
            with self.assertRaises(build_site.BuildError) as raised:
                build_site.call_openai_curation({})

        message = str(raised.exception)
        self.assertIn("HTTP 401", message)
        self.assertNotIn("sensitive provider detail", message)

    def test_empty_source_is_a_hard_failure(self) -> None:
        with self.assertRaisesRegex(build_site.BuildError, "EU"):
            build_site.validate_source_hits(
                {
                    "OFAC": [
                        build_site.SourceHit(
                            authority="OFAC",
                            title="Cuba Sanctions",
                            url="https://example.com",
                        )
                    ],
                    "EU": [],
                }
            )

    def test_ai_output_cannot_add_unsupported_country_codes(self) -> None:
        with self.assertRaisesRegex(build_site.BuildError, "unsupported country codes"):
            build_site.validate_ai_output(
                {"recommended_country_codes": ["CU", "ZZ"]},
                {"CU"},
            )

    def test_build_outputs_include_version_and_keep_ai_advisory(self) -> None:
        source_results = {
            "parse_ofac_hits": (
                [
                    build_site.SourceHit(
                        authority="OFAC",
                        title="Iran Sanctions",
                        url="https://example.com/ofac",
                    )
                ],
                {},
            ),
            "parse_eu_hits": (
                [
                    build_site.SourceHit(
                        authority="EU",
                        title="EU sanctions regime IRN",
                        url="https://example.com/eu",
                    )
                ],
                {},
            ),
            "parse_uk_hits": (
                [
                    build_site.SourceHit(
                        authority="UK",
                        title="The Iran (Sanctions) Regulations 2023",
                        url="https://example.com/uk",
                    )
                ],
                {},
            ),
            "parse_un_hits": (
                [
                    build_site.SourceHit(
                        authority="UN",
                        title="1737 Committee (Iran)",
                        url="https://example.com/un",
                    )
                ],
                {},
            ),
        }
        overrides = {
            "manual_include_country_codes": [],
            "manual_exclude_country_codes": [],
            "notes_by_country_code": {},
        }
        patches = [
            patch.object(build_site, name, return_value=result)
            for name, result in source_results.items()
        ]
        with patch.object(build_site, "load_overrides", return_value=overrides), patch.dict(
            os.environ, {}, clear=True
        ):
            for active_patch in patches:
                active_patch.start()
            try:
                sanctions, evidence, countries = build_site.build_outputs()
            finally:
                for active_patch in patches:
                    active_patch.stop()

        self.assertEqual(sanctions["schema_version"], build_site.SCHEMA_VERSION)
        self.assertEqual(evidence["curation"]["mode"], "heuristic")
        self.assertEqual(evidence["curation"]["ai_recommended_country_codes"], [])
        self.assertEqual(countries["effective_geoip_block_country_codes"], ["IR"])


class RenderingTests(unittest.TestCase):
    def test_renderer_escapes_model_and_has_accessible_table_headers(self) -> None:
        payload = {
            "generated_at": "2026-07-23T12:00:00Z",
            "disclaimer": "Not legal advice.",
            "effective_geoip_block_country_codes": ["IR"],
            "countries": [
                {
                    "country_code": "IR",
                    "country_name": "Iran",
                    "authorities": ["OFAC"],
                }
            ],
        }
        evidence = {
            "curation": {
                "mode": "openai",
                "model": "<unsafe>",
                "ai_summary": "Reviewed.",
                "ai_error": None,
            },
            "scores": [{"country_code": "IR", "score": 5}],
        }

        rendered = render_index(payload, evidence, 5)

        self.assertIn("&lt;unsafe&gt;", rendered)
        self.assertNotIn("<unsafe>", rendered)
        self.assertIn("Limitations / Not legal advice", rendered)
        self.assertIn("not sanctions compliance automation", rendered)
        self.assertIn('<th scope="col">Code</th>', rendered)
        self.assertIn("<caption>", rendered)


if __name__ == "__main__":
    unittest.main()
