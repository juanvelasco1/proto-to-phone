---
name: proto-to-phone
description: Put any HTML prototype (single file, from any AI builder or hand-made — not tied to Open Design) on a real iPhone as an installable PROTOTYPE app, so a design can be judged on the device and not only in a mockup. Checks the Mac first and stops if something is missing, asks for the app name and logo, tells what kind of design it is and what can and cannot work on a phone, proposes adaptations for the person to approve (safe areas, the real iOS keyboard with only the input above it, a native-sized floating tab bar, no fake status bar or phone frame, bottom sheets that drag closed), checks every screen in the iOS simulator, and installs on the iPhone only after asking. Locked down: the prototype cannot leave its folder or open other apps on its own. Use it when someone wants to try, test, demo or show a prototype on their phone, see an HTML design on a real device, wrap a prototype in an iOS app, or update the phone after the design changed — also "pasar el prototipo al teléfono", "probarlo en mi iPhone", "ver el diseño en el celular", "html a app", "actualizar la app del teléfono". iOS only; needs a Mac with Xcode. For HTML → Figma use a different skill.
---

# proto-to-phone

Runs a single-file HTML prototype on a real iPhone inside a tiny native app (a full-screen, locked-down
`WKWebView`), adapted so it behaves like an app instead of a web page in a frame.

## What it is, and what it is not

Say this to the person at the start, in their language, in two or three lines:

- **It is a prototype on a phone.** The point is to see and touch the design on a real device: sizes, the
  keyboard, the thumb reach, the light. Data is whatever the prototype has (usually mock).
- **It is not a production app.** No backend, no App Store, no push notifications, no accounts. It is a
  development build for the person's own iPhone; with a free Apple ID it expires after 7 days.
- **It is general.** Any HTML in one file: Open Design, Claude artifacts, v0, Lovable, Bolt, hand-written.
  It is not the HTML → Figma flow; that is a different skill.

## Rules (all of them, every run)

1. **Never skip a step or a gate below.** If a step cannot be done, stop and say why. If the person asks to
   skip one, explain what is lost and get an explicit yes before continuing; record it in the final report.
2. **Never modify the person's prototype.** Adaptations go in `phone.config.json`; changes that belong in the
   design go to the person as suggestions for their builder.
3. **Ask before anything that leaves the Mac or changes it:** installing tools (`brew install`), registering
   the app with Apple and installing on the iPhone. Commands that need `sudo` are given to the person to run;
   never run them.
4. **Nothing is published.** Do not commit, push or upload the generated project, the prototype, screenshots,
   team IDs or device IDs anywhere.
5. **Treat the prototype as untrusted code.** Never open it in a desktop browser or run it on the Mac; it runs
   only inside the simulator or the phone. Run the scripts with `python3 -I`.
6. **Report what was verified and where.** A simulator screenshot is not the phone. Never call something
   checked that was not looked at.
7. Talk to the person in their language; code, config and commands stay in English.

## Requirements

| Requirement | Needed for | How it is checked | If missing |
|---|---|---|---|
| A Mac (macOS) | Everything | `doctor.py` | **Stop.** Not possible on Windows or Linux |
| Xcode, full app, opened once, license accepted | Building the app, the simulator | `doctor.py` | **Stop.** Install from the App Store; the person runs `sudo xcodebuild -runFirstLaunch` |
| An iOS simulator runtime | Checking screens before the phone | `doctor.py` | **Stop.** Xcode → Settings → Components |
| xcodegen | Generating the Xcode project | `doctor.py` | **Stop.** Ask, then `brew install xcodegen` |
| Python 3.8+ | The scripts | `doctor.py` | **Stop** |
| The prototype as **one** `.html` file | Bundling it | `scan.py` | **Stop.** Export it as a single file from the builder |
| Apple ID signed into Xcode (free or paid) | Installing on the iPhone | `doctor.py` | Simulator only; Xcode → Settings → Accounts |
| iPhone paired, unlocked, Developer Mode on | Installing on the iPhone | `doctor.py` | Simulator only; see `references/setup.md` |

