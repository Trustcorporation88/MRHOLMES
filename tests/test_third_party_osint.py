import unittest
from unittest.mock import patch

from Core.Support.OsintLeak import redact_record, search as ol_search
from Core.Support.WhatsMyName import check_username, selectable_sites
from external_services import get_all_services_flat


class WhatsMyNameTests(unittest.TestCase):
    def test_skips_captcha_nsfw_and_prefers_social(self):
        data = {
            "sites": [
                {
                    "name": "NSFW",
                    "uri_check": "https://x.example/{account}",
                    "e_code": 200,
                    "e_string": "ok",
                    "cat": "xx NSFW xx",
                },
                {
                    "name": "CaptchaSite",
                    "uri_check": "https://cap.example/{account}",
                    "e_code": 200,
                    "e_string": "ok",
                    "cat": "social",
                    "protection": ["captcha"],
                },
                {
                    "name": "GitHub",
                    "uri_check": "https://github.com/{account}",
                    "uri_pretty": "https://github.com/{account}",
                    "e_code": 200,
                    "e_string": "ok-profile",
                    "m_code": 404,
                    "cat": "coding",
                },
                {
                    "name": "Shop",
                    "uri_check": "https://shop.example/{account}",
                    "e_code": 200,
                    "e_string": "ok",
                    "cat": "shopping",
                },
            ]
        }
        sites = selectable_sites(data, max_sites=10)
        names = [s["name"] for s in sites]
        self.assertEqual(names[0], "GitHub")
        self.assertIn("Shop", names)
        self.assertNotIn("NSFW", names)
        self.assertNotIn("CaptchaSite", names)

    def test_check_username_uses_injected_list(self):
        data = {
            "sites": [
                {
                    "name": "Demo",
                    "uri_check": "https://demo.example/{account}",
                    "uri_pretty": "https://demo.example/{account}",
                    "e_code": 200,
                    "e_string": "profile-ok",
                    "m_string": "missing",
                    "m_code": 404,
                    "cat": "social",
                }
            ]
        }

        class _Resp:
            status_code = 200
            text = "hello profile-ok there"

        with patch("Core.Support.WhatsMyName.requests.get", return_value=_Resp()):
            out = check_username("joaosilva", data=data, max_sites=5, workers=1)
        self.assertTrue(out["ok"])
        self.assertEqual(out["profiles"][0]["site"], "Demo")
        self.assertIn("joaosilva", out["profiles"][0]["url"])
        self.assertEqual(out["source"], "WhatsMyName dataset")

    def test_rejects_bad_handle(self):
        out = check_username("a", data={"sites": []})
        self.assertFalse(out["ok"])


class OsintLeakTests(unittest.TestCase):
    def test_redacts_passwords(self):
        clean = redact_record(
            {
                "email": "ana@exemplo.com",
                "username": "ana",
                "password": "supersecret",
                "PasswordHash": "abc",
                "url": "https://example.com",
                "cookie": "sid=1",
            }
        )
        self.assertEqual(clean["email"], "ana@exemplo.com")
        self.assertEqual(clean["url"], "https://example.com")
        blob = " ".join(clean.keys()).lower()
        self.assertNotIn("password", blob)
        self.assertNotIn("cookie", blob)
        self.assertNotIn("hash", blob)

    def test_search_without_key(self):
        with patch.dict("os.environ", {"OSINTLEAK_API_KEY": ""}, clear=False):
            with patch("Core.Support.OsintLeak._key", return_value=""):
                out = ol_search("ana@exemplo.com", kind="email")
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("needs_key"))
        self.assertIn("OSINTLEAK_API_KEY", out["error"])

    def test_search_sends_official_params(self):
        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "status": "success",
                    "count": 1,
                    "results": [{"email": "ana@exemplo.com", "password": "nope", "source": "breach-a"}],
                }

        with patch("Core.Support.OsintLeak.requests.get", return_value=_Resp()) as get:
            out = ol_search("ana@exemplo.com", kind="email", api_key="test-key")
        self.assertTrue(out["ok"])
        self.assertEqual(out["hits"][0]["email"], "ana@exemplo.com")
        self.assertNotIn("password", out["hits"][0])
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["stealerlogs"], "false")
        self.assertEqual(params["type"], "email")
        self.assertTrue(str(get.call_args.args[0]).endswith("/api/v1/search_api/"))

    def test_domain_maps_to_url_type(self):
        class _Resp:
            status_code = 200

            def json(self):
                return {"status": "success", "count": 0, "results": []}

        with patch("Core.Support.OsintLeak.requests.get", return_value=_Resp()) as get:
            ol_search("exemplo.com", kind="domain", api_key="test-key")
        self.assertEqual(get.call_args.kwargs["params"]["type"], "url")


class CatalogNativeTests(unittest.TestCase):
    def test_whatsmyname_and_osintleak_point_inside_holmes(self):
        items = {s["id"]: s for s in get_all_services_flat()}
        self.assertEqual(items["whatsmyname"].get("native_page"), "OSINT Avançado")
        self.assertEqual(items["whatsmyname"].get("osint_tool"), "whatsmyname")
        self.assertEqual(items["osintleak"].get("native_page"), "Leaks")
        self.assertIn("não raspa", items["truecaller"]["description"].lower())
        self.assertIn("holehe", items["epieos"]["description"].lower())


if __name__ == "__main__":
    unittest.main()
