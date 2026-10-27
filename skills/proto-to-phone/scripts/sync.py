#!/usr/bin/env python3
"""Adapt the prototype, build the app, install it and launch it.

Usage: sync.py [prototype.html] [--project DIR] [--target auto|device|sim]
               [--device NAME_OR_UDID] [--sim NAME]

auto = the iPhone when one is reachable (unlocked), the simulator otherwise.
A prototype path replaces the one remembered by the project.
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phone_lib as pl  # noqa: E402


def pick_device(wanted):
    devs = [d for d in pl.physical_devices() if d["reachable"]]
    if wanted:
        devs = [d for d in devs if wanted in (d["name"], d["udid"], d["id"])]
    if not devs:
        return None
    if len(devs) > 1 and not wanted:
        raise pl.PhoneError("Several iPhones are reachable (%s). Pass --device <name>." %
                            ", ".join(d["name"] for d in devs))
    return devs[0]


def explain(err, target):
    text = str(err)
    hints = []
    if "No Accounts" in text or "requires a development team" in text or "No profiles for" in text:
        hints.append("Signing: sign in with an Apple ID in Xcode > Settings > Accounts, then re-run init.py --team <ID>.")
    if "Failed Registering Bundle Identifier" in text or "is not available" in text:
        hints.append("The bundle id is taken by another account. Re-run init.py --force --bundle-id <something unique>.")
    if "locked" in text.lower():
        hints.append("Unlock the iPhone and keep the screen on, then run again.")
    if "Developer Mode" in text:
        hints.append("Enable Settings > Privacy & Security > Developer Mode on the iPhone.")
    if "untrusted" in text.lower() or "profile has not been explicitly trusted" in text.lower():
        hints.append("On the iPhone: Settings > General > VPN & Device Management > trust the developer app.")
    return text + ("\n\n" + "\n".join("-> " + h for h in hints) if hints else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prototype", nargs="?")
    ap.add_argument("--project")
    ap.add_argument("--target", default="auto", choices=["auto", "device", "sim"])
    ap.add_argument("--device")
    ap.add_argument("--sim")
    ap.add_argument("--confirm-device", action="store_true",
                    help="the person agreed to the first install on their iPhone (registers the app id)")
    args = ap.parse_args()

    try:
        m = pl.load_project(args.project)
        if args.prototype:
            m["source"] = os.path.abspath(os.path.expanduser(args.prototype))
        device = None if args.target == "sim" else pick_device(args.device)
        if args.target == "device" and not device:
            raise pl.PhoneError("No reachable iPhone. Unlock it and connect it (cable or same Wi-Fi), "
                                "or run doctor.py. Use --target sim to try the simulator.")
        kind = "device" if device else "sim"
        if kind == "device" and not m.get("team"):
            raise pl.PhoneError("This project has no signing team (simulator only). "
                                "Re-run init.py --force --team <ID> to install on an iPhone.")

        if kind == "device" and not m.get("device_confirmed") and not args.confirm_device:
            raise pl.PhoneError(
                "First install on an iPhone. It registers the app id %s in the Apple account (team %s) and installs "
                "a development build on %s. Ask the person; if they agree, run again with --confirm-device."
                % (m["bundle_id"], m["team"], device["name"]))

        pl.prepare(m)
        pl.save_project(m)

        if kind == "device":
            verified = (m.get("verified") or {}).get("sha256")
            if verified != pl.sha256_file(os.path.join(m["dir"], "Web", "index.html")):
                raise pl.PhoneError(
                    "This version (prototype + phone.config.json) has not been checked in the simulator. "
                    "Run shots.py, read the screenshots, fix what is wrong, then sync again.")

        app = pl.built_app(m, "device" if kind == "device" else "sim")
        # Web is a folder reference: Xcode does not notice in-place edits, so the
        # copied bundle is dropped and always rebuilt from the current files.
        shutil.rmtree(app, ignore_errors=True)

        build = ["xcodebuild", "-project", "App.xcodeproj", "-scheme", "App", "-configuration", "Debug",
                 "-derivedDataPath", "build", "-quiet", "build"]
        if kind == "device":
            build += ["-destination", "id=%s" % device["udid"], "-allowProvisioningUpdates"]
            target_name = device["name"]
        else:
            sim = pl.pick_simulator(args.sim)
            build += ["-destination", "platform=iOS Simulator,id=%s" % sim["udid"]]
            target_name = sim["name"]
        print("sync: building for %s (%s)" % (target_name, "iPhone" if kind == "device" else "simulator"))
        pl.run(build, cwd=m["dir"])

        built = os.path.join(app, "Web", "index.html")
        with open(os.path.join(m["dir"], "Web", "index.html"), "rb") as a, open(built, "rb") as b:
            if a.read() != b.read():
                raise pl.PhoneError("The bundled HTML differs from Web/index.html; delete build/ and run again.")

        if kind == "device":
            pl.run(["xcrun", "devicectl", "device", "install", "app", "--device", device["udid"], app])
            m["device_confirmed"] = True
            pl.save_project(m)
            pl.run(["xcrun", "devicectl", "device", "process", "launch", "--device", device["udid"],
                    "--terminate-existing", m["bundle_id"]])
        else:
            pl.boot_simulator(sim)
            pl.run(["xcrun", "simctl", "install", sim["udid"], app])
            pl.run(["xcrun", "simctl", "launch", "--terminate-running-process", sim["udid"], m["bundle_id"]])
            pl.run(["open", "-a", "Simulator"], check=False)
        print("sync: %s is running on %s" % (m["name"], target_name))
    except pl.PhoneError as e:
        sys.exit("sync: " + explain(e, args.target))


if __name__ == "__main__":
    main()
