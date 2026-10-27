#!/usr/bin/env python3
"""Run the prototype in the simulator, drive it, and save screenshots to look at.

Usage: shots.py [--project DIR] [--sim NAME] [--out DIR] [--steps "STEP;STEP;..."]

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
import phone_lib as pl  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--project")
    ap.add_argument("--sim")
    ap.add_argument("--out")
    ap.add_argument("--steps", default="shot:launch")
    args = ap.parse_args()
    try:
        m = pl.load_project(args.project)
        out = os.path.abspath(args.out or os.path.join(m["dir"], "shots"))
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        sim = pl.pick_simulator(args.sim)
        pl.boot_simulator(sim)
        pl.prepare(m)
        shutil.rmtree(pl.built_app(m, "sim"), ignore_errors=True)  # see sync.py: Web is a folder reference
        env = dict(os.environ, TEST_RUNNER_PHONE_STEPS=args.steps, TEST_RUNNER_PHONE_SHOTS=out)
        pl.run(["xcodebuild", "test", "-project", "App.xcodeproj", "-scheme", "App",
                "-destination", "platform=iOS Simulator,id=%s" % sim["udid"], "-derivedDataPath", "build",
                "-only-testing:AppUITests/ShellUITests/testSteps", "-quiet"], cwd=m["dir"], env=env)
        shots = sorted(f for f in os.listdir(out) if f.endswith(".png"))
        if not shots:
            raise pl.PhoneError("The run finished but saved no screenshots.")
        # What was looked at: sync.py refuses to install on an iPhone a build
        # that does not match this (see the gate there).
        m["verified"] = {"sha256": pl.sha256_file(os.path.join(m["dir"], "Web", "index.html")),
                         "shots": out, "steps": args.steps}
        pl.save_project(m)
        print("shots: %d screenshot(s) in %s" % (len(shots), out))
        print("shots: read every screenshot before calling this version checked.")
        for f in shots:
            print("  " + os.path.join(out, f))
    except pl.PhoneError as e:
        sys.exit("shots: %s" % e)


if __name__ == "__main__":
    main()
