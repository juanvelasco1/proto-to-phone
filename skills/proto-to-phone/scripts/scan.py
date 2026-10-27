#!/usr/bin/env python3
"""Look for what keeps a single-file HTML prototype from behaving on a real phone.

Usage: scan.py <prototype.html> [--json]

Heuristics only: it points at places to read, it does not decide. The agent
reads the CSS and JS around each hit, then writes phone.config.json.

Python 3.8+, standard library only.
"""
import argparse
import json
import re
import sys
from collections import OrderedDict

# class / id tokens that give away a mockup drawn on a desktop canvas
CHROME_PATTERNS = OrderedDict([
    ("statusbar", r"(^|[-_])status[-_]?bar($|[-_])|^statusbar"),
    ("keyboard", r"(^|[-_])(kb|keyboard)($|[-_])"),
    ("frame", r"^(device|iphone|phone|bezel|mockup|device[-_]frame|phone[-_]frame)$"),
    ("notch", r"notch|dynamic[-_]?island"),
    ("home-indicator", r"home[-_]?(indicator|bar)$"),
    ("caption", r"^(cap|caption|device[-_]?cap|device[-_]?label)$"),
    ("canvas", r"^(canvas|stage[-_]?wrap|scene|backdrop)$"),
])


def style_blocks(html):
    return re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.S | re.I)


def css_rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel = " ".join(m.group(1).split())
        sel = sel.split("}")[-1].strip()
        yield sel, m.group(2)


def decl(body, prop):
    m = re.search(r"(?:^|[;\s])%s\s*:\s*([^;]+)" % re.escape(prop), body, re.I)
    return m.group(1).strip() if m else None


def line_of(html, needle):
    i = html.find(needle)
    return html.count("\n", 0, i) + 1 if i >= 0 else None


