import unittest
from pathlib import Path

from osint_premium import (
    FEATURED,
    NATIVE_SUITES,
    PLAYBOOKS,
    apply_pending_navigation,
    premium_stats,
    queue_navigation,
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
        self.assertTrue(any(item["id"] == "robin" for item in hits))

    def test_flowsint_and_arsenal_are_featured(self):
        ids = {item["id"] for item in FEATURED}
        self.assertIn("flowsint", ids)
        self.assertIn("arsenal", ids)
        self.assertIn("robin", ids)

    def test_flowsint_playbook_maps_to_holmes(self):
        book = next(item for item in PLAYBOOKS if item["id"] == "flowsint")
        pages = {step.get("page") for step in book["steps"] if step.get("kind") == "native"}
        self.assertIn("Gráfico", pages)
        self.assertIn("OSINT Avançado", pages)
        self.assertTrue(any(step.get("url", "").startswith("https://github.com/reconurge/flowsint") for step in book["steps"]))

    def test_catalog_includes_flowsint(self):
        hits = search_catalog("flowsint", "flowsint")
        self.assertTrue(any(item.get("id") == "flowsint" for item in hits))

    def test_catalog_includes_arsenal_osint_only(self):
        hits = search_catalog("blackbird", "arsenal")
        self.assertTrue(any(item.get("id") == "blackbird" for item in hits))
        blob = " ".join(f"{h.get('name')} {h.get('description')}" for h in search_catalog("", "arsenal")).lower()
        self.assertNotIn("mimikatz", blob)
        self.assertNotIn("phishing", blob)

    def test_playbook_pessoa_opens_whatsmyname(self):
        book = next(item for item in PLAYBOOKS if item["id"] == "pessoa")
        self.assertTrue(any(step.get("osint_tool") == "whatsmyname" for step in book["steps"]))

    def test_osintleak_featured_is_native_leaks_page(self):
        item = next(x for x in FEATURED if x["id"] == "osintleak")
        self.assertEqual(item.get("native_page"), "Leaks")
        self.assertIn("OSINTLEAK_API_KEY", item.get("requires", ""))

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


NAV = ["OSINT Premium", "Telefone", "OSINT Avançado", "Gráfico"]


class PendingNavigationTests(unittest.TestCase):
    def test_queue_does_not_write_nav_page(self):
        session = {"nav_page": "OSINT Premium"}
        queue_navigation(session, "OSINT Avançado", osint_tool="maigret")
        self.assertEqual(session["nav_page"], "OSINT Premium")
        self.assertEqual(session["_pending_nav"], "OSINT Avançado")
        self.assertEqual(session["_pending_osint_tool"], "maigret")

    def test_apply_moves_to_maigret_module(self):
        session = {
            "nav_page": "OSINT Premium",
            "_pending_nav": "OSINT Avançado",
            "_pending_osint_tool": "maigret",
        }
        apply_pending_navigation(session, NAV)
        self.assertEqual(session["nav_page"], "OSINT Avançado")
        self.assertEqual(session["osint_adv_tool"], "maigret")
        self.assertNotIn("_pending_nav", session)
        self.assertNotIn("_pending_osint_tool", session)

    def test_apply_opens_robin_without_leaving_premium(self):
        session = {
            "nav_page": "OSINT Premium",
            "_pending_nav": "OSINT Premium",
            "_pending_premium_view": "robin",
        }
        apply_pending_navigation(session, NAV)
        self.assertEqual(session["nav_page"], "OSINT Premium")
        self.assertEqual(session["premium_view"], "robin")
        self.assertNotIn("_pending_premium_view", session)

    def test_unknown_pending_page_is_ignored(self):
        session = {"nav_page": "Telefone", "_pending_nav": "Nope"}
        apply_pending_navigation(session, NAV)
        self.assertEqual(session["nav_page"], "Telefone")

    def test_default_when_nav_missing(self):
        session = {}
        apply_pending_navigation(session, NAV)
        self.assertEqual(session["nav_page"], "Telefone")


class RobinQueryFieldTests(unittest.TestCase):
    def test_name_field_sits_above_options(self):
        src = Path("robin_workspace.py").read_text(encoding="utf-8")
        body = src[src.index("def display_robin_workspace") :]
        self.assertIn("Nome, username ou query", body)
        self.assertLess(body.index("Nome, username ou query"), body.index("_robin_options("))


if __name__ == "__main__":
    unittest.main()
