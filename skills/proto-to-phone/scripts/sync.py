#!/usr/bin/env python3
"""Adapt the prototype, build the app, install it and launch it.

Usage: sync.py [prototype.html] [--project DIR] [--platform ios|android]
               [--target auto|device|sim] [--device NAME_OR_ID] [--sim NAME] [--confirm-device]

ios: iPhone, or the iOS simulator. android (experimental): Android phone, or
the Android emulator. auto = the phone when one is reachable, the simulator /
emulator otherwise. A prototype path replaces the one remembered by the project.
Web mode has its own script: serve.py.

Gates for a real phone: the person agreed once (--confirm-device), and the
exact version (prototype + config) was checked first with shots.py.
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import android_lib as al  # noqa: E402
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


def pick_android(wanted):
    devs = [d for d in al.devices() if not d["emulator"]]
    if any(d["state"] == "unauthorized" for d in devs):
        raise pl.PhoneError("The Android phone has not allowed this computer: unlock it and accept "
                            "'Allow USB debugging'.")
    devs = [d for d in devs if d["state"] == "device" and (not wanted or wanted in (d["serial"], d["model"]))]
    if len(devs) > 1 and not wanted:
        raise pl.PhoneError("Several Android phones are connected (%s). Pass --device <serial>." %
                            ", ".join(d["serial"] for d in devs))
    return devs[0] if devs else None


def explain(err):
    text = str(err)
    hints = []
    if "No Accounts" in text or "requires a development team" in text or "No profiles for" in text:
        hints.append("Signing: sign in with an Apple ID in Xcode > Settings > Accounts, then re-run init.py --team <ID>.")
    if "Failed Registering Bundle Identifier" in text or "is not available" in text:
        hints.append("The bundle id is taken by another account. Re-run init.py --force --bundle-id <something unique>.")
    if "locked" in text.lower():
        hints.append("Unlock the phone and keep the screen on, then run again.")
    if "Developer Mode" in text:
        hints.append("Enable Settings > Privacy & Security > Developer Mode on the iPhone.")
    if "untrusted" in text.lower() or "profile has not been explicitly trusted" in text.lower():
        hints.append("On the iPhone: Settings > General > VPN & Device Management > trust the developer app.")
    if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in text:
        hints.append("An app with the same id but another signature is installed: uninstall it from the phone first.")
    if "SDK location not found" in text:
        hints.append("Set ANDROID_HOME to the Android SDK folder (see doctor.py).")
    return text + ("\n\n" + "\n".join("-> " + h for h in hints) if hints else "")


def gates(m, platform, name):
    if not pl.device_confirmed(m, platform):
        what = ("registers the app id %s in the Apple account (team %s) and installs a development build"
                % (m["bundle_id"], m["team"]) if platform == "ios"
                else "installs a debug build of %s" % m.get("android_id"))
        raise pl.PhoneError("First install on %s. It %s. Ask the person; if they agree, run again with "
                            "--confirm-device." % (name, what))


def check_verified(m, platform, page):
    if pl.verified_for(m, platform) != pl.sha256_file(page):
        raise pl.PhoneError(
            "This version (prototype + phone.config.json) has not been checked for %s. Run shots.py --platform %s, "
            "read the screenshots, fix what is wrong, then sync again." % (platform, platform))


def sync_ios(m, args):
    device = None if args.target == "sim" else pick_device(args.device)
    if args.target == "device" and not device:
        raise pl.PhoneError("No reachable iPhone. Unlock it and connect it (cable or same Wi-Fi), "
                            "or run doctor.py. Use --target sim to try the simulator.")
    kind = "device" if device else "sim"
    if kind == "device" and not m.get("team"):
        raise pl.PhoneError("This project has no signing team (simulator only). "
                            "Re-run init.py --force --team <ID> to install on an iPhone.")
    if kind == "device" and not args.confirm_device:
        gates(m, "ios", device["name"])

    page = pl.prepare(m, "ios")
    pl.save_project(m)
    if kind == "device":
        check_verified(m, "ios", page)

    app = pl.built_app(m, kind)
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

    with open(page, "rb") as a, open(os.path.join(app, "Web", "index.html"), "rb") as b:
        if a.read() != b.read():
            raise pl.PhoneError("The bundled HTML differs from Web/index.html; delete build/ and run again.")

    if kind == "device":
        pl.run(["xcrun", "devicectl", "device", "install", "app", "--device", device["udid"], app])
        pl.set_device_confirmed(m, "ios")
        pl.save_project(m)
        pl.run(["xcrun", "devicectl", "device", "process", "launch", "--device", device["udid"],
                "--terminate-existing", m["bundle_id"]])
    else:
        pl.boot_simulator(sim)
        pl.run(["xcrun", "simctl", "install", sim["udid"], app])
        pl.run(["xcrun", "simctl", "launch", "--terminate-running-process", sim["udid"], m["bundle_id"]])
        pl.run(["open", "-a", "Simulator"], check=False)
    return target_name


def sync_android(m, args):
    phone = None if args.target == "sim" else pick_android(args.device)
    if args.target == "device" and not phone:
        raise pl.PhoneError("No Android phone connected. Enable Developer options > USB debugging, connect it "
                            "and accept the prompt; or use --target sim for the emulator.")
    if phone and not args.confirm_device:
        gates(m, "android", phone["model"] or phone["serial"])
    page = pl.prepare(m, "android")
    pl.save_project(m)
    if phone:
        check_verified(m, "android", page)
    serial = phone["serial"] if phone else al.start_emulator(args.sim)
    print("sync: building the Android app")
    apk = al.build(m)
    al.install_and_launch(serial, apk, m["android_id"])
    if phone:
        pl.set_device_confirmed(m, "android")
        pl.save_project(m)
    return phone["model"] if phone else serial


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("prototype", nargs="?")
    ap.add_argument("--project")
    ap.add_argument("--platform", choices=["ios", "android"])
    ap.add_argument("--target", default="auto", choices=["auto", "device", "sim"])
    ap.add_argument("--device")
    ap.add_argument("--sim", help="iOS simulator name or Android emulator (AVD) name")
    ap.add_argument("--confirm-device", action="store_true",
                    help="the person agreed to the first install on their phone")
    args = ap.parse_args()

    try:
        m = pl.load_project(args.project)
        native = [p for p in m.get("platforms", ["ios"]) if p in ("ios", "android")]
        platform = args.platform or (native[0] if len(native) == 1 else None)
        if not platform:
            raise pl.PhoneError("This project has %s. Pass --platform ios or --platform android."
                                % (" and ".join(native) or "no app platform (web only: use serve.py)"))
        if platform not in native:
            raise pl.PhoneError("This project was not created for %s. Re-run init.py --force --platforms ..."
                                % platform)
        if args.prototype:
            m["source"] = os.path.abspath(os.path.expanduser(args.prototype))
        where = sync_ios(m, args) if platform == "ios" else sync_android(m, args)
        print("sync: %s is running on %s" % (m["name"], where))
    except pl.PhoneError as e:
        sys.exit("sync: " + explain(e))


if __name__ == "__main__":
    main()