def scan(html):
    r = OrderedDict()
    css_all = "\n".join(style_blocks(html))
    rules = list(css_rules(css_all))

    vp = re.search(r"<meta\b[^>]*\bname\s*=\s*[\"']viewport[\"'][^>]*>", html, re.I)
    r["viewport"] = vp.group(0) if vp else None
    r["bytes"] = len(html.encode("utf-8"))

    # mockup chrome by class/id
    tokens = OrderedDict()
    for attr, val in re.findall(r"\b(class|id)\s*=\s*\"([^\"]*)\"", html):
        for t in val.split():
            key = ("#" if attr == "id" else ".") + t
            tokens[key] = tokens.get(key, 0) + 1
    chrome = OrderedDict()
    for key, n in tokens.items():
        bare = key[1:]
        for kind, pat in CHROME_PATTERNS.items():
            if re.search(pat, bare, re.I):
                chrome.setdefault(kind, []).append({"selector": key, "uses": n})
                break
    r["mockup_chrome"] = chrome

    # fixed-width frames
    frames = []
    for sel, body in rules:
        w = decl(body, "width")
        m = re.fullmatch(r"(\d+(?:\.\d+)?)px", w or "")
        if m and 340 <= float(m.group(1)) <= 450 and re.search(
                r"device|phone|frame|iphone|mockup|screen|app\b", sel, re.I):
            frames.append({"selector": sel, "width": w})
    r["fixed_width_frames"] = frames

    # anchored to an edge: these need the safe areas. Decorations (pseudo
    # elements, sibling separators) and sub-12px nudges are not edge bars.
    bottom, top = [], []
    for sel, body in rules:
        if re.search(r"::|:before|:after|[+~]", sel):
            continue
        pos = decl(body, "position")
        if pos and pos.split()[0] in ("absolute", "fixed", "sticky"):
            b, t = decl(body, "bottom"), decl(body, "top")
            nudge = bool(b) and bool(re.fullmatch(r"-?([1-9]|1[01])(\.\d+)?px", b.strip()))
            if b and "env(" not in b and not nudge:
                bottom.append({"selector": sel, "position": pos, "bottom": b})
            if t and pos.split()[0] == "fixed" and re.fullmatch(r"0(px)?", t.strip()):
                top.append({"selector": sel, "position": pos, "top": t})
    r["bottom_anchored"] = bottom[:15]
    r["top_anchored"] = top[:15]

    # inputs under 16px: iOS zooms the page on focus (the shell also sets maximum-scale=1)
    small = []
    for sel, body in rules:
        if re.search(r"\b(input|textarea|select)\b|contenteditable", sel, re.I):
            fs = decl(body, "font-size")
            m = re.fullmatch(r"(\d+(?:\.\d+)?)px", fs or "")
            if m and float(m.group(1)) < 16:
                small.append({"selector": sel, "font_size": fs})
    r["inputs_under_16px"] = small

    r["uses_100vh"] = len(re.findall(r"100vh", css_all))
    r["uses_100dvh"] = len(re.findall(r"100dvh", css_all))
    r["safe_area_env_uses"] = len(re.findall(r"env\(\s*safe-area-inset", html))
    r["hover_rules"] = len(re.findall(r":hover", css_all))

    js = "\n".join(re.findall(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S | re.I))
    sig = OrderedDict()
    sig["simulated_keyboard_functions"] = sorted(set(re.findall(r"function\s+(\w*(?:[Kk]b|[Kk]eyboard)\w*)\s*\(", js)))
    sig["kb_open_class"] = bool(re.search(r"kb-open", html))
    sig["localStorage"] = "localStorage" in js
    sig["window_open_or_blank"] = bool(re.search(r"window\.open\(|target\s*=\s*[\"']_blank", html))
    sig["scrollIntoView"] = "scrollIntoView" in js
    sig["file_inputs"] = len(re.findall(r"<input\b[^>]*type\s*=\s*[\"']file[\"']", html, re.I))
    sig["permissions"] = sorted(set(re.findall(r"\b(geolocation|getUserMedia|Notification\.requestPermission|vibrate)\b", js)))
    sig["dark_theme_signals"] = bool(re.search(r"prefers-color-scheme|\.dark\b|data-theme", html))
    r["script_signals"] = sig

    # network and files
    urls = re.findall(r"(?:src|href)\s*=\s*\"(https?://[^\"]+)\"|url\(\s*['\"]?(https?://[^)'\"]+)|@import\s+['\"](https?://[^'\"]+)", html)
    flat = sorted({u for t in urls for u in t if u and "w3.org" not in u})
    r["external_urls"] = [u for u in flat if not re.match(r"https?://(www\.)?(w3\.org)", u)][:20]
    r["insecure_http_urls"] = [u for u in flat if u.startswith("http://")][:10]
    rel = re.findall(r"(?:src|href)\s*=\s*\"((?!https?:|data:|#|//|mailto:|tel:|javascript:)[^\"]+\.(?:png|jpe?g|gif|svg|webp|css|js|woff2?|ttf|mp4))\"", html, re.I)
    r["relative_files"] = sorted(set(rel))[:20]

    # format signals used by assess()
    fmt = OrderedDict()
    fmt["wide_fixed_layouts"] = [sel for sel, body in rules
                                 if re.search(r"^(html|body|main)$|\.(app|container|wrapper|layout|page|shell)\b", sel)
                                 and any(float(v) >= 600 for v in re.findall(r"(?:^|[;\s])(?:min-)?width\s*:\s*(\d{3,4})px", body))][:8]
    fmt["sidebar"] = any(re.search(r"side-?bar|side-?nav|drawer", t, re.I) for t in tokens)
    fmt["mobile_media_queries"] = len(re.findall(r"@media[^{]*max-width\s*:\s*(?:[3-7]\d\d)px", css_all))
    fmt["landscape_rules"] = len(re.findall(r"orientation\s*:\s*landscape", css_all))
    fmt["tablet_frame"] = [f for f in rules_widths(rules) if 700 <= f[1] <= 1100]
    fmt["local_css_js"] = sorted(set(re.findall(
        r"<(?:link\b[^>]*\bhref|script\b[^>]*\bsrc)\s*=\s*[\"']((?!https?:|//|data:)[^\"']+\.(?:css|js|mjs|ts|tsx|jsx))[\"']", html, re.I)))
    fmt["needs_build"] = bool(re.search(r"<script\b[^>]*type\s*=\s*[\"']module[\"'][^>]*src\s*=\s*[\"'][^\"']*\.(?:tsx?|jsx)", html, re.I)
                              or re.search(r"^\s*import\s+[^;]+from\s+['\"]\.{1,2}/", js, re.M))
    fmt["server_calls"] = sorted(set(re.findall(
        r"(?:fetch|axios\.\w+|open)\(\s*['\"`](\/(?!\/)[^'\"`]*|api\/[^'\"`]*|https?:\/\/localhost[^'\"`]*)", js)))[:8]
    fmt["websocket_localhost"] = bool(re.search(r"wss?://(localhost|127\.0\.0\.1)", js))
    fmt["hover_only_reveals"] = len(re.findall(
        r":hover[^{,]*\{[^}]*(?:display\s*:\s*(?:block|flex|grid)|visibility\s*:\s*visible|opacity\s*:\s*1\b)", css_all))
    fmt["small_targets"] = [sel for sel, body in rules
                            if re.search(r"btn|button|tab\b|chip|close|toggle", re.split(r"[\s>+~]+", sel)[-1], re.I)
                            and not re.search(r"::|:before|:after|(^|[.\-])ic(on)?$|^svg", re.split(r"[\s>+~]+", sel)[-1])
                            and any(float(v) < 32 for v in re.findall(r"(?:^|[;\s])height\s*:\s*(\d+(?:\.\d+)?)px", body))][:8]
    r["format_signals"] = fmt

    r["notes"] = notes(r)
    r["assessment"] = assess(r)
    return r


