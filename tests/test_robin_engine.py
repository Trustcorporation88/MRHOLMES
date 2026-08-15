import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Core.Support.Robin.engine import (
    _fallback_summary,
    _filter_results,
    _refine_query,
    run_investigation,
)
from Core.Support.Robin.llm_bridge import apply_keys, list_models
from Core.Support.Robin.search import ensure_tor, extract_onion_results, tor_proxy_up


AHMIA_HTML = """
<html><body>
<a href="http://abcdefghijklmnopqrstuvwxyz012345.onion/thread">Forum leak thread</a>
<a href="/search?q=test">search self</a>
<a href="http://abcdefghijklmnopqrstuvwxyz012345.onion/thread">dup</a>
<a href="https://example.com">clear</a>
</body></html>
"""


class RobinKeyTests(unittest.TestCase):
    def test_apply_keys_unlocks_openai_and_claude(self):
        import os

        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        apply_keys(openai="sk-test-openai", anthropic="sk-ant-test")
        ids = {m["id"] for m in list_models()}
        self.assertIn("gpt-4o-mini", ids)
        self.assertIn("claude-sonnet-4-5", ids)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("CLAUDE_API_KEY", None)


class RobinSearchTests(unittest.TestCase):
    def test_ensure_tor_without_binary_is_false_or_already_up(self):
        up = tor_proxy_up()
        result = ensure_tor(wait_seconds=0.2)
        if up:
            self.assertTrue(result)
        else:
            self.assertIsInstance(result, bool)

    def test_extract_onion_results(self):
        hits = extract_onion_results(AHMIA_HTML)
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0]["link"].endswith(".onion/thread"))
        self.assertIn("Forum", hits[0]["title"])


class RobinEngineTests(unittest.TestCase):
    def test_refine_without_llm_keeps_keywords(self):
        refined = _refine_query(None, "vazamento de credenciais exemplo.com 2024")
        self.assertTrue(refined)
        self.assertLessEqual(len(refined.split()), 6)

    def test_filter_without_llm_caps(self):
        results = [{"title": f"t{i}", "link": f"http://x{i}.onion"} for i in range(12)]
        picked = _filter_results(None, "q", results, 4)
        self.assertEqual(len(picked), 4)

    def test_fallback_summary_lists_sources(self):
        text = _fallback_summary(
            "teste",
            [{"title": "A", "link": "http://aaa.onion"}],
            {"http://aaa.onion": "A - hello world"},
        )
        self.assertIn("## Input Query", text)
        self.assertIn("http://aaa.onion", text)
        self.assertIn("hello world", text)

    @patch("Core.Support.Robin.engine.scrape_multiple", return_value={})
    @patch("Core.Support.Robin.engine.get_search_results")
    def test_run_investigation_saves_json(self, mock_search, _mock_scrape):
        mock_search.return_value = {
            "results": [{"title": "Hit", "link": "http://bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.onion/x"}],
            "via_tor": False,
            "via_clearnet": True,
            "engines": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch("Core.Support.Robin.engine.INVESTIGATIONS_DIR", Path(tmp)):
                result = run_investigation("caso educacional autorizado", model=None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["results_count"], 1)
        self.assertTrue(result["summary"])
        self.assertTrue(result["filename"].startswith("investigation_"))


if __name__ == "__main__":
    unittest.main()