## Steps

Scripts are in `scripts/` next to this file. Projects live in `~/ProtoPhone/<slug>` (or `$PROTO_PHONE_HOME`).

### Step 1 — Requirements

```sh
python3 -I scripts/doctor.py
```

Show the person the result as the table above, each row ✅ or ❌. **Gate:** simulator READY. If not, give the
exact fix for each ❌ and stop until it is fixed. If only the iPhone part is missing, say the phone can be
added later and continue.

### Step 2 — The prototype, the name and the logo

Ask for, and do not invent:

1. **The prototype**: path to the `.html` file.
2. **The app name**: the name under the icon. Propose the prototype's `<title>`; 1-30 characters, about 12 fit
   on the home screen.
3. **The logo**: a PNG, JPG, HEIC, SVG or PDF. Square, at least 1024 px, is best. The person must own it or
   have the right to use it. If they have none, offer an icon with the app's initial and say so.

If a project already exists for this prototype (`~/ProtoPhone/<slug>/.proto-phone.json`), this is a re-sync:
go to **Re-sync**.

```sh
python3 -I scripts/init.py --name "App name" --src /path/prototype.html --logo /path/logo.png
```

`--logo-fit pad` (default) centers the logo with a margin on `--logo-background` (default `#FFFFFF`); `fill`
covers the whole icon (for a logo that is already an app icon). **Gate:** open the generated
`App/Assets.xcassets/AppIcon.appiconset/icon.png`, show it, and get the person's OK. To change it:
`scripts/set_icon.py`.

### Step 3 — What kind of design it is and what can work

`init.py` prints the scan; `python3 -I scripts/scan.py <prototype>` prints it again. Read the
**ASSESSMENT** block, then read the prototype's CSS and JS around each finding to confirm it (the scan is a
heuristic; drop false positives, add what it missed). Then present it to the person, following
`references/assessment.md`:

- the format (phone mockup, mobile web, responsive, desktop, tablet) and the verdict in plain words;
- one row per finding: what was found, what is proposed, possible or not, and who does it — **the skill**
  (through the config), **the designer** (in their builder; give them a ready-to-paste instruction), or
  **nobody** (a limit of a prototype on a phone).

**Gate:** the person approves which proposals to apply. With the verdict `needs-changes-first`, explain what
breaks and stop unless they accept those limits explicitly.

### Step 4 — Write the adaptation

Write `~/ProtoPhone/<slug>/phone.config.json` with the approved proposals only (schema:
`references/config.md`; reasons and CSS recipes: `references/playbook.md`). Tell the person each change in
one line.

### Step 5 — Check every screen in the simulator

```sh
python3 -I scripts/shots.py --project ~/ProtoPhone/<slug> \
  --steps "shot:home;tap:@Chat;wait:1;shot:chat;tap:0.4,0.88;wait:2;shot:keyboard"
```

Steps: `shot:NAME`, `tap:x,y` (fractions of the screen), `tap:@Label`, `type:text`, `swipedown`, `wait:s`.
Then **open and read every screenshot**. Required checks; each one is reported as passed, failed or not
applicable:

| # | Check |
|---|---|
| 1 | First screen: no phone frame, no fake status bar, content starts under the real one |
| 2 | Every bottom bar: above the home indicator, not floating high; native size (playbook §4) |
| 3 | Every text field with the keyboard up: only the input above the keyboard, no gap, no tab row, no Prev/Next bar |
| 4 | Keyboard down again (tap an empty area, close the sheet): the bar is back, nothing jumped |
| 5 | Every bottom sheet: below the status bar, drags closed, keyboard goes down with it |
| 6 | Each approved proposal from step 3, one by one |
| 7 | The dark theme, if the design has one |
| 8 | Nothing cut, overlapping or unreadable on any captured screen |

