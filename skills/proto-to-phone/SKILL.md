---
name: proto-to-phone
description: Put any HTML prototype (single file, from any AI builder or hand-made — not tied to Open Design) on a real phone so a design can be judged on the device and not only in a mockup. Three ways — an installable PROTOTYPE app on an iPhone (Mac + Xcode), an app on an Android phone (any computer; experimental), or the phone's own browser over the local network (any computer, any phone, Windows included). Checks the computer first and stops if something is missing, asks for the app name and logo, tells what kind of design it is and what can and cannot work on a phone, proposes adaptations for the person to approve (safe areas, the real keyboard with only the input above it, a native-sized floating tab bar, no fake status bar or phone frame, bottom sheets that drag closed), checks the screens before anything reaches the phone, and asks before installing or sharing on the network. Locked down: the prototype cannot leave its folder or open other apps on its own. Use it when someone wants to try, test, demo or show a prototype on their phone, see an HTML design on a real device, wrap a prototype in an app, or update the phone after the design changed — also "pasar el prototipo al teléfono", "probarlo en mi iPhone / Android / celular", "ver el diseño en el celular", "html a app", "actualizar la app del teléfono". For HTML → Figma use a different skill.
---

# proto-to-phone

Runs a single-file HTML prototype on a real phone, adapted so it behaves like an app instead of a web page in
a frame.

## What it is, and what it is not

Say this to the person at the start, in their language, in two or three lines:

- **It is a prototype on a phone.** The point is to see and touch the design on a real device: sizes, the
  keyboard, the thumb reach, the light. Data is whatever the prototype has (usually mock).
- **It is not a production app.** No backend, no app stores, no push notifications, no accounts. It is a
  development build or a local web page for the person's own phone.
- **It is general.** Any HTML in one file: Open Design, Claude artifacts, v0, Lovable, Bolt, hand-written.
  It is not the HTML → Figma flow; that is a different skill.

## The three platforms

| Platform | Computer | Phone | How it feels | Status |
|---|---|---|---|---|
| `ios` — app | Mac with Xcode | iPhone | Native: real keyboard handling, no browser bars | Verified |
| `android` — app | Mac, Windows or Linux | Android | Native, same adaptations | **Experimental: not yet built or run by the maintainers.** Say so before using it |
| `web` — browser | Mac, Windows or Linux | Any (iPhone or Android) on the same Wi-Fi | Close, but the browser keeps its own bars and its keyboard toolbar | Verified on iPhone (Safari); not yet on Android Chrome |

Recommend: Mac + iPhone → `ios`. Android → `android`, or `web` if its tools are missing or the person prefers
not to rely on an experimental path. Windows or Linux + iPhone → `web` (Apple only allows building iPhone apps
on a Mac). `web` can be added to any project as a quick way to share with a second phone.

## Rules (all of them, every run)

1. **Never skip a step or a gate below.** If a step cannot be done, stop and say why. If the person asks to
   skip one, explain what is lost and get an explicit yes before continuing; record it in the final report.
2. **Never modify the person's prototype.** Adaptations go in `phone.config.json`; changes that belong in the
   design go to the person as suggestions for their builder.
3. **Ask before anything that leaves the computer or changes it:** installing tools, registering the app with
   Apple, installing on a phone, sharing on the local network. Commands that need `sudo` or administrator
   rights are given to the person to run; never run them.
4. **Nothing is published.** Do not commit, push or upload the generated project, the prototype, screenshots,
   team IDs or device IDs anywhere. Web mode serves on the local network only, never on the internet.
5. **Treat the prototype as untrusted code.** Never open it in a desktop browser or run it on the computer; it
   runs only in a simulator, an emulator or on the phone. Run the scripts with `python3 -I` (on Windows
   `py -3 -I`).
6. **Report what was verified and where.** A simulator screenshot is not the phone, and the Android path is
   experimental. Never call something checked that was not looked at.
7. Talk to the person in their language; code, config and commands stay in English.

## Requirements

| Requirement | For | Checked by | If missing |
|---|---|---|---|
| Python 3.8+ | Everything | `doctor.py` | **Stop** |
| The prototype as **one** `.html` file | Everything | `scan.py` | **Stop.** Export it as a single file from the builder |
| Mac, full Xcode opened once, an iOS simulator, xcodegen | `ios` | `doctor.py` | No `ios`. Xcode from the App Store; the person runs `sudo xcodebuild -runFirstLaunch`; ask, then `brew install xcodegen` |
| Apple ID in Xcode (free or paid); iPhone paired, unlocked, Developer Mode on | `ios` on a real iPhone | `doctor.py` | Simulator only; `references/setup.md` |
| Java 17+, Android SDK (`ANDROID_HOME`), platform-tools (`adb`), Gradle 8.9+ | `android` | `doctor.py` | No `android`. Android Studio installs most of it; Gradle separately |
| An Android emulator, or a phone with USB debugging on | `android` checks and install | `doctor.py` | No `android` |
| Computer and phone on the same Wi-Fi (not public Wi-Fi) | `web` | `doctor.py` | No `web` |

