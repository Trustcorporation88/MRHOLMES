import unittest
from pathlib import Path


class ThemeCssTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("web_app.py").read_text(encoding="utf-8")

    def test_body_font_rule_does_not_target_span(self):
        self.assertNotIn("p, label, span, .stMarkdown", self.css)

    def test_expander_icon_font_is_restored(self):
        self.assertIn('[data-testid="stIconMaterial"]', self.css)
        self.assertIn("Material Symbols Rounded", self.css)


if __name__ == "__main__":
    unittest.main()
