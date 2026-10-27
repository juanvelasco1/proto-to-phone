#!/usr/bin/env python3
"""Adapt a single-file HTML prototype to the native iOS shell.

Usage: adapt.py <source.html> <dest.html> [--config phone.config.json]

Writes <dest.html> and, next to it, shell.json (read by the native shell).
The source is never modified. Every literal patch in the config is anchored on
a string from the prototype and fails loudly when the anchor is missing or
ambiguous, so a redesign that moves things is caught here and not on the phone.

Python 3.8+, standard library only.
"""
import argparse
import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL_JS = os.path.join(HERE, "..", "assets", "shell.js")

MARK_BEGIN = "<!-- proto-to-phone:begin -->"
MARK_END = "<!-- proto-to-phone:end -->"

VIEWPORT = "width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover"
VIEWPORT_TAG = '<meta name="viewport" content="%s" />' % VIEWPORT

# Runs before the first paint, also when the page is opened from the home
# screen in Safari (the native shell sets the same class before any script).
HEAD_SCRIPT = """<script>
  (function () {
    var standalone = navigator.standalone ||
      (window.matchMedia && matchMedia('(display-mode: standalone)').matches);
    if (standalone) document.documentElement.classList.add('app-shell');
  })();
</script>"""

# What every prototype gets under :root.app-shell. --shell-top and
# --shell-bottom are the raw safe areas; --shell-float-bottom is where a
# floating bar rests: just over the home-indicator zone, like a native one.
BASE_CSS = """
:root.app-shell{--shell-top:env(safe-area-inset-top);--shell-bottom:env(safe-area-inset-bottom);
  --shell-float-bottom:max(16px,calc(env(safe-area-inset-bottom) - 10px))}
:root.app-shell,:root.app-shell body{-webkit-text-size-adjust:100%;-webkit-tap-highlight-color:transparent;
  overscroll-behavior:none}
:root.app-shell body{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}
:root.app-shell :is(input,textarea,[contenteditable],[contenteditable] *){-webkit-user-select:text;user-select:text}
"""


# Local files that can be inlined as data URIs (images and fonts only: local
# CSS or JS would need a bundler, and is reported instead).
INLINE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".svg": "image/svg+xml", ".avif": "image/avif",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf", ".otf": "font/otf",
}
INLINE_MAX_FILE = 5 * 1024 * 1024
INLINE_MAX_TOTAL = 30 * 1024 * 1024


class AdaptError(Exception):
    pass


def no_breakout(text, tag):
    """Config text goes inside <style>/<script>: it must not be able to close it."""
    return re.sub(r"</(%s)" % tag, r"<\\/\1", text, flags=re.I)


def load_config(path):
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        raise AdaptError("cannot read config %s: %s" % (path, e))
    if not isinstance(cfg, dict):
        raise AdaptError("config must be a JSON object")
    return cfg


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def frame_css(cfg):
    """Turn a mockup into the whole screen: no canvas around it, no bezel."""
    frame = cfg.get("frame") or {}
    out = []
    if frame.get("container"):
        out.append(":root.app-shell %s{padding:0;gap:0;margin:0;min-height:100dvh}" % frame["container"])
    if frame.get("device"):
        out.append(":root.app-shell %s{width:100%%;max-width:none;height:100dvh;margin:0;border:0;border-radius:0;"
                   "box-shadow:none;padding-top:env(safe-area-inset-top)}" % frame["device"])
    if frame.get("background"):
        out.append(":root.app-shell body{background:%s}" % frame["background"])
    hide = as_list(cfg.get("hide"))
    if hide:
        out.append(":root.app-shell %s{display:none !important}" % ",\n:root.app-shell ".join(hide))
    return "\n".join(out)


def build_css(cfg):
    parts = [BASE_CSS.strip("\n"), frame_css(cfg)]
    extra = "\n".join(as_list(cfg.get("css")))
    if extra.strip():
        parts.append("/* from phone.config.json */\n" + extra)
    return no_breakout("\n".join(p for p in parts if p.strip()), "style")


def build_js(cfg):
    runtime = {
        "keyboardTargets": as_list(cfg.get("keyboardTargets")),
        "themeSource": cfg.get("themeSource") or (cfg.get("frame") or {}).get("device"),
        "sheetDrag": cfg.get("sheetDrag"),
    }
    with open(SHELL_JS, encoding="utf-8") as f:
        shell = f.read()
    out = "<script>window.__shellConfig=%s;</script>\n<script>\n%s\n</script>" % (
        json.dumps(runtime, separators=(",", ":")).replace("</", "<\\/"), shell)
    extra = "\n".join(as_list(cfg.get("js")))
    if extra.strip():
        out += "\n<script>\n/* from phone.config.json */\n%s\n</script>" % no_breakout(extra, "script")
    return out


