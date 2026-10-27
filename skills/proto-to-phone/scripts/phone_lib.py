"""Shared helpers for the proto-to-phone scripts. Python 3.8+, standard library only."""
import colorsys
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

META = ".proto-phone.json"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))


class PhoneError(Exception):
    pass


def run(cmd, check=True, capture=True, **kw):
    """Run a command; on failure raise PhoneError with the tail of its output."""
    p = subprocess.run(cmd, stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.STDOUT if capture else None,
                       universal_newlines=True, **kw)
    if check and p.returncode != 0:
        tail = "\n".join((p.stdout or "").strip().splitlines()[-25:])
        raise PhoneError("%s failed (exit %d)\n%s" % (" ".join(cmd[:3]), p.returncode, tail))
    return p


def have(tool):
    return shutil.which(tool) is not None


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "app"


def product_name(name):
    s = re.sub(r"[^A-Za-z0-9]+", " ", name).title().replace(" ", "")
    return s or "App"


def projects_root():
    return os.path.expanduser(os.environ.get("PROTO_PHONE_HOME", "~/ProtoPhone"))


def load_project(path=None):
    d = os.path.abspath(path or os.getcwd())
    meta = os.path.join(d, META)
    if not os.path.isfile(meta):
        raise PhoneError("%s is not a proto-to-phone project (no %s). Run init.py first." % (d, META))
    with open(meta, encoding="utf-8") as f:
        m = json.load(f)
    m["dir"] = d
    return m


def save_project(m):
    d = m["dir"]
    data = {k: v for k, v in m.items() if k != "dir"}
    with open(os.path.join(d, META), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Xcode, devices, simulators ──────────────────────────────────────────

def xcode_teams():
    """Signing teams Xcode knows about, from its preferences."""
    p = subprocess.run(["defaults", "export", "com.apple.dt.Xcode", "-"], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    if p.returncode != 0:
        return []
    try:
        prefs = plistlib.loads(p.stdout)
    except Exception:
        return []
    teams = []
    for entries in (prefs.get("IDEProvisioningTeamByIdentifier") or {}).values():
        for t in entries:
            if t.get("teamID"):
                teams.append({"id": t["teamID"], "name": t.get("teamName", ""),
                              "free": bool(t.get("isFreeProvisioningTeam"))})
    return teams


def physical_devices():
    """Paired iPhones/iPads. `reachable` means connected now (unlocked, cable or Wi-Fi)."""
    with tempfile.TemporaryDirectory() as tmp:  # private to this user, not a guessable /tmp name
        out = os.path.join(tmp, "devices.json")
        p = subprocess.run(["xcrun", "devicectl", "list", "devices", "--json-output", out],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0 or not os.path.isfile(out):
            return []
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
    devs = []
    for d in data.get("result", {}).get("devices", []):
        hw, dp, cp = d.get("hardwareProperties", {}), d.get("deviceProperties", {}), d.get("connectionProperties", {})
        if hw.get("reality") != "physical" or hw.get("platform") != "iOS":
            continue
        devs.append({
            "id": d.get("identifier"),
            "udid": hw.get("udid"),
            "name": dp.get("name"),
            "model": hw.get("marketingName") or hw.get("productType"),
            "os": dp.get("osVersionNumber"),
            "paired": cp.get("pairingState") == "paired",
            "reachable": cp.get("tunnelState") in ("connected", "disconnected") and cp.get("pairingState") == "paired",
            "developer_mode": dp.get("developerModeStatus"),
        })
    return devs


def simulators():
    p = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "-j"], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, universal_newlines=True)
    if p.returncode != 0:
        return []
    out = []
    for runtime, devs in json.loads(p.stdout).get("devices", {}).items():
        if "iOS" not in runtime:
            continue
        for d in devs:
            if "iPhone" in d["name"]:
                out.append({"udid": d["udid"], "name": d["name"], "state": d["state"],
                            "runtime": runtime.split(".")[-1]})
    return out


def pick_simulator(name=None):
    sims = simulators()
    if not sims:
        raise PhoneError("No iPhone simulator is installed. Xcode > Settings > Components, install an iOS runtime.")
    if name:
        hit = [s for s in sims if s["name"] == name or s["udid"] == name]
        if not hit:
            raise PhoneError("No simulator named %r. Available: %s" % (name, ", ".join(s["name"] for s in sims)))
        return hit[0]
    booted = [s for s in sims if s["state"] == "Booted"]
    if booted:
        return booted[0]
    pro = [s for s in sims if re.search(r"Pro$", s["name"])] or sims
    return sorted(pro, key=lambda s: s["runtime"])[-1]


def boot_simulator(sim):
    if sim["state"] != "Booted":
        subprocess.run(["xcrun", "simctl", "boot", sim["udid"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(["xcrun", "simctl", "bootstatus", sim["udid"], "-b"], check=False)


# ── prepare: adapt + generate the Xcode project ─────────────────────────

def prepare(m):
    """Adapt the prototype into Web/ and regenerate the Xcode project."""
    src = m.get("source")
    if not src or not os.path.isfile(src):
        raise PhoneError("Prototype not found: %s" % src)
    if not have("xcodegen"):
        raise PhoneError("xcodegen is missing. Install it with: brew install xcodegen")
    cfg = os.path.join(m["dir"], "phone.config.json")
    cmd = [sys.executable, "-I", os.path.join(HERE, "adapt.py"), src, os.path.join(m["dir"], "Web", "index.html")]
    if os.path.isfile(cfg):
        cmd += ["--config", cfg]
    p = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise PhoneError(p.stdout.strip())
    print(p.stdout.strip())
    run(["xcodegen", "generate", "--quiet"], cwd=m["dir"])


def built_app(m, kind):
    folder = "Debug-iphoneos" if kind == "device" else "Debug-iphonesimulator"
    return os.path.join(m["dir"], "build", "Build", "Products", folder, m["product"] + ".app")


# ── validation ──────────────────────────────────────────────────────────

TEAM_RE = re.compile(r"^[A-Z0-9]{10}$")
BUNDLE_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
LOGO_TYPES = (".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff", ".svg", ".pdf")
LOGO_MAX = 20 * 1024 * 1024


def check_name(name):
    name = (name or "").strip()
    if not name or len(name) > 30 or any(ord(c) < 32 for c in name):
        raise PhoneError("The app name must be 1-30 printable characters.")
    return name


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── icon ────────────────────────────────────────────────────────────────

def letter_colors(name):
    h = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:6], 16) / 0xFFFFFF
    r, g, b = colorsys.hls_to_rgb(h, 0.40, 0.55)
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255)), "#FFFFFF"


