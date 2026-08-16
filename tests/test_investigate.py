import unittest
from unittest.mock import patch

from Core.Support.Investigate import (
    _fallback_dossier,
    _search_angles,
    classify_target,
    handle_candidates,
    looks_like_same_person,
    official_links,
    plan_holmes_tools,
    run_name_investigation,
)
from Core.Support.Robin import llm_bridge


class ClassifyTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify_target(""), "empty")
        self.assertEqual(classify_target("ana@exemplo.com"), "email")
        self.assertEqual(classify_target("joaosilva"), "username")
        self.assertEqual(classify_target("exemplo.com"), "domain")
        self.assertEqual(classify_target("Maria Silva"), "person")
        self.assertEqual(classify_target("+5511999999999"), "phone")


class NamesakeTests(unittest.TestCase):
    def test_discards_first_name_only(self):
        query = "Thiago Augusto Pinto Gomes"
        self.assertFalse(looks_like_same_person("Thiago Ferreira", query))
        self.assertFalse(looks_like_same_person("codethi", query))
        self.assertTrue(looks_like_same_person("Thiago Augusto Pinto Gomes", query))


class HolmesPlanTests(unittest.TestCase):
    def test_person_handles_from_full_name(self):
        cands = handle_candidates("Thiago Augusto Pinto Gomes")
        self.assertIn("thiagogomes", cands)
        self.assertTrue(any("." in c for c in cands) or len(cands) >= 1)

    @patch("Core.Support.Investigate._holmes_available", return_value={"maigret": True, "holehe": True})
    def test_person_plan_includes_maigret(self, _avail):
        labels = " ".join(step["label"] for step in plan_holmes_tools("Thiago Augusto Pinto Gomes", "person"))
        self.assertIn("Maigret", labels)

    @patch("Core.Support.Investigate._holmes_available", return_value={"holehe": True})
    def test_email_plan_includes_holehe(self, _avail):
        ids = [step["id"] for step in plan_holmes_tools("ana@exemplo.com", "email")]
        self.assertIn("holehe", ids)
        self.assertIn("email_holmes", ids)
    def test_angles_forbid_user_homework(self):
        blob = " ".join(p for _, p in _search_angles("Maria Silva", "person")).lower()
        self.assertIn("não diga ao usuário para procurar", blob)
        self.assertGreaterEqual(len(_search_angles("Maria Silva", "person")), 2)


class LinksTests(unittest.TestCase):
    def test_email_includes_hibp(self):
        urls = " ".join(item["url"] for item in official_links("ana@exemplo.com", "email"))
        self.assertIn("haveibeenpwned.com", urls)


class FallbackTests(unittest.TestCase):
    def test_fallback_mentions_query(self):
        text = _fallback_dossier(
            "joaosilva",
            "username",
            {"github": {"users": [{"login": "joaosilva", "url": "https://github.com/joaosilva"}]}},
        )
        self.assertIn("joaosilva", text)
        self.assertIn("github.com/joaosilva", text)
        self.assertNotIn("Use os atalhos oficiais", text)


class InvestigateRunTests(unittest.TestCase):
    def test_empty_query(self):
        result = run_name_investigation("  ")
        self.assertFalse(result["ok"])

    @patch("Core.Support.Investigate._holmes_available", return_value={})
    @patch("Core.Support.Investigate.llm_bridge.chat")
    @patch("Core.Support.Investigate.llm_bridge.openai_web_search")
    @patch("Core.Support.Investigate._wikipedia")
    @patch("Core.Support.Investigate._github_users")
    def test_person_uses_web_search_and_returns_dossier(self, gh, wiki, web, chat, _avail):
        wiki.return_value = {"ok": False, "hits": []}
        gh.return_value = {"ok": False, "users": []}
        web.return_value = {
            "ok": True,
            "text": "LinkedIn: não encontrado nesta busca. GitHub: não encontrado nesta busca.",
            "citations": [],
            "error": None,
        }
        chat.return_value = (
            "## Resumo\nAda Lovelace, matemática.\n"
            "## Presença pública\nWikipedia confirmada.\n"
            "## Lacunas\nLinkedIn: não encontrado nesta busca."
        )
        result = run_name_investigation("Ada Lovelace", model="gpt-4o")
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "person")
        self.assertIn("Ada Lovelace", result["dossier"])
        self.assertTrue(result["web_ok"])
        self.assertGreaterEqual(web.call_count, 2)
        self.assertEqual(result.get("links") or [], [])
        self.assertNotIn("procure no", result["dossier"].lower())
        self.assertTrue(any("GitHub" in t or "Wikipedia" in t for t in result.get("tools_used") or []))
        chat.assert_called_once()


class WebSearchHelperTests(unittest.TestCase):
    def test_web_search_without_key(self):
        with patch.object(llm_bridge, "_clean", return_value=None):
            out = llm_bridge.openai_web_search("teste")
        self.assertFalse(out["ok"])
        self.assertIn("OPENAI_API_KEY", out["error"])


if __name__ == "__main__":
    unittest.main()
