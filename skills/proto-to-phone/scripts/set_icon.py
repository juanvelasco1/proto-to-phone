#!/usr/bin/env python3
"""Change the app icon of an existing project.

Usage: set_icon.py --project DIR [--logo FILE] [--logo-background #FFFFFF] [--logo-fit pad|fill]
Without --logo the icon goes back to the app's initial. Takes effect on the next sync.
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_lib as pl  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project")
    ap.add_argument("--logo")
    ap.add_argument("--logo-background", default="#FFFFFF")
    ap.add_argument("--logo-fit", default="pad", choices=["pad", "fill"])
    args = ap.parse_args()
    try:
        m = pl.load_project(args.project)
        icon = os.path.join(m["dir"], "icon.png")
        pl.make_icon(icon, m["name"], logo=args.logo, background=args.logo_background, fit=args.logo_fit)
        copies = [os.path.join(m["dir"], "App", "Assets.xcassets", "AppIcon.appiconset", "icon.png"),
                  os.path.join(m["dir"], "android", "app", "src", "main", "res", "mipmap-xxxhdpi", "ic_launcher.png")]
        for c in copies:
            if os.path.isdir(os.path.dirname(c)):
                shutil.copyfile(icon, c)
        m["logo"] = os.path.abspath(args.logo) if args.logo else None
        pl.save_project(m)
        print("set_icon: %s  <- show it to the person" % icon)
    except pl.PhoneError as e:
        sys.exit("set_icon: %s" % e)
