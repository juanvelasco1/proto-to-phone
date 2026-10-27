# Setup and troubleshooting

## Signing (real iPhone)

| Account | Works | Limits |
|---|---|---|
| Free Apple ID | Yes | The app expires after 7 days (run `sync.py` again), at most 3 apps at a time, bundle id must be unique |
| Paid Apple Developer Program | Yes | 1 year, no app limit |
| None | Simulator only | `init.py --team none` |

Sign in once: Xcode → Settings → Accounts → add the Apple ID. `init.py` reads the team from there; with
several teams it asks for `--team <ID>`. The bundle id is `phone.<team>.<slug>`, unique per team; override with
`--bundle-id`.

## The iPhone

1. Connect by cable once, unlock, tap **Trust** on the phone.
2. Settings → Privacy & Security → **Developer Mode** → on (the phone restarts).
3. Keep it unlocked while `sync.py` runs. After the first pairing, the same Wi-Fi is enough.
4. Free account, first launch: Settings → General → VPN & Device Management → trust the developer.

## Android (experimental)

1. Install Android Studio (it brings Java and the SDK) and Gradle 8.9+. Set `ANDROID_HOME` to the SDK folder
   if `doctor.py` does not find it.
2. Create an emulator: Android Studio → Device Manager.
3. For a real phone: Settings → About phone → tap Build number 7 times; then Developer options → USB debugging
   on; connect it and accept "Allow USB debugging".
4. Debug builds are signed with the computer's own debug key: no account, no expiry.

## Web mode

1. Computer and phone on the same Wi-Fi (not public Wi-Fi; some office networks block devices from seeing
   each other).
2. The firewall may ask to allow Python to accept incoming connections: allow it while serving.
3. On the phone, open the link and add it to the home screen to hide the browser bars.

## Errors

| Message | Meaning | Do |
|---|---|---|
| `xcodegen is missing` | Not installed | `brew install xcodegen` |
| `Full Xcode is required` | Only Command Line Tools | Install Xcode, open it once, `sudo xcode-select -s /Applications/Xcode.app` |
| `No Accounts` / `requires a development team` / `No profiles for` | No signing team | Add the Apple ID in Xcode; `init.py --force --team <ID>` |
| `Failed Registering Bundle Identifier` | Bundle id taken by another account | `init.py --force --bundle-id <unique id>` |
| `No reachable iPhone` | Locked, asleep, or not paired | Unlock, connect, run `doctor.py`; or `--target sim` |
| `Developer Mode` | Disabled on the phone | Enable it (see above) |
| `untrusted developer` on the phone | Free account, first run | Trust it in VPN & Device Management |
| `The bundled HTML differs from Web/index.html` | Stale build copy | Delete the project's `build/` and run again |
| `First install on an iPhone ... --confirm-device` | Gate: the person has not agreed yet | Explain (app id registered, development build), ask, then add `--confirm-device` |
| `has not been checked in the simulator` | Gate: this prototype + config was not run through `shots.py` | Run `shots.py`, read the screenshots, then sync |
| `The app name must be 1-30 printable characters` | Name rejected | Shorter name |
| `The logo must be a ... file` | Unsupported logo | PNG, JPG, HEIC, TIFF, SVG or PDF, under 20 MB |
| `is not empty and is not a proto-to-phone project` | `--dir` points at an existing folder | Choose a new or empty folder |
| `has not been checked for android` | Gate: run `shots.py --platform android` first | Check on the emulator, or on the phone with `--device --confirm-device` |
| `The Android phone has not allowed this computer` | USB debugging prompt not accepted | Unlock the phone, accept the prompt |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Same app id, other signature | Uninstall the app from the phone first |
| `No local network found` | The computer is offline | Connect to the same Wi-Fi as the phone |
| The phone cannot open the link | Different network, client isolation, or firewall | Same Wi-Fi; allow Python in the firewall; try another network |
| `expected one anchor for ...` | A `patches` anchor moved | Update that patch in `phone.config.json` |
| Simulator test saves no screenshots | The steps never reached `shot:` | Run `shots.py` with only `shot:launch` first |
| App stops opening after 7 days | Free account expiry | Run `sync.py` again |

## Where things are

```
~/ProtoPhone/<slug>/
  .proto-phone.json      name, bundle id, team, prototype path, checked version (do not share)
  phone.config.json      the adaptation (edit this)
  Web/index.html         the adapted copy bundled into the app (generated)
  App/                   native shell (Swift) and the icon; rarely edited
  shots/                 screenshots from shots.py
  build/                 Xcode output (safe to delete)
  android/               Android app (Kotlin), when the project has android
  site/                  web mode's adapted page (generated)
  icon.png               the icon, shared by every platform
```
