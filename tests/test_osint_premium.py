import unittest

from osint_premium import (
    FEATURED,
    NATIVE_SUITES,
    PLAYBOOKS,
    premium_stats,
    search_catalog,
    search_featured,
    search_native,
)


class OsintPremiumCatalogTests(unittest.TestCase):
    def test_stats_are_positive(self):
        stats = premium_stats()
        self.assertGreaterEqual(stats["native"], 8)
        self.assertGreaterEqual(stats["featured"], 1)
        self.assertGreaterEqual(stats["playbooks"], 5)
        self.assertGreaterEqual(stats["catalog"], 1)

    def test_robin_is_in_app(self):
        robin = next(item for item in FEATURED if item["id"] == "robin")
        self.assertTrue(robin.get("in_app"))
        self.assertEqual(robin.get("premium_view"), "robin")
        self.assertTrue(robin["url"].startswith("https://github.com/apurvsinghgautam/robin"))
        self.assertTrue(any(item["id"] == "robin" for item in NATIVE_SUITES))

    def test_search_native_filters(self):
        hits = search_native("telefone")
        self.assertTrue(any(item["id"] == "telefone" for item in hits))
        self.assertFalse(any(item["id"] == "grafo" for item in hits))

    def test_search_featured_robin(self):
        hits = search_featured("robin")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], "robin")

    def test_playbooks_have_actionable_steps(self):
        for book in PLAYBOOKS:
            self.assertTrue(book["steps"])
            kinds = {step["kind"] for step in book["steps"]}
            self.assertTrue(kinds & {"native", "external", "note", "tool"})

    def test_darkweb_playbook_opens_tool(self):
        book = next(item for item in PLAYBOOKS if item["id"] == "darkweb")
        self.assertTrue(any(step.get("kind") == "tool" for step in book["steps"]))

    def test_native_pages_are_known(self):
        known = {item["page"] for item in NATIVE_SUITES}
        self.assertIn("Telefone", known)
        self.assertIn("OSINT Avançado", known)
        self.assertIn("Serviços Externos", known)
        self.assertIn("OSINT Premium", known)

    def test_catalog_includes_robin_category(self):
        hits = search_catalog("robin", "darkweb")
        self.assertTrue(any(item.get("id") == "robin" for item in hits))


if __name__ == "__main__":
    unittest.main()
