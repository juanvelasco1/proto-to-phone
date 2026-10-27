import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "proto-to-phone", "scripts"))
import scan  # noqa: E402

PROTO = """<html><head><style>
.device{width:390px;position:relative}
.statusbar{height:54px}
.tabbar{position:absolute;left:0;right:0;bottom:0}
.dot{position:absolute;bottom:3px}
.row::before{position:absolute;bottom:0}
.fake-keyboard{position:absolute;bottom:0}
input{font-size:14px}
body{height:100vh}
</style></head><body>
<div class="canvas"><div id="device" class="device"><div class="statusbar"></div>
<div class="fake-keyboard"></div><img src="logo.png"><a href="http://x.example/a">x</a></div></div>
<script>function showKeyboard(){} function hideKeyboard(){} localStorage.setItem('a','b');</script>
</body></html>"""


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.r = scan.scan(PROTO)

    def test_finds_mockup_chrome(self):
        kinds = self.r["mockup_chrome"]
        self.assertIn("statusbar", kinds)
        self.assertIn("keyboard", kinds)
        self.assertIn("frame", kinds)
        self.assertIn("canvas", kinds)

    def test_fixed_width_frame(self):
        self.assertEqual(self.r["fixed_width_frames"][0]["width"], "390px")

    def test_bottom_anchored_ignores_nudges_and_pseudo_elements(self):
        sels = [b["selector"] for b in self.r["bottom_anchored"]]
        self.assertIn(".tabbar", sels)
        self.assertNotIn(".dot", sels)
        self.assertNotIn(".row::before", sels)

    def test_inputs_and_viewport(self):
        self.assertEqual(self.r["inputs_under_16px"][0]["font_size"], "14px")
        self.assertIsNone(self.r["viewport"])
        self.assertEqual(self.r["uses_100vh"], 1)

    def test_script_and_files(self):
        self.assertEqual(self.r["script_signals"]["simulated_keyboard_functions"], ["hideKeyboard", "showKeyboard"])
        self.assertTrue(self.r["script_signals"]["localStorage"])
        self.assertEqual(self.r["relative_files"], ["logo.png"])
        self.assertEqual(self.r["insecure_http_urls"], ["http://x.example/a"])

    def test_notes_are_actionable(self):
        text = " ".join(self.r["notes"])
        self.assertIn("phone mockup", text)
        self.assertIn("simulated keyboard", text)
        self.assertIn("local files", text)


class AssessTest(unittest.TestCase):
    def test_mockup_is_ready_to_adapt(self):
        a = scan.scan(PROTO)["assessment"]
        self.assertEqual(a["format"], "phone-mockup")
        findings = " ".join(i["finding"] for i in a["items"])
        self.assertIn("phone mockup", findings)
        self.assertIn("Simulated keyboard", findings)

    def test_desktop_build_and_server_are_flagged(self):
        html = """<html><head><link rel="stylesheet" href="app.css"><style>
        .layout{display:grid;min-width:1200px}.menu:hover .dd{display:block}</style></head>
        <body><aside class="sidebar"></aside><script>fetch('/api/x');navigator.geolocation</script></body></html>"""
        a = scan.scan(html)["assessment"]
        self.assertEqual(a["format"], "desktop")
        self.assertEqual(a["verdict"], "needs-changes-first")
        by = {(i["feasible"], i["by"]) for i in a["items"]}
        self.assertIn(("no", "designer"), by)
        self.assertIn(("partial", "designer"), by)
        self.assertTrue(any("hover" in i["finding"] for i in a["items"]))
        self.assertTrue(any("geolocation" in i["finding"] for i in a["items"]))

    def test_mobile_page_is_ready(self):
        html = '<html><head><meta name="viewport" content="width=device-width"></head><body><p>x</p></body></html>'
        a = scan.scan(html)["assessment"]
        self.assertEqual((a["format"], a["verdict"]), ("mobile-web", "ready-to-adapt"))


if __name__ == "__main__":
    unittest.main()
