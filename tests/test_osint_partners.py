import unittest

from osint_partners import (
    ARSENAL_BLOCKLIST,
    ARSENAL_PICKS,
    ARSENAL_URL,
    FLOWSINT_ENRICHERS,
    FLOWSINT_URL,
    arsenal_picks_are_clean,
)


class OsintPartnersTests(unittest.TestCase):
    def test_arsenal_picks_exclude_redteam(self):
        self.assertTrue(arsenal_picks_are_clean())
        blob = " ".join(
            f"{item['name']} {item['url']} {item['description']}" for item in ARSENAL_PICKS
        ).lower()
        tokens = set(blob.replace("/", " ").replace("-", " ").replace(".", " ").split())
        for word in ARSENAL_BLOCKLIST:
            self.assertNotIn(word, tokens)

    def test_arsenal_index_points_to_upstream(self):
        self.assertTrue(any(item["url"] == ARSENAL_URL for item in ARSENAL_PICKS))
        self.assertTrue(ARSENAL_URL.startswith("https://github.com/rawfilejson/awesome-osint-arsenal"))

    def test_flowsint_enrichers_have_actions(self):
        self.assertGreaterEqual(len(FLOWSINT_ENRICHERS), 6)
        for step in FLOWSINT_ENRICHERS:
            self.assertTrue(step.get("label"))
            if step["kind"] == "native":
                self.assertTrue(step.get("page"))
            elif step["kind"] == "external":
                self.assertTrue(str(step.get("url", "")).startswith("http"))
        self.assertEqual(FLOWSINT_ENRICHERS[-1]["url"], FLOWSINT_URL)


if __name__ == "__main__":
    unittest.main()
