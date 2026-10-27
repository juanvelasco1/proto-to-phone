# proto-to-phone

**See your prototype on a real phone, not only inside a mockup.**

[Agent Skill](https://agentskills.io) for AI coding tools. It takes a single-file HTML prototype (from any AI
builder or hand-made) and puts it on your phone, adapted so it behaves like an app instead of a web page in a
frame.

| Platform | Your computer | Your phone | Status |
|---|---|---|---|
| iOS app | Mac with Xcode | iPhone | Verified |
| Android app | Mac, Windows or Linux | Android | **Experimental**: written, not yet built or run by the maintainers. Reports welcome |
| Web (the phone's browser, local network) | Mac, Windows or Linux | Any phone on the same Wi-Fi | Verified on iPhone Safari; Android Chrome not yet |

Windows or Linux with an iPhone: use web mode. Apple only allows building iPhone apps on a Mac.

## What it is, and what it is not

| It is | It is not |
|---|---|
| A way to judge a design on the device: real sizes, real keyboard, thumb reach, safe areas | A production app: no backend, no accounts, no push, no App Store |
| General: any single HTML file (Open Design, Claude artifacts, v0, Lovable, Bolt, hand-written) | An HTML → Figma tool |
| A development build or a local web page for your own phone | A way to distribute the app to other people (TestFlight, Play Store) |
| A local tool: nothing is uploaded, no telemetry | App Store material: the shell uses a runtime trick to hide the keyboard's Prev/Next bar that App Review would not accept |

> Independent project. Not affiliated with, endorsed or sponsored by Apple Inc., Anthropic or any of the
> prototype builders named here. iPhone, iOS and Xcode are trademarks of Apple Inc.; Android is a trademark
> of Google LLC.

## What it does

1. **Checks your computer**, per platform, and stops, saying exactly what to fix, if something is missing.
2. **Asks for the app name and your logo** (PNG, JPG, HEIC, SVG or PDF) and shows you the icon.
3. **Tells you what kind of design it is** (phone mockup, mobile web, responsive, desktop, tablet) and what can
   and cannot work on a phone, with a proposal for each finding: done by the skill, by you in your builder
   (with a ready-to-paste instruction), or not possible. You approve what gets applied.
4. **Adapts a copy** of the prototype, never the original: removes the phone frame, fake status bar and fake
   keyboard; respects the safe areas; with the real keyboard up, only the input stays above it; sizes and
   places a floating tab bar like a native one; lets bottom sheets be dragged closed; makes the status bar
   follow the design.
5. **Checks every screen** before the phone, with screenshots and a fixed checklist: iOS simulator, Android
   emulator, or Safari in the simulator for web mode.
6. **Installs on your phone, after asking**, and only the version that passed the check. Web mode shares a
   time-limited link on your local network, also after asking.
7. **Re-syncs** with one command when the design changes.

## Requirements

| Requirement | For | If missing |
|---|---|---|
| Python 3.8+ | Everything | Stops |
| The prototype as **one** `.html` file | Everything | Stops; export it as a single file |
| An AI tool that loads skills and runs commands | Everything | Not possible |
| Mac with Xcode (opened once), an iOS simulator, [xcodegen](https://github.com/yonaskolb/XcodeGen) | iOS app | No iOS app |
| An Apple ID in Xcode (free works); iPhone paired, unlocked, Developer Mode on | iOS app on a real iPhone | Simulator only |
| Java 17+, Android SDK with platform-tools, Gradle 8.9+ (Android Studio brings most of it) | Android app | No Android app |
| An Android emulator, or a phone with USB debugging | Android app | No Android app |
| Computer and phone on the same Wi-Fi | Web mode | No web mode |

`python3 skills/proto-to-phone/scripts/doctor.py` checks everything and says what to fix. With a free Apple ID
the iOS app expires after 7 days; sync again to renew it.

## Security

The prototype is treated as untrusted code. It never runs on your computer, only in a simulator, an emulator
or on the phone. Inside the apps it cannot read files outside its own folder, navigate away or open other
apps on its own, or use plain `http://`. A link you tap opens in the browser, mail or phone app. It talks to
the native side only to report its background color and to close the keyboard. Web mode serves three files
from memory under a random link, on your local network only, for a limited time. The scripts validate every
name, id and path, run commands without a shell, never overwrite a folder that is not theirs, ask before
installing tools, installing on a phone or sharing on the network, and never publish anything. Details:
[`references/security.md`](skills/proto-to-phone/references/security.md).

## Install

**Claude Code** (as a plugin):

```sh
claude plugin marketplace add juanvelasco1/proto-to-phone
claude plugin install proto-to-phone@proto-to-phone
```

**Any tool** (with the [skills CLI](https://skills.sh)):

```sh
npx skills add juanvelasco1/proto-to-phone
```

**By hand:**

```sh
git clone https://github.com/juanvelasco1/proto-to-phone.git
ln -s "$PWD/proto-to-phone/skills/proto-to-phone" ~/.claude/skills/proto-to-phone
```

## Use

Ask your tool: *"Put ~/Downloads/prototype.html on my iPhone"*, *"pasa este prototipo a mi Android"*, *"open
my prototype on my phone, I'm on Windows"*, or *"I changed the design, update the phone"*. It follows [`SKILL.md`](skills/proto-to-phone/SKILL.md) step by
step. Projects are created in `~/ProtoPhone/<name>`.

## Checks

```sh
python3 -m unittest discover tests
```

## License

[MIT](LICENSE).