def rules_widths(rules):
    out = []
    for sel, body in rules:
        if re.search(r"device|tablet|ipad|frame|mockup", sel, re.I):
            for v in re.findall(r"(?:^|[;\s])width\s*:\s*(\d{3,4})px", body):
                out.append((sel, float(v)))
    return out


def assess(r):
    """What kind of prototype this is, whether it can work on an iPhone, and
    what to adapt. feasible: yes | partial | no. by: skill (the config does
    it) | designer (change it in the prototype's builder) | none."""
    f, sig, chrome = r["format_signals"], r["script_signals"], r["mockup_chrome"]
    items = []

    def add(finding, proposal, feasible, by):
        items.append(OrderedDict([("finding", finding), ("proposal", proposal),
                                  ("feasible", feasible), ("by", by)]))

    mockup = bool(chrome.get("frame") or r["fixed_width_frames"])
    desktop = not mockup and (bool(f["wide_fixed_layouts"]) or (f["sidebar"] and not f["mobile_media_queries"])
                              or not r["viewport"])
    if f["tablet_frame"]:
        fmt = "tablet-mockup"
    elif mockup:
        fmt = "phone-mockup"
    elif desktop:
        fmt = "desktop"
    elif f["mobile_media_queries"]:
        fmt = "responsive"
    else:
        fmt = "mobile-web"

    if fmt == "phone-mockup":
        add("Drawn inside a phone mockup on a desktop canvas", "Make the device the whole screen; hide the fake chrome", "yes", "skill")
    if fmt == "tablet-mockup":
        add("Tablet-sized mockup (%dpx)" % f["tablet_frame"][0][1],
            "The app is iPhone-only: it would be squeezed to ~400pt. Ask the builder for a phone version", "partial", "designer")
    if fmt == "desktop":
        why = (["fixed widths: " + ", ".join(f["wide_fixed_layouts"][:3])] if f["wide_fixed_layouts"] else []) + \
              (["sidebar without mobile breakpoints"] if f["sidebar"] and not f["mobile_media_queries"] else []) + \
              (["no viewport meta (built for a desktop browser)"] if not r["viewport"] else [])
        add("Desktop layout (%s)" % "; ".join(why),
            "It runs, but as a shrunk or overflowing desktop page. Ask the builder for a mobile version of the screens", "partial", "designer")
    if f["needs_build"] or f["local_css_js"]:
        add("Source code or separate CSS/JS files (%s)" % ", ".join(f["local_css_js"][:3] or ["module imports"]),
            "Only one HTML file is bundled. Export or build the prototype as a single HTML file first", "no", "designer")
    if f["server_calls"] or f["websocket_localhost"]:
        add("Calls a server or localhost (%s)" % ", ".join(f["server_calls"][:3] or ["websocket"]),
            "There is no server in the app; those calls fail. Use mock data in the prototype", "no", "designer")
    if chrome.get("keyboard") or sig["simulated_keyboard_functions"]:
        add("Simulated keyboard", "Hide it; the real keyboard drives kb-open", "yes", "skill")
    if r["bottom_anchored"]:
        add("Bars anchored to the bottom (%s)" % ", ".join(b["selector"] for b in r["bottom_anchored"][:3]),
            "Respect the home indicator; size a floating tab bar like a native one", "yes", "skill")
    if r["uses_100vh"]:
        add("100vh heights", "Use 100dvh inside the app", "yes", "skill")
    if r["inputs_under_16px"]:
        add("Text fields under 16px", "Zoom on focus is already blocked; 16px is still better for legibility", "yes", "skill")
    if f["small_targets"]:
        add("Small tap targets (%s)" % ", ".join(f["small_targets"][:3]),
            "Stretch the hit area to 44pt without changing the look", "yes", "skill")
    if f["hover_only_reveals"]:
        add("%d hover-only reveals (menus or actions that appear on :hover)" % f["hover_only_reveals"],
            "Touch has no hover: those need a tap. Check each one; some need a change in the builder", "partial", "designer")
    if f["landscape_rules"]:
        add("Landscape rules", "The app is portrait-only", "partial", "none")
    media = [x for x in r["relative_files"] if not re.search(r"\.(css|js)$", x, re.I)]
    if media:
        add("Local images or fonts (%s)" % ", ".join(media[:3]),
            "Inline them into the bundled copy (inlineLocalFiles)", "yes", "skill")
    if r["insecure_http_urls"]:
        add("http:// resources", "iOS blocks them. Switch them to https:// in the prototype", "no", "designer")
    if r["external_urls"]:
        add("Loads %d external resources" % len(r["external_urls"]),
            "Works with internet only, and those servers see the requests", "partial", "none")
    if sig["permissions"]:
        add("Uses %s" % ", ".join(sig["permissions"]), "Not wired by this app shell", "no", "none")
    if sig["file_inputs"]:
        add("File or photo picker", "Works (camera and photo permissions are declared)", "yes", "skill")

    blockers = [i for i in items if i["feasible"] == "no" and i["by"] == "designer"]
    partial = [i for i in items if i["feasible"] in ("partial", "no")]
    if blockers:
        verdict = "needs-changes-first"
    elif fmt in ("desktop", "tablet-mockup"):
        verdict = "possible-but-not-a-phone-design"
    elif partial:
        verdict = "works-with-limits"
    else:
        verdict = "ready-to-adapt"
    return OrderedDict([("format", fmt), ("verdict", verdict), ("items", items)])