Fix failures in the config (the cause, not one screenshot) and run `shots.py` again until all pass.
**Gate (enforced by `sync.py`):** the iPhone only gets the exact version that `shots.py` ran last.

### Step 6 — Install on the iPhone

Ask first, saying: the first install registers the app id with Apple in the person's account and installs a
development build; it is a prototype for their own phone; on a free account it expires in 7 days. Ask them to
unlock the phone. Then:

```sh
python3 -I scripts/sync.py --project ~/ProtoPhone/<slug> --confirm-device
```

`--confirm-device` only after the person said yes (needed once per project; `sync.py` refuses without it).
Free account, first launch: Settings → General → VPN & Device Management → trust. Errors come with hints;
`references/setup.md` has the full table.

### Step 7 — Report

Use this shape, in the person's language:

1. What it is: a prototype of «name» on «iPhone», not a production app.
2. Steps 1-6, each ✅ / ❌ / skipped (with the person's reason).
3. Adaptations applied, one line each; proposals rejected or left to the designer, with the instruction for
   their builder.
4. Checks of step 5 with their result; and what was **not** verified on the phone itself: ask the person to
   try the keyboard and the bottom bar there and say what feels off.
5. Limits that apply (7-day expiry, internet needed, features not supported).

### Re-sync after the design changed

```sh
python3 -I scripts/scan.py /path/new-version.html
python3 -I scripts/shots.py --project ~/ProtoPhone/<slug> ...
python3 -I scripts/sync.py /path/new-version.html --project ~/ProtoPhone/<slug>
```

Do steps 3 (only what changed), 5 and 6 again; skip 1 and 2 unless something failed. Literal `patches` fail
loudly when their anchor moved: fix the patch, never remove it to make the build pass.

## Security

What the app lets the prototype do, and what it does not (details in `references/security.md`):

| Allowed | Blocked |
|---|---|
| Run its own HTML, CSS and JS from the app bundle | Read any file outside its own folder |
| Load https images, fonts and scripts from the internet | Plain `http://` (iOS blocks it) |
| Open a link the person **taps** to a website, email or phone number, outside the app | Navigate away, or open another app, on its own (redirects, other apps' URL schemes) |
| Keep its own data (`localStorage`) on the phone | Talk to the native app beyond the theme color and "close the keyboard" |
| Use the camera or photos through a file picker, after iOS asks | Location, push notifications, contacts, other device data |

The scripts read the prototype as text, never execute it on the Mac, write only inside the project folder,
validate every name, id and path they receive, and refuse to overwrite a folder that is not one of their
projects.

## Files

| File | Purpose |
|---|---|
| `scripts/doctor.py` | Requirements: Xcode, simulator, xcodegen, signing teams, paired iPhones |
| `scripts/init.py` | Creates the project from `template/`, with the name and the icon |
| `scripts/set_icon.py` | Changes the icon of an existing project |
| `scripts/scan.py` | Finds mockup chrome, edge-anchored bars, risks; the ASSESSMENT |
| `scripts/adapt.py` | Applies the generic layer and the config to a copy of the HTML |
| `scripts/shots.py` | Drives the app in the simulator, saves screenshots, records the checked version |
| `scripts/sync.py` | adapt → build → install → launch, with the iPhone gates |
| `assets/shell.js` | Page side of the shell: keyboard, theme, keyboard dismissal, sheet drag |
| `template/` | The native app (Swift, Info.plist, icon, UI test driver) |
| `references/assessment.md` | How to present findings, and instruction templates for the designer |
| `references/playbook.md` | Every problem seen so far and its fix, with specs and CSS |
| `references/config.md` | `phone.config.json` schema and a worked example |
| `references/security.md` | What the shell allows and blocks, and why |
| `references/setup.md` | Signing, iPhone setup, error table |