def apply_patches(html, patches):
    for i, p in enumerate(patches):
        what = p.get("what") or "patch %d" % (i + 1)
        find, repl = p.get("find"), p.get("replace")
        if not isinstance(find, str) or not find or not isinstance(repl, str):
            raise AdaptError("%s: needs string 'find' and 'replace'" % what)
        n = html.count(find)
        if p.get("optional") and n == 0:
            continue
        if p.get("all"):
            if n == 0:
                raise AdaptError("%s: anchor not found" % what)
        elif n != 1:
            raise AdaptError("%s: expected one anchor, found %d" % (what, n))
        html = html.replace(find, repl)
    return html


def inline_local_files(html, base_dir):
    """Replace src="x.png" / url(x.woff2) pointing inside base_dir with data URIs.

    Only files inside the prototype's own folder (no ../ escapes, no symlinks
    out), of an image or font type, under the size caps."""
    root = os.path.realpath(base_dir)
    total = [0]
    skipped = []

    def data_uri(ref):
        clean = ref.split("?")[0].split("#")[0]
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", clean, re.I) or not clean:
            return None
        ext = os.path.splitext(clean)[1].lower()
        if ext not in INLINE_TYPES:
            return None
        path = os.path.realpath(os.path.join(root, clean))
        if os.path.commonpath([root, path]) != root:
            skipped.append("%s (outside the prototype folder)" % ref)
            return None
        if not os.path.isfile(path):
            skipped.append("%s (not found)" % ref)
            return None
        size = os.path.getsize(path)
        if size > INLINE_MAX_FILE or total[0] + size > INLINE_MAX_TOTAL:
            skipped.append("%s (too large)" % ref)
            return None
        total[0] += size
        with open(path, "rb") as f:
            return "data:%s;base64,%s" % (INLINE_TYPES[ext], base64.b64encode(f.read()).decode("ascii"))

    def attr(m):
        uri = data_uri(m.group(2))
        return m.group(0) if uri is None else "%s%s%s" % (m.group(1), uri, m.group(3))

    def url(m):
        uri = data_uri(m.group(2))
        return m.group(0) if uri is None else "url(%s%s%s)" % (m.group(1), uri, m.group(1))

    html = re.sub(r"(\bsrc\s*=\s*[\"'])([^\"']+)([\"'])", attr, html, flags=re.I)
    html = re.sub(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)", url, html)
    for s_ in skipped:
        print("adapt: not inlined: %s" % s_)
    return html


def set_viewport(html):
    pat = re.compile(r"<meta\b[^>]*\bname\s*=\s*[\"']viewport[\"'][^>]*>", re.I)
    if pat.search(html):
        return pat.sub(lambda m: VIEWPORT_TAG, html, count=1)
    head = re.search(r"<head\b[^>]*>", html, re.I)
    if head:
        return html[:head.end()] + "\n" + VIEWPORT_TAG + html[head.end():]
    return VIEWPORT_TAG + "\n" + html


def insert_before(html, tag, block, last=True):
    """Insert block before </tag> (the last one, or the first); append if missing."""
    low = html.lower()
    idx = low.rfind("</%s>" % tag) if last else low.find("</%s>" % tag)
    if idx < 0:
        return html + "\n" + block + "\n"
    return html[:idx] + block + "\n" + html[idx:]


def adapt(html, cfg, base_dir=None):
    if MARK_BEGIN in html:
        raise AdaptError("the source is already adapted; pass the original prototype")
    html = apply_patches(html, cfg.get("patches") or [])
    if cfg.get("inlineLocalFiles"):
        if not base_dir:
            raise AdaptError("inlineLocalFiles needs the prototype's folder")
        html = inline_local_files(html, base_dir)
    html = set_viewport(html)

    head_block = "%s\n%s\n<style>\n%s\n</style>\n%s" % (MARK_BEGIN, HEAD_SCRIPT, build_css(cfg), MARK_END)
    html = insert_before(html, "head", head_block, last=False)

    body_block = "%s\n%s\n%s" % (MARK_BEGIN, build_js(cfg), MARK_END)
    html = insert_before(html, "body", body_block)
    return html


def scroll_mode(cfg):
    mode = cfg.get("scroll")
    if mode in ("app", "page"):
        return mode
    return "app" if (cfg.get("frame") or {}).get("device") else "page"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("dest")
    ap.add_argument("--config")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        with open(args.src, encoding="utf-8") as f:
            html = f.read()
        out = adapt(html, cfg, base_dir=os.path.dirname(os.path.abspath(args.src)))
    except (AdaptError, OSError, UnicodeDecodeError) as e:
        sys.exit("adapt: %s" % e)
    os.makedirs(os.path.dirname(os.path.abspath(args.dest)), exist_ok=True)
    with open(args.dest, "w", encoding="utf-8") as f:
        f.write(out)
    with open(os.path.join(os.path.dirname(os.path.abspath(args.dest)), "shell.json"), "w") as f:
        json.dump({"scroll": scroll_mode(cfg)}, f)
    print("adapt: %s -> %s (scroll: %s)" % (args.src, args.dest, scroll_mode(cfg)))


if __name__ == "__main__":
    main()