def notes(r):
    n = []
    if not r["viewport"]:
        n.append("No viewport meta: adapt.py adds one.")
    if r["mockup_chrome"].get("frame") or r["fixed_width_frames"]:
        n.append("The design is drawn inside a phone mockup: set frame.container, frame.device and hide the fake status bar, keyboard, notch and home indicator.")
    if r["mockup_chrome"].get("keyboard") or r["script_signals"]["simulated_keyboard_functions"]:
        n.append("A simulated keyboard exists: hide it, and read what the design does with kb-open (tab bars, composers). The shell sets kb-open from the real keyboard.")
    if r["bottom_anchored"]:
        n.append("Elements anchored to the bottom edge need the safe area: use --shell-bottom or --shell-float-bottom.")
    if r["safe_area_env_uses"]:
        n.append("The prototype already uses env(safe-area-inset-*): check it is not counted twice inside the shell.")
    if r["relative_files"]:
        n.append("References to local files: only index.html is bundled. Inline them or the app shows broken images.")
    if r["insecure_http_urls"]:
        n.append("http:// resources are blocked by App Transport Security; use https://.")
    if r["external_urls"]:
        n.append("External resources need network access on the phone.")
    if r["script_signals"]["scrollIntoView"]:
        n.append("scrollIntoView can shift the whole page under the keyboard; check forms.")
    if r["script_signals"]["file_inputs"] or r["script_signals"]["permissions"]:
        n.append("Camera, photos, microphone or location: Info.plist carries usage strings; location and notifications are not wired by the shell.")
    return n


def human(r):
    out = []
    add = out.append
    add("viewport: %s" % (r["viewport"] or "MISSING"))
    for kind, items in r["mockup_chrome"].items():
        add("mockup %-14s %s" % (kind, ", ".join("%s (%d)" % (i["selector"], i["uses"]) for i in items)))
    for f in r["fixed_width_frames"]:
        add("fixed-width frame: %s { width: %s }" % (f["selector"], f["width"]))
    for b in r["bottom_anchored"]:
        add("bottom-anchored: %s { %s; bottom: %s }" % (b["selector"], b["position"], b["bottom"]))
    for t in r["top_anchored"]:
        add("top-anchored:    %s { %s; top: %s }" % (t["selector"], t["position"], t["top"]))
    for s in r["inputs_under_16px"]:
        add("input under 16px: %s { font-size: %s }" % (s["selector"], s["font_size"]))
    add("100vh: %d   100dvh: %d   env(safe-area): %d   :hover rules: %d" % (
        r["uses_100vh"], r["uses_100dvh"], r["safe_area_env_uses"], r["hover_rules"]))
    for k, v in r["script_signals"].items():
        if v:
            add("script: %s = %s" % (k, v))
    for u in r["external_urls"]:
        add("external: %s" % u)
    for f in r["relative_files"]:
        add("local file: %s" % f)
    a = r["assessment"]
    add("")
    add("ASSESSMENT  format: %s   verdict: %s" % (a["format"], a["verdict"]))
    for i in a["items"]:
        add("  [%-7s by %-8s] %s -> %s" % (i["feasible"], i["by"], i["finding"], i["proposal"]))
    add("")
    for n in r["notes"]:
        add("- " + n)
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        with open(args.src, encoding="utf-8") as f:
            html = f.read()
    except (OSError, UnicodeDecodeError) as e:
        sys.exit("scan: %s" % e)
    r = scan(html)
    print(json.dumps(r, indent=2, ensure_ascii=False) if args.json else human(r))


if __name__ == "__main__":
    main()
