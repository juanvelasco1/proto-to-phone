#!/usr/bin/env python3
"""Check this Mac can put a prototype on an iPhone, and say what is missing.

Usage: doctor.py [--json]
Exit code 0 when at least the simulator path works.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_lib as pl  # noqa: E402


def check():
    r = {"ok_simulator": False, "ok_device": False, "problems": [], "advice": []}
    prob, adv = r["problems"], r["advice"]

    if sys.platform != "darwin":
        prob.append("iOS apps can only be built on macOS.")
        return r

    r["python"] = "%d.%d" % sys.version_info[:2]
    if sys.version_info < (3, 8):
        prob.append("Python 3.8 or newer is required (found %s)." % r["python"])

    dev_dir = pl.run(["xcode-select", "-p"], check=False).stdout.strip()
    r["developer_dir"] = dev_dir
    xcb = pl.run(["xcodebuild", "-version"], check=False)
    if xcb.returncode != 0 or "Xcode.app" not in dev_dir and "Xcode" not in xcb.stdout:
        prob.append("Full Xcode is required (Command Line Tools alone are not enough).")
        adv.append("Install Xcode from the App Store, open it once, then run: sudo xcode-select -s /Applications/Xcode.app")
    else:
        r["xcode"] = xcb.stdout.splitlines()[0]
        first = pl.run(["xcodebuild", "-checkFirstLaunchStatus"], check=False)
        if first.returncode != 0:
            prob.append("Xcode has pending first-launch setup or license.")
            adv.append("Run once: sudo xcodebuild -runFirstLaunch   (and: sudo xcodebuild -license accept)")

    r["xcodegen"] = pl.have("xcodegen")
    if not r["xcodegen"]:
        prob.append("xcodegen is not installed.")
        adv.append("brew install xcodegen   (Homebrew: https://brew.sh)")

    sims = pl.simulators()
    r["simulators"] = sims
    if not sims:
        prob.append("No iPhone simulator is installed.")
        adv.append("Xcode > Settings > Components: install an iOS runtime.")

    r["teams"] = pl.xcode_teams()
    r["devices"] = pl.physical_devices()
    if not r["teams"]:
        adv.append("To install on a real iPhone, sign in with an Apple ID: Xcode > Settings > Accounts. "
                   "A free account works (the app expires after 7 days; reinstall to renew).")
    for t in r["teams"]:
        t["note"] = "free account: apps expire after 7 days" if t["free"] else "paid program"
    if not r["devices"]:
        adv.append("No iPhone is paired. Connect it by cable, unlock it, tap Trust, and enable "
                   "Settings > Privacy & Security > Developer Mode (the phone restarts).")
    for d in r["devices"]:
        if d["developer_mode"] not in ("enabled", None):
            adv.append("%s: enable Settings > Privacy & Security > Developer Mode." % d["name"])

    blocking = [p for p in prob]
    r["ok_simulator"] = not blocking
    r["ok_device"] = r["ok_simulator"] and bool(r["teams"]) and any(d["reachable"] for d in r["devices"])
    return r


def human(r):
    out = []
    mark = lambda ok: "ok " if ok else "-- "
    out.append(mark(sys.platform == "darwin") + "macOS")
    if "xcode" in r:
        out.append(mark(True) + r["xcode"])
    out.append(mark(r.get("xcodegen")) + "xcodegen")
    out.append(mark(bool(r.get("simulators"))) + "iPhone simulators: %d" % len(r.get("simulators", [])))
    for t in r.get("teams", []):
        out.append("ok signing team %s (%s) — %s" % (t["id"], t["name"], t["note"]))
    if not r.get("teams"):
        out.append("-- no signing team (simulator only)")
    for d in r.get("devices", []):
        state = "reachable" if d["reachable"] else "not reachable (unlock it / connect it)"
        out.append("%siPhone %s (%s, iOS %s): %s" % (mark(d["reachable"]), d["name"], d["model"], d["os"], state))
    out.append("")
    out.append("simulator: %s    real iPhone: %s" % ("READY" if r["ok_simulator"] else "NOT READY",
                                                      "READY" if r["ok_device"] else "NOT READY"))
    for p in r["problems"]:
        out.append("problem: " + p)
    for a in r["advice"]:
        out.append("-> " + a)
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = check()
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else human(res))
    sys.exit(0 if res["ok_simulator"] else 1)
