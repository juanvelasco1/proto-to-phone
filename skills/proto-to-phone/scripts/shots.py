#!/usr/bin/env python3
"""Run the prototype in the simulator, drive it, and save screenshots to look at.

Usage: shots.py [--project DIR] [--platform ios|android] [--sim NAME] [--device SERIAL]
                [--confirm-device] [--out DIR] [--steps "STEP;STEP;..."]

ios: the iOS simulator. android: the Android emulator, or a connected Android
phone with --device (it installs there, so it needs --confirm-device).
web (macOS, project with ios): serves the web version for a few minutes, opens
it in Safari in the iOS simulator and drives Safari (needs --confirm-network).

Steps (default "shot:launch"):
  shot:NAME       save NAME.png
  tap:0.5,0.9     tap at a fraction of the screen (x,y from the top left)
  tap:@Label      tap the control whose accessibility label is Label
  type:text       press the keys of a text (the field must already be focused)
  swipedown       swipe from the middle downwards
  wait:2          wait 2 seconds
Example: --steps "shot:home;tap:@New chat;wait:1;shot:chat;tap:0.4,0.88;wait:2;shot:keyboard"
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import android_lib as al  # noqa: E402
import phone_lib as pl  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--platform", choices=["ios", "android", "web"])
    ap.add_argument("--confirm-network", action="store_true", help="web: the person agreed to serve on the local network")
    ap.add_argument("--sim")
    ap.add_argument("--device", help="Android: run on this connected phone instead of the emulator")
    ap.add_argument("--confirm-device", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--steps", default="shot:launch")
    args = ap.parse_args()
    try:
        m = pl.load_project(args.project)
        out = os.path.abspath(args.out or os.path.join(m["dir"], "shots"))
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        platforms = m.get("platforms", ["ios"])
        native = [p for p in platforms if p in ("ios", "android")]
        platform = args.platform or (native[0] if len(native) == 1 else None)
        if platform not in platforms:
            raise pl.PhoneError("Pass --platform with one of this project's platforms: %s." % ", ".join(platforms))
        if platform == "web":
            if sys.platform != "darwin" or "ios" not in platforms:
                raise pl.PhoneError("Checking web mode here needs a Mac and a project with the ios platform. "
                                    "Otherwise run serve.py and check it on the phone itself.")
            if not args.confirm_network:
                raise pl.PhoneError("This serves the prototype on the local network for a few minutes. Ask the "
                                    "person; if they agree, run again with --confirm-network.")
            import serve
            import threading
            sim = pl.pick_simulator(args.sim)
            pl.boot_simulator(sim)
            server, url = serve.start_server(m, 10, log=lambda line: None)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                pl.prepare(m, "ios")  # the UI test runner is part of the iOS project
                pl.run(["xcrun", "simctl", "openurl", sim["udid"], url])
                env = dict(os.environ, TEST_RUNNER_PHONE_STEPS="wait:3;" + args.steps,
                           TEST_RUNNER_PHONE_SHOTS=out, TEST_RUNNER_PHONE_APP="com.apple.mobilesafari")
                pl.run(["xcodebuild", "test", "-project", "App.xcodeproj", "-scheme", "App",
                        "-destination", "platform=iOS Simulator,id=%s" % sim["udid"], "-derivedDataPath", "build",
                        "-only-testing:AppUITests/ShellUITests/testSteps", "-quiet"], cwd=m["dir"], env=env)
            finally:
                server.shutdown()
                server.server_close()
            page = os.path.join(m["dir"], "site", "index.html")
        elif platform == "ios":
            sim = pl.pick_simulator(args.sim)
            pl.boot_simulator(sim)
            page = pl.prepare(m, "ios")
            shutil.rmtree(pl.built_app(m, "sim"), ignore_errors=True)  # see sync.py: Web is a folder reference
            env = dict(os.environ, TEST_RUNNER_PHONE_STEPS=args.steps, TEST_RUNNER_PHONE_SHOTS=out)
            pl.run(["xcodebuild", "test", "-project", "App.xcodeproj", "-scheme", "App",
                    "-destination", "platform=iOS Simulator,id=%s" % sim["udid"], "-derivedDataPath", "build",
                    "-only-testing:AppUITests/ShellUITests/testSteps", "-quiet"], cwd=m["dir"], env=env)
        else:
            if args.device:
                if not (args.confirm_device or pl.device_confirmed(m, "android")):
                    raise pl.PhoneError("Checking on a real Android phone installs the app there. Ask the person; "
                                        "if they agree, run again with --confirm-device.")
                serial = args.device
            else:
                serial = al.start_emulator(args.sim)
            page = pl.prepare(m, "android")
            apk = al.build(m)
            al.install_and_launch(serial, apk, m["android_id"], reset=True)
            import time
            time.sleep(3)
            al.run_steps(serial, args.steps, out)
            if args.device:
                pl.set_device_confirmed(m, "android")
        shots = sorted(f for f in os.listdir(out) if f.endswith(".png"))
        if not shots:
            raise pl.PhoneError("The run finished but saved no screenshots.")
        # What was looked at: sync.py refuses to install on an iPhone a build
        # that does not match this (see the gate there).
        pl.set_verified(m, platform, {"sha256": pl.sha256_file(page), "shots": out, "steps": args.steps})
        pl.save_project(m)
        print("shots: %d screenshot(s) in %s" % (len(shots), out))
        print("shots: read every screenshot before calling this version checked.")
        for f in shots:
            print("  " + os.path.join(out, f))
    except pl.PhoneError as e:
        sys.exit("shots: %s" % e)


if __name__ == "__main__":
    main()