## Steps

Scripts are in `scripts/` next to this file. Projects live in `~/ProtoPhone/<slug>` (or `$PROTO_PHONE_HOME`).

### Step 1 — Requirements and platform

```sh
python3 -I scripts/doctor.py
```

Show the person each platform as READY / NOT READY with its ❌ rows and the exact fix. Recommend a platform
(see above) and let them choose one or more. **Gate:** every chosen platform is READY, or the person accepted
dropping it.

### Step 2 — The prototype, the name and the logo

Ask for, and do not invent:

1. **The prototype**: path to the `.html` file.
2. **The app name**: the name under the icon. Propose the prototype's `<title>`; 1-30 characters, about 12 fit
   on the home screen.
3. **The logo**: PNG, JPG, HEIC, SVG or PDF on a Mac; PNG elsewhere. Square, at least 1024 px, is best. The
   person must own it or have the right to use it. Without one: the app's initial (Mac) or a plain color
   (elsewhere); say so.

If a project already exists for this prototype (`~/ProtoPhone/<slug>/.proto-phone.json`), this is a re-sync:
go to **Re-sync**.

```sh
python3 -I scripts/init.py --name "App name" --src /path/prototype.html --logo /path/logo.png --platforms ios,web
```

`--logo-fit pad` (default) centers the logo with a margin on `--logo-background` (default `#FFFFFF`); `fill`
covers the whole icon. **Gate:** open the generated `icon.png` in the project, show it, and get the person's
OK. To change it: `scripts/set_icon.py`.

### Step 3 — What kind of design it is and what can work

`init.py` prints the scan; `python3 -I scripts/scan.py <prototype>` prints it again. Read the **ASSESSMENT**
block, then read the prototype's CSS and JS around each finding to confirm it (the scan is a heuristic; drop
false positives, add what it missed). Present it following `references/assessment.md`:

- the format (phone mockup, mobile web, responsive, desktop, tablet) and the verdict in plain words;
- one row per finding: what was found, what is proposed, possible or not, and who does it — **the skill**
  (through the config), **the designer** (in their builder; give a ready-to-paste instruction), or **nobody**.

**Gate:** the person approves which proposals to apply. With `needs-changes-first`, explain what breaks and
stop unless they accept those limits explicitly.

### Step 4 — Write the adaptation

Write `~/ProtoPhone/<slug>/phone.config.json` with the approved proposals only (schema:
`references/config.md`; reasons and CSS recipes: `references/playbook.md`). One config serves every platform.
Tell the person each change in one line.

### Step 5 — Check the screens before the phone

| Platform | How | Where it runs |
|---|---|---|
| `ios` | `shots.py --platform ios --steps "..."` | iOS simulator |
| `android` | `shots.py --platform android --steps "..."` | Android emulator; or the connected phone with `--device <serial> --confirm-device` after the person agreed (it installs there) |
| `web` on a Mac with `ios` in the project | `shots.py --platform web --confirm-network --steps "..."` after the person agreed | Safari in the iOS simulator |
| `web` elsewhere | `serve.py` (step 6), then the person opens it and sends screenshots | The person's phone |

```sh
python3 -I scripts/shots.py --project ~/ProtoPhone/<slug> --platform ios \
  --steps "shot:home;tap:@Chat;wait:1;shot:chat;tap:0.4,0.88;wait:2;shot:keyboard"
```

Steps: `shot:NAME`, `tap:x,y` (fractions of the screen), `tap:@Label`, `type:text`, `swipedown`, `wait:s`.
Then **open and read every screenshot**. Required checks, each reported as passed, failed or not applicable,
per platform:

