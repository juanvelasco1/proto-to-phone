"""Android helpers: SDK, adb, emulator, Gradle. Python 3.8+, standard library only.
Works on macOS, Windows and Linux. Every command runs without a shell."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

import phone_lib as pl

EXE = ".exe" if os.name == "nt" else ""
ACTIVITY = "app.protophone.shell.MainActivity"


def sdk_root():
    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(var) and os.path.isdir(os.environ[var]):
            return os.environ[var]
    for p in (os.path.expanduser("~/Library/Android/sdk"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk"),
              os.path.expanduser("~/Android/Sdk")):
        if p and os.path.isdir(p):
            return p
    return None


def tool(name):
    """adb or emulator: from the SDK first, then PATH."""
    sub = {"adb": "platform-tools", "emulator": "emulator"}[name]
    root = sdk_root()
    if root:
        p = os.path.join(root, sub, name + EXE)
        if os.path.isfile(p):
            return p
    return shutil.which(name)


def gradle():
    return shutil.which("gradle")


def java_major():
    p = subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       universal_newlines=True) if shutil.which("java") else None
    if not p or p.returncode != 0:
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', p.stdout)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2)) if major == 1 and m.group(2) else major


def gradle_version():
    g = gradle()
    if not g:
        return None
    p = subprocess.run([g, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    m = re.search(r"Gradle (\d+)\.(\d+)", p.stdout or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_devices(text):
    """`adb devices -l` output -> [{serial, state, model, emulator}]."""
    out = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        model = re.search(r"\bmodel:(\S+)", line)
        out.append({"serial": parts[0], "state": parts[1], "model": model.group(1).replace("_", " ") if model else "",
                    "emulator": parts[0].startswith("emulator-")})
    return out


def devices():
    adb = tool("adb")
    if not adb:
        return []
    p = subprocess.run([adb, "devices", "-l"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
    return parse_devices(p.stdout) if p.returncode == 0 else []


def avds():
    emu = tool("emulator")
    if not emu:
        return []
    p = subprocess.run([emu, "-list-avds"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True)
    return [l.strip() for l in p.stdout.splitlines() if l.strip() and not l.startswith("INFO")]


def adb(serial, *args, binary=False, check=True):
    cmd = [tool("adb"), "-s", serial] + list(args)
    if binary:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and p.returncode != 0:
            raise pl.PhoneError("adb %s failed: %s" % (" ".join(args[:2]), p.stderr.decode("utf-8", "replace")[-300:]))
        return p.stdout
    return pl.run(cmd, check=check).stdout


def start_emulator(name=None):
    """Boot an Android Virtual Device and wait for it. Returns its serial."""
    running = [d for d in devices() if d["emulator"] and d["state"] == "device"]
    if running:
        return running[0]["serial"]
    names = avds()
    if not names:
        raise pl.PhoneError("No Android emulator (AVD). Create one in Android Studio > Device Manager.")
    avd = name if name in names else names[0]
    subprocess.Popen([tool("emulator"), "-avd", avd, "-no-boot-anim"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    for _ in range(180):
        time.sleep(2)
        emus = [d for d in devices() if d["emulator"] and d["state"] == "device"]
        if emus and adb(emus[0]["serial"], "shell", "getprop", "sys.boot_completed", check=False).strip() == "1":
            return emus[0]["serial"]
    raise pl.PhoneError("The Android emulator did not finish booting in 6 minutes.")


def apk_path(m):
    return os.path.join(m["dir"], "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")


def build(m):
    g = gradle()
    if not g:
        raise pl.PhoneError("Gradle 8.9+ is needed to build the Android app (see doctor.py).")
    pl.run([g, "--quiet", "--no-daemon", "assembleDebug"], cwd=os.path.join(m["dir"], "android"))
    apk = apk_path(m)
    if not os.path.isfile(apk):
        raise pl.PhoneError("The build finished but produced no APK.")
    return apk


def install_and_launch(serial, apk, package, reset=False):
    adb(serial, "install", "-r", apk)
    if reset:
        adb(serial, "shell", "pm", "clear", package, check=False)
    adb(serial, "shell", "am", "force-stop", package, check=False)
    adb(serial, "shell", "am", "start", "-n", "%s/%s" % (package, ACTIVITY))


def screen_size(serial):
    text = adb(serial, "shell", "wm", "size")
    sizes = re.findall(r"(\d+)x(\d+)", text)
    if not sizes:
        raise pl.PhoneError("Could not read the screen size.")
    w, h = sizes[-1]  # an override size, if any, comes last
    return int(w), int(h)


def screenshot(serial, out):
    data = adb(serial, "exec-out", "screencap", "-p", binary=True)
    if not data.startswith(b"\x89PNG"):
        raise pl.PhoneError("The screenshot is not a PNG (is the screen on and unlocked?).")
    with open(out, "wb") as f:
        f.write(data)


def find_label(serial, label):
    """Center of the on-screen element whose text or accessibility label is `label`."""
    adb(serial, "shell", "uiautomator", "dump", "/sdcard/proto-phone-ui.xml", check=False)
    xml = adb(serial, "exec-out", "cat", "/sdcard/proto-phone-ui.xml", binary=True, check=False)
    adb(serial, "shell", "rm", "-f", "/sdcard/proto-phone-ui.xml", check=False)
    try:
        tree = ET.fromstring(xml)
    except ET.ParseError:
        return None
    for node in tree.iter("node"):
        if label in (node.get("text"), node.get("content-desc")):
            b = re.findall(r"\d+", node.get("bounds", ""))
            if len(b) == 4:
                x1, y1, x2, y2 = map(int, b)
                return (x1 + x2) // 2, (y1 + y2) // 2
    return None


def run_steps(serial, steps, out):
    """Same step language as the iOS UI test: shot, tap, type, swipedown, wait."""
    w, h = screen_size(serial)
    for step in [s.strip() for s in steps.split(";") if s.strip()]:
        kind, _, arg = step.partition(":")
        if kind == "shot":
            screenshot(serial, os.path.join(out, (arg or "shot") + ".png"))
        elif kind == "wait":
            time.sleep(float(arg or 1))
        elif kind == "swipedown":
            adb(serial, "shell", "input", "swipe", str(w // 2), str(h // 3), str(w // 2), str(h * 9 // 10), "250")
        elif kind == "type":
            if not re.fullmatch(r"[A-Za-z0-9 .,]*", arg):
                raise pl.PhoneError("type: only letters, digits, spaces, dots and commas on Android: %r" % arg)
            adb(serial, "shell", "input", "text", arg.replace(" ", "%s"))
        elif kind == "tap" and arg.startswith("@"):
            pos = find_label(serial, arg[1:])
            if not pos:
                raise pl.PhoneError("No control labelled %r on screen." % arg[1:])
            adb(serial, "shell", "input", "tap", str(pos[0]), str(pos[1]))
        elif kind == "tap":
            try:
                fx, fy = [float(v) for v in arg.split(",")]
            except ValueError:
                raise pl.PhoneError("Bad tap step: %s" % step)
            adb(serial, "shell", "input", "tap", str(int(fx * w)), str(int(fy * h)))
        else:
            raise pl.PhoneError("Unknown step: %s" % step)


def android_id(bundle_id):
    """An Android applicationId: dot-separated segments that start with a letter; letters, digits, _."""
    segs = []
    for seg in bundle_id.split("."):
        seg = re.sub(r"[^A-Za-z0-9_]", "_", seg)
        if not seg or not seg[0].isalpha():
            seg = "a" + seg
        segs.append(seg)
    return ".".join(segs if len(segs) > 1 else ["app"] + segs)


def string_resource(text):
    """Escape a value for res/values/strings.xml."""
    from xml.sax.saxutils import escape
    t = escape(text).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    return "\\" + t if t[:1] in ("@", "?") else t
