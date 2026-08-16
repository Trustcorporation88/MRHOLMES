import unittest
from unittest.mock import patch

from Core.Support.Investigate import classify_target, official_links, run_name_investigation, _fallback_dossier
from Core.Support.Robin import llm_bridge


class ClassifyTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify_target(""), "empty")
        self.assertEqual(classify_target("ana@exemplo.com"), "email")
        self.assertEqual(classify_target("joaosilva"), "username")
        self.assertEqual(classify_target("exemplo.com"), "domain")
        self.assertEqual(classify_target("Maria Silva"), "person")
        self.assertEqual(classify_target("+5511999999999"), "phone")


class LinksTests(unittest.TestCase):
    def test_email_includes_hibp(self):
        urls = " ".join(item["url"] for item in official_links("ana@exemplo.com", "email"))
        self.assertIn("haveibeenpwned.com", urls)

    def test_person_includes_opencorporates(self):
        names = [item["name"] for item in official_links("Maria Silva", "person")]
        self.assertIn("OpenCorporates", names)


class FallbackTests(unittest.TestCase):
    def test_fallback_mentions_query(self):
        text = _fallback_dossier("joaosilva", "username", {"github": {"users": [{"login": "joaosilva", "url": "https://github.com/joaosilva"}]}})
        self.assertIn("joaosilva", text)
        self.assertIn("github.com/joaosilva", text)


class InvestigateRunTests(unittest.TestCase):
    def test_empty_query(self):
        result = run_name_investigation("  ")
        self.assertFalse(result["ok"])

    @patch("Core.Support.Investigate.llm_bridge.openai_web_search")
    @patch("Core.Support.Investigate._wikipedia")
    @patch("Core.Support.Investigate._github_users")
    @patch("Core.Support.Investigate._ddg")
    def test_person_uses_web_search(self, ddg, gh, wiki, web):
        wiki.return_value = {"ok": True, "hits": [{"title": "Ada", "desc": "math", "url": "https://en.wikipedia.org/wiki/Ada"}]}
        gh.return_value = {"ok": False, "users": []}
        ddg.return_value = {"ok": False}
        web.return_value = {"ok": True, "text": "## Resumo\nAda Lovelace", "citations": [{"title": "Wiki", "url": "https://en.wikipedia.org/wiki/Ada"}], "error": None}
        result = run_name_investigation("Ada Lovelace", model="gpt-4o-mini")
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "person")
        self.assertIn("Ada Lovelace", result["dossier"])
        self.assertTrue(result["web_ok"])
        web.assert_called_once()


class WebSearchHelperTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=False)
    def test_web_search_without_key(self):
        with patch.object(llm_bridge, "_clean", return_value=None):
            out = llm_bridge.openai_web_search("teste")
        self.assertFalse(out["ok"])
        self.assertIn("OPENAI_API_KEY", out["error"])


if __name__ == "__main__":
    unittest.main()