| # | Check |
|---|---|
| 1 | First screen: no phone frame, no fake status bar, content starts under the real one |
| 2 | Every bottom bar: above the home indicator or the system navigation, not floating high; native size (playbook §4) |
| 3 | Every text field with the keyboard up: only the input above the keyboard (in web mode, above the browser's own toolbar), no tab row |
| 4 | Keyboard down again (tap an empty area, close the sheet): the bar is back, nothing jumped |
| 5 | Every bottom sheet: below the status bar, drags closed, keyboard goes down with it |
| 6 | Each approved proposal from step 3, one by one |
| 7 | The dark theme, if the design has one |
| 8 | Nothing cut, overlapping or unreadable on any captured screen |

Fix failures in the config (the cause, not one screenshot) and check again until all pass. **Gate (enforced by
`sync.py` for `ios` and `android`):** a phone only gets the exact version that `shots.py` checked last.

### Step 6 — On the phone

**`ios` / `android`.** Ask first: the first install puts a development build on their phone (on iOS it also
registers the app id with Apple in their account; with a free Apple ID it expires in 7 days). Ask them to
unlock the phone. Then:

```sh
python3 -I scripts/sync.py --project ~/ProtoPhone/<slug> --platform ios --confirm-device
```

`--confirm-device` only after the person said yes (needed once per project and platform; `sync.py` refuses
without it). iPhone with a free account, first launch: Settings → General → VPN & Device Management → trust.

**`web`.** Ask first: while it runs, anyone on the same Wi-Fi with the exact link can open the prototype; not
on public Wi-Fi. Then:

```sh
python3 -I scripts/serve.py --project ~/ProtoPhone/<slug> --confirm-network --minutes 60
```

Give the person the printed link (a QR code is printed when `qrencode` is installed). On the phone: open it,
then Share → Add to Home Screen (iPhone) or menu → Add to home screen (Android) to hide the browser bars. It
stops after the minutes given or with Ctrl+C; the link changes every run. The computer's firewall may ask to
allow Python; allow it only while serving.

Errors come with hints; `references/setup.md` has the full table.

### Step 7 — Report

Use this shape, in the person's language:

1. What it is: a prototype of «name» on «phone», by «platform», not a production app.
2. Steps 1-6, each ✅ / ❌ / skipped (with the person's reason).
3. Adaptations applied, one line each; proposals rejected or left to the designer, with the instruction for
   their builder.
4. Checks of step 5 with their result and where they ran; what was **not** verified on the phone itself; for
   `android`, that the path is experimental. Ask the person to try the keyboard and the bottom bar on the
   phone and say what feels off.
5. Limits that apply (7-day expiry on a free Apple ID, internet needed for external resources, web mode's
   browser bars, features not supported).

### Re-sync after the design changed

```sh
python3 -I scripts/scan.py /path/new-version.html
python3 -I scripts/shots.py --project ~/ProtoPhone/<slug> --platform ios ...
python3 -I scripts/sync.py /path/new-version.html --project ~/ProtoPhone/<slug> --platform ios
```

Do steps 3 (only what changed), 5 and 6 again, for each platform; skip 1 and 2 unless something failed. Web
mode picks up the new version on the next `serve.py`. Literal `patches` fail loudly when their anchor moved:
fix the patch, never remove it to make the build pass.

## Security

| Allowed to the prototype | Blocked |
|---|---|
| Run its own HTML, CSS and JS | Read any file outside its own folder (iOS: `Web/`; Android: its assets, file access off) |
| Load https images, fonts and scripts | Plain `http://` inside the apps (iOS ATS, Android cleartext off) |
| Open a link the person **taps** to a website, email or phone number, outside the app | Navigate away, or open another app, on its own |
| Keep its own data (`localStorage`) | Talk to the native app beyond the theme color and "close the keyboard" (Android: only from its own origin) |
| Use the camera or photos through a file picker, after the system asks | Location, push notifications, contacts, other device data |

Web mode serves three files (page, manifest, icon) from memory under a random path, on the local network only,
for a limited time, GET/HEAD only, and never prints the secret path in its log. The scripts read the
prototype as text, never execute it on the computer, write only inside the project folder, validate every
name, id and path, and refuse to overwrite a folder that is not one of their projects. Details:
`references/security.md`.

## Files

| File | Purpose |
|---|---|
| `scripts/doctor.py` | Requirements per platform, with the exact fix for each gap |
| `scripts/init.py` | Creates the project for the chosen platforms, with the name and the icon |
| `scripts/set_icon.py` | Changes the icon of an existing project |
| `scripts/scan.py` | Finds mockup chrome, edge-anchored bars, risks; the ASSESSMENT |
| `scripts/adapt.py` | Applies the generic layer and the config to a copy of the HTML, per target |
| `scripts/shots.py` | Drives the simulator, emulator or Safari and saves screenshots; records the checked version |
| `scripts/sync.py` | Builds, installs and launches the `ios` or `android` app, with the phone gates |
| `scripts/serve.py` | Web mode: serves the adapted page on the local network for a limited time |
| `scripts/phone_lib.py`, `scripts/android_lib.py` | Shared helpers (Xcode, devices, icons; SDK, adb, Gradle) |
| `assets/shell.js` | Page side of the shell: keyboard, theme, keyboard dismissal, sheet drag, web-mode keyboard |
| `template/`, `template-android/` | The native apps: iOS (Swift) and Android (Kotlin) |
| `references/assessment.md` | How to present findings, and instruction templates for the designer |
| `references/playbook.md` | Every problem seen so far and its fix, with specs and CSS |
| `references/config.md` | `phone.config.json` schema and a worked example |
| `references/security.md` | What each shell and web mode allow and block, and why |
| `references/setup.md` | Signing, iPhone and Android setup, error table |
