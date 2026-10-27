import http.client
import os
import sys
import threading
import unittest
import http.server

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "proto-to-phone", "scripts"))
import adapt  # noqa: E402
import android_lib as al  # noqa: E402
import serve  # noqa: E402


class ServeTest(unittest.TestCase):
    """The web server only hands out the three files, only under the secret path,
    only for GET/HEAD, and never prints the secret."""

    def setUp(self):
        self.lines = []
        files = {"index.html": (b"<html>page</html>", "text/html; charset=utf-8"),
                 "manifest.webmanifest": (b"{}", "application/manifest+json"),
                 "icon.png": (b"\x89PNG", "image/png")}
        self.token = "SECRETtoken123"
        handler = serve.make_handler(self.token, files, self.lines.append)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def get(self, path, method="GET"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request(method, path)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, body, r

    def test_serves_the_page_under_the_secret_path(self):
        status, body, r = self.get("/%s/" % self.token)
        self.assertEqual((status, body), (200, b"<html>page</html>"))
        self.assertEqual(r.getheader("Cache-Control"), "no-store")
        self.assertEqual(r.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(self.get("/%s/icon.png" % self.token)[0], 200)
        self.assertEqual(self.get("/%s" % self.token)[0], 301)

    def test_everything_else_is_refused(self):
        for path in ("/", "/index.html", "/wrong/", "/%s/../index.html" % self.token,
                     "/%s/phone.config.json" % self.token, "/%s/.proto-phone.json" % self.token,
                     "/%s/%%2e%%2e/etc/passwd" % self.token):
            self.assertEqual(self.get(path)[0], 404, path)
        self.assertEqual(self.get("/%s/" % self.token, "POST")[0], 405)

    def test_secret_is_not_logged(self):
        self.get("/%s/" % self.token)
        self.assertTrue(self.lines)
        self.assertFalse(any(self.token in line for line in self.lines))

    def test_manifest(self):
        import json
        m = json.loads(serve.manifest("My App"))
        self.assertEqual((m["display"], m["start_url"], m["icons"][0]["src"]), ("standalone", "./", "icon.png"))


class WebAdaptTest(unittest.TestCase):
    def test_web_target(self):
        html = "<html><head></head><body><div id='d'></div></body></html>"
        out = adapt.adapt(html, {"frame": {"device": "#d"}}, target="web")
        self.assertIn('rel="manifest"', out)
        self.assertIn('"mode":"web"', out)
        self.assertIn("classList.add('app-shell');</script>", out)
        self.assertIn(":root.app-shell.kb-open #d{position:fixed", out)
        with self.assertRaises(adapt.AdaptError):
            adapt.adapt(html, {}, target="desktop")


class AndroidLibTest(unittest.TestCase):
    def test_application_id(self):
        self.assertEqual(al.android_id("phone.abc123.my-app"), "phone.abc123.my_app")
        self.assertEqual(al.android_id("local.protophone.9lives"), "local.protophone.a9lives")
        self.assertEqual(al.android_id("single"), "app.single")

    def test_string_resource_escaping(self):
        self.assertEqual(al.string_resource("Mi App's"), "Mi App\\'s")
        self.assertEqual(al.string_resource("@home"), "\\@home")
        self.assertEqual(al.string_resource("A <b> & \"c\""), "A &lt;b&gt; &amp; \\\"c\\\"")

    def test_parse_devices(self):
        out = al.parse_devices("List of devices attached\n"
                               "emulator-5554 device product:sdk model:sdk_gphone64 device:emu\n"
                               "R58N123 unauthorized usb:1-1\n\n")
        self.assertEqual([d["serial"] for d in out], ["emulator-5554", "R58N123"])
        self.assertTrue(out[0]["emulator"])
        self.assertEqual(out[1]["state"], "unauthorized")

    def test_android_template_has_safe_settings(self):
        root = os.path.join(os.path.dirname(__file__), "..", "skills", "proto-to-phone", "template-android")
        kt = open(os.path.join(root, "app", "src", "main", "java", "app", "protophone", "shell", "MainActivity.kt")).read()
        manifest = open(os.path.join(root, "app", "src", "main", "AndroidManifest.xml")).read()
        for needle in ("allowFileAccess = false", "allowContentAccess = false", "MIXED_CONTENT_NEVER_ALLOW",
                       'setOf("https://$ASSET_HOST")', "request.hasGesture()", "BuildConfig.DEBUG"):
            self.assertIn(needle, kt)
        self.assertIn('android:usesCleartextTraffic="false"', manifest)
        self.assertIn('android:allowBackup="false"', manifest)
        self.assertNotIn("addJavascriptInterface", kt)


if __name__ == "__main__":
    unittest.main()
