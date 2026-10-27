import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "proto-to-phone", "scripts"))
import adapt  # noqa: E402

PROTO = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>.device{width:390px}</style></head>
<body><div class="canvas"><div id="device" class="device"><div class="statusbar"></div>
<div class="fake-keyboard"></div><button id="b">go</button></div></div></body></html>"""


class AdaptTest(unittest.TestCase):
    def test_viewport_is_replaced(self):
        out = adapt.adapt(PROTO, {})
        self.assertEqual(out.count('name="viewport"'), 1)
        self.assertIn("maximum-scale=1, viewport-fit=cover", out)

    def test_viewport_is_added_when_missing(self):
        out = adapt.adapt("<html><head></head><body></body></html>", {})
        self.assertIn('name="viewport"', out)

    def test_base_layer_and_shell_js_injected(self):
        out = adapt.adapt(PROTO, {})
        self.assertIn(":root.app-shell", out)
        self.assertIn("--shell-float-bottom", out)
        self.assertIn("window.__shellConfig", out)
        self.assertIn("window.__shell", out)
        self.assertLess(out.index("proto-to-phone:begin"), out.lower().index("</head>"))

    def test_frame_hide_and_extra_css(self):
        cfg = {"frame": {"container": ".canvas", "device": "#device"}, "hide": [".statusbar", ".fake-keyboard"],
               "css": [":root.app-shell .x{color:red}"], "keyboardTargets": ["#device"]}
        out = adapt.adapt(PROTO, cfg)
        self.assertIn(":root.app-shell .canvas{padding:0", out)
        self.assertIn(":root.app-shell #device{width:100%", out)
        self.assertIn(":root.app-shell .statusbar,", out)
        self.assertIn("display:none !important", out)
        self.assertIn(".x{color:red}", out)
        self.assertIn('"keyboardTargets":["#device"]', out)

    def test_patch_applies_and_fails_loudly(self):
        ok = adapt.adapt(PROTO, {"patches": [{"find": ">go<", "replace": ">stop<"}]})
        self.assertIn(">stop<", ok)
        with self.assertRaises(adapt.AdaptError):
            adapt.adapt(PROTO, {"patches": [{"what": "missing", "find": "nope", "replace": "x"}]})
        with self.assertRaises(adapt.AdaptError):
            adapt.adapt(PROTO, {"patches": [{"what": "ambiguous", "find": "<div", "replace": "<div"}]})

    def test_optional_and_all_patches(self):
        out = adapt.adapt(PROTO, {"patches": [{"find": "nope", "replace": "x", "optional": True},
                                              {"find": "<div", "replace": "<section", "all": True}]})
        self.assertNotIn("<div", out.split("proto-to-phone:begin")[0])

    def test_already_adapted_is_refused(self):
        once = adapt.adapt(PROTO, {})
        with self.assertRaises(adapt.AdaptError):
            adapt.adapt(once, {})

    def test_source_is_not_modified_and_shell_json_written(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "p.html"), os.path.join(d, "out", "index.html")
            with open(src, "w") as f:
                f.write(PROTO)
            cfg = os.path.join(d, "c.json")
            with open(cfg, "w") as f:
                json.dump({"frame": {"device": "#device"}}, f)
            adapt.main([src, dst, "--config", cfg])
            with open(src) as f:
                self.assertEqual(f.read(), PROTO)
            with open(os.path.join(d, "out", "shell.json")) as f:
                self.assertEqual(json.load(f), {"scroll": "app"})

    def test_scroll_mode(self):
        self.assertEqual(adapt.scroll_mode({}), "page")
        self.assertEqual(adapt.scroll_mode({"frame": {"device": "#d"}}), "app")
        self.assertEqual(adapt.scroll_mode({"frame": {"device": "#d"}, "scroll": "page"}), "page")

    def test_script_close_tag_in_config_is_escaped(self):
        out = adapt.adapt(PROTO, {"sheetDrag": {"sheet": "</script>", "scrim": "#s"}})
        self.assertNotIn('"sheet":"</script>"', out)

    def test_config_cannot_close_style_or_script(self):
        out = adapt.adapt(PROTO, {"css": ["a{}</style><script>bad()</script>"], "js": ["var s='</script>'"]})
        block = out.split("proto-to-phone:begin")[1]
        self.assertNotIn("</style><script>bad()", block)
        self.assertIn("<\\/style>", block)
        self.assertIn("var s='<\\/script>'", out)

    def test_inline_local_files_stays_inside_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "proto", "img"))
            with open(os.path.join(d, "proto", "img", "a.png"), "wb") as f:
                f.write(b"PNG")
            with open(os.path.join(d, "secret.png"), "wb") as f:
                f.write(b"SECRET")
            html = ('<html><head><style>.a{background:url(img/a.png)}</style></head><body>'
                    '<img src="img/a.png"><img src="../secret.png"><img src="https://x.example/b.png"></body></html>')
            out = adapt.adapt(html, {"inlineLocalFiles": True}, base_dir=os.path.join(d, "proto"))
            self.assertEqual(out.count("data:image/png;base64,UE5H"), 2)
            self.assertIn('src="../secret.png"', out)
            self.assertNotIn("U0VDUkVU", out)
            self.assertIn("https://x.example/b.png", out)


if __name__ == "__main__":
    unittest.main()