def make_icon(out, name, logo=None, background="#FFFFFF", fit="pad"):
    """Write the 1024 icon: the person's logo, or their app's initial."""
    swift = os.path.join(HERE, "icon.swift")
    if not have("swift"):
        raise PhoneError("swift is not available (comes with Xcode).")
    if not HEX_RE.match(background):
        raise PhoneError("Background must be a color like #FFFFFF.")
    if logo is None:
        bg, fg = letter_colors(name)
        run(["swift", swift, "letter", out, name[:1], bg, fg])
        return
    logo = os.path.abspath(os.path.expanduser(logo))
    ext = os.path.splitext(logo)[1].lower()
    if not os.path.isfile(logo) or ext not in LOGO_TYPES:
        raise PhoneError("The logo must be a %s file." % ", ".join(LOGO_TYPES))
    if os.path.getsize(logo) > LOGO_MAX:
        raise PhoneError("The logo file is larger than 20 MB.")
    with tempfile.TemporaryDirectory() as tmp:
        src = logo
        if ext in (".svg", ".pdf"):
            # Quick Look renders vector files to a bitmap without running a browser.
            run(["qlmanage", "-t", "-s", "1024", "-o", tmp, logo])
            src = os.path.join(tmp, os.path.basename(logo) + ".png")
            if not os.path.isfile(src):
                raise PhoneError("Could not render %s; export it as PNG." % os.path.basename(logo))
        run(["swift", swift, "logo", out, src, background, "fill" if fit == "fill" else "pad"])
