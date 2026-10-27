#!/usr/bin/env python3
"""Check what this computer can do, per platform, and say exactly what is missing.

Usage: doctor.py [--json]

ios      app on an iPhone (needs a Mac with Xcode)
android  app on an Android phone (any computer; experimental)
web      the phone's browser over the local network (any computer, any phone)

Exit code 0 when at least one platform is ready.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import android_lib as al  # noqa: E402
import phone_lib as pl  # noqa: E402


def check_ios():
    r = {"ready": False, "device_ready": False, "problems": [], "advice": [], "details": []}
    if sys.platform != "darwin":
        r["problems"].append("iOS apps can only be built on a Mac (Apple's rule). Use web mode for an iPhone.")
        return r
    dev_dir = pl.run(["xcode-select", "-p"], check=False).stdout.strip()
    xcb = pl.run(["xcodebuild", "-version"], check=False)
    if xcb.returncode != 0 or ("Xcode.app" not in dev_dir and "Xcode" not in xcb.stdout):
        r["problems"].append("Full Xcode is required (Command Line Tools alone are not enough).")
        r["advice"].append("Install Xcode from the App Store, open it once, then run: "
                           "sudo xcode-select -s /Applications/Xcode.app")
    else:
        r["details"].append(xcb.stdout.splitlines()[0])
        if pl.run(["xcodebuild", "-checkFirstLaunchStatus"], check=False).returncode != 0:
            r["problems"].append("Xcode has pending first-launch setup or license.")
            r["advice"].append("Run once: sudo xcodebuild -runFirstLaunch   (and: sudo xcodebuild -license accept)")
    if not pl.have("xcodegen"):
        r["problems"].append("xcodegen is not installed.")
        r["advice"].append("brew install xcodegen   (Homebrew: https://brew.sh)")
    sims = pl.simulators()
    r["details"].append("iPhone simulators: %d" % len(sims))
    if not sims:
        r["problems"].append("No iPhone simulator is installed.")
        r["advice"].append("Xcode > Settings > Components: install an iOS runtime.")
    teams = pl.xcode_teams()
    devices = pl.physical_devices()
    for t in teams:
        r["details"].append("signing team %s (%s): %s" % (t["id"], t["name"],
                            "free account, apps expire after 7 days" if t["free"] else "paid program"))
    for d in devices:
        r["details"].append("iPhone %s (%s, iOS %s): %s" % (d["name"], d["model"], d["os"],
                            "reachable" if d["reachable"] else "not reachable (unlock it / connect it)"))
        if d["developer_mode"] not in ("enabled", None):
            r["advice"].append("%s: enable Settings > Privacy & Security > Developer Mode." % d["name"])
    if not teams:
        r["advice"].append("For a real iPhone, sign in with an Apple ID: Xcode > Settings > Accounts (free works).")
    if not devices:
        r["advice"].append("No iPhone paired: connect it by cable, unlock it, tap Trust, and enable Developer Mode.")
    r["ready"] = not r["problems"]
    r["device_ready"] = r["ready"] and bool(teams) and any(d["reachable"] for d in devices)
    return r


def check_android():
    r = {"ready": False, "device_ready": False, "experimental": True, "problems": [], "advice": [], "details": []}
    java = al.java_major()
    if not java or java < 17:
        r["problems"].append("Java 17 or newer is required%s." % (" (found %s)" % java if java else ""))
        r["advice"].append("Install a JDK 17+ (for example Temurin: https://adoptium.net), or Android Studio, which bundles one.")
    else:
        r["details"].append("Java %d" % java)
    if not al.sdk_root():
        r["problems"].append("The Android SDK was not found.")
        r["advice"].append("Install Android Studio (https://developer.android.com/studio) or the command-line tools, "
                           "and set ANDROID_HOME to the SDK folder.")
    else:
        r["details"].append("Android SDK at %s" % al.sdk_root())
    if not al.tool("adb"):
        r["problems"].append("adb (platform-tools) was not found.")
        r["advice"].append("Android Studio > SDK Manager > SDK Tools: Android SDK Platform-Tools.")
    gv = al.gradle_version()
    if not gv or gv < (8, 9):
        r["problems"].append("Gradle 8.9 or newer is required%s." % (" (found %d.%d)" % gv if gv else ""))
        r["advice"].append("Install Gradle (https://gradle.org/install: brew, scoop, sdkman or the zip).")
    else:
        r["details"].append("Gradle %d.%d" % gv)
    emus = al.avds()
    r["details"].append("Android emulators: %d" % len(emus))
    phones = [d for d in al.devices() if not d["emulator"]]
    for d in phones:
        r["details"].append("Android %s %s: %s" % (d["model"], d["serial"], d["state"]))
        if d["state"] == "unauthorized":
            r["advice"].append("Unlock the Android phone and accept 'Allow USB debugging'.")
    if not emus and not phones:
        r["advice"].append("Create an emulator in Android Studio > Device Manager, or connect a phone with "
                           "Developer options > USB debugging on.")
    r["ready"] = not r["problems"] and bool(emus or phones)
    if not r["problems"] and not (emus or phones):
        r["problems"].append("No emulator and no phone to check the app on.")
    r["device_ready"] = not r["problems"] and any(d["state"] == "device" for d in phones)
    return r


def check_web():
    r = {"ready": False, "problems": [], "advice": [], "details": []}
    try:
        import serve
        r["details"].append("this computer on the network: %s" % serve.lan_ip())
        r["ready"] = True
    except pl.PhoneError as e:
        r["problems"].append(str(e))
    r["advice"].append("The phone must be on the same Wi-Fi. Avoid public Wi-Fi. The computer's firewall may ask "
                       "to allow incoming connections for Python: allow it while serving.")
    return r


def check():
    res = {"python": "%d.%d" % sys.version_info[:2], "os": sys.platform}
    if sys.version_info < (3, 8):
        res["problems"] = ["Python 3.8 or newer is required."]
        return res
    res["ios"], res["android"], res["web"] = check_ios(), check_android(), check_web()
    return res


def human(r):
    out = ["Python %s on %s" % (r["python"], r["os"]), ""]
    labels = {"ios": "iOS app (iPhone)", "android": "Android app (experimental)", "web": "Web mode (any phone)"}
    for key in ("ios", "android", "web"):
        p = r.get(key)
        if not p:
            continue
        state = "READY" if p["ready"] else "NOT READY"
        if key in ("ios", "android") and p["ready"]:
            state += " — real phone %s" % ("ready" if p["device_ready"] else "not ready (simulator/emulator only)")
        out.append("%s: %s" % (labels[key], state))
        out += ["   " + d for d in p["details"]]
        out += ["   problem: " + x for x in p["problems"]]
        out += ["   -> " + x for x in p["advice"]]
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = check()
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else human(res))
    ok = any((res.get(k) or {}).get("ready") for k in ("ios", "android", "web"))
    sys.exit(0 if ok else 1)
