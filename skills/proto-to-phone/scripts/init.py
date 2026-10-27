#!/usr/bin/env python3
"""Create a phone project (a small Xcode app that runs one prototype).

Usage: init.py --name "My App" --src prototype.html
               [--logo logo.png|svg|pdf|jpg|heic] [--logo-background #FFFFFF] [--logo-fit pad|fill]
               [--team ID|none] [--bundle-id ID] [--dir DIR] [--force]

Projects live in ~/ProtoPhone/<slug> (or $PROTO_PHONE_HOME), never inside the
skill. The prototype is only read. Without --logo the icon is the app's initial.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_lib as pl  # noqa: E402

STARTER_CONFIG = {"frame": None, "hide": [], "keyboardTargets": [], "css": [], "js": [], "patches": []}
GITIGNORE = "build/\n*.xcodeproj/\nshots/\n"
TEMPLATE_ENTRIES = ("App", "UITests", "project.yml")


def pick_team(arg):
    if arg:
        if arg.lower() == "none":
            return None
        if not pl.TEAM_RE.match(arg):
            raise pl.PhoneError("A team ID is 10 capital letters and digits (see doctor.py).")
        return arg
    teams = pl.xcode_teams()
    paid = [t for t in teams if not t["free"]]
    pool = paid or teams
    if len(pool) == 1:
        return pool[0]["id"]
    if len(pool) > 1:
        raise pl.PhoneError("Several signing teams found (%s). Pass --team <ID> (or --team none for simulator only)."
                            % ", ".join("%s %s" % (t["id"], t["name"]) for t in pool))
    return None


def safe_destination(dest, force):
    """Write only into a new or empty folder, or into one of our own projects."""
    if not os.path.exists(dest):
        return
    if not os.path.isdir(dest):
        raise pl.PhoneError("%s exists and is not a folder." % dest)
    ours = os.path.isfile(os.path.join(dest, pl.META))
    if ours and not force:
        raise pl.PhoneError("%s already exists. Use it (sync.py --project) or pass --force to rebuild it "
                            "(phone.config.json is kept)." % dest)
    if not ours and os.listdir(dest):
        raise pl.PhoneError("%s is not empty and is not a proto-to-phone project; choose another --dir." % dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", required=True, help="name shown under the icon (1-30 characters)")
    ap.add_argument("--src", required=True, help="the prototype HTML")
    ap.add_argument("--logo", help="logo image for the icon (png, jpg, heic, tiff, svg, pdf)")
    ap.add_argument("--logo-background", default="#FFFFFF", help="color behind the logo, e.g. #FFFFFF")
    ap.add_argument("--logo-fit", default="pad", choices=["pad", "fill"],
                    help="pad: logo centered with margin; fill: logo covers the whole icon")
    ap.add_argument("--team", help="Apple signing team ID, or 'none' for simulator only")
    ap.add_argument("--bundle-id")
    ap.add_argument("--dir")
    ap.add_argument("--force", action="store_true", help="rebuild an existing proto-to-phone project")
    args = ap.parse_args()

    try:
        name = pl.check_name(args.name)
        src = os.path.abspath(os.path.expanduser(args.src))
        if not os.path.isfile(src) or not src.lower().endswith((".html", ".htm")):
            raise pl.PhoneError("The prototype must be an existing .html file: %s" % src)
        slug, product = pl.slugify(name), pl.product_name(name)
        dest = os.path.abspath(os.path.expanduser(args.dir)) if args.dir else os.path.join(pl.projects_root(), slug)
        safe_destination(dest, args.force)

        team = pick_team(args.team)
        if args.bundle_id:
            if not pl.BUNDLE_RE.match(args.bundle_id) or len(args.bundle_id) > 155:
                raise pl.PhoneError("A bundle id looks like com.example.myapp (letters, digits, hyphens, dots).")
            bundle_id = args.bundle_id
        elif team:
            bundle_id = "phone.%s.%s" % (team.lower(), slug)
        else:
            bundle_id = "local.protophone.%s" % slug
        prefix = bundle_id.rsplit(".", 1)[0]

        os.makedirs(dest, exist_ok=True)
        tpl = os.path.join(pl.SKILL, "template")
        for entry in TEMPLATE_ENTRIES:
            to = os.path.join(dest, entry)
            if os.path.isdir(to):
                shutil.rmtree(to)
            if os.path.isdir(os.path.join(tpl, entry)):
                shutil.copytree(os.path.join(tpl, entry), to)
            else:
                shutil.copy2(os.path.join(tpl, entry), to)

        subs = {"__TEAM_ID__": team or "", "__BUNDLE_ID__": bundle_id, "__BUNDLE_PREFIX__": prefix,
                "__PRODUCT_NAME__": product, "__DISPLAY_NAME__": escape(name)}
        for rel in ("project.yml", os.path.join("App", "Info.plist")):
            fp = os.path.join(dest, rel)
            with open(fp, encoding="utf-8") as f:
                text = f.read()
            for k, v in subs.items():
                text = text.replace(k, v)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(text)

        os.makedirs(os.path.join(dest, "Web"), exist_ok=True)
        icon = os.path.join(dest, "App", "Assets.xcassets", "AppIcon.appiconset", "icon.png")
        pl.make_icon(icon, name, logo=args.logo, background=args.logo_background, fit=args.logo_fit)
        cfg = os.path.join(dest, "phone.config.json")
        if not os.path.exists(cfg):
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(STARTER_CONFIG, f, indent=2)
        with open(os.path.join(dest, ".gitignore"), "w") as f:
            f.write(GITIGNORE)
        pl.save_project({"dir": dest, "name": name, "slug": slug, "product": product, "bundle_id": bundle_id,
                         "team": team, "source": src, "logo": os.path.abspath(args.logo) if args.logo else None,
                         "device_confirmed": False, "verified": None})

        print("init: project at %s" % dest)
        print("init: bundle id %s, team %s" % (bundle_id, team or "none (simulator only)"))
        print("init: icon %s  <- show it to the person before going on" % icon)
        if len(name) > 12:
            print("init: note: the home screen shows about 12 characters; '%s' may be cut." % name)
        scan = subprocess.run([sys.executable, "-I", os.path.join(pl.HERE, "scan.py"), src], universal_newlines=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print("\nscan of the prototype:\n" + scan.stdout)
    except pl.PhoneError as e:
        sys.exit("init: %s" % e)


if __name__ == "__main__":
    main()
