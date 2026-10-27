# proto-to-phone

**See an HTML prototype on a real iPhone, not only inside a mockup.**

[Agent Skill](https://agentskills.io) for AI coding tools. It takes a single-file HTML prototype (from any AI
builder or hand-made) and installs it on your iPhone as a small prototype app, adapted so it behaves like an
app instead of a web page in a frame.

## What it is, and what it is not

| It is | It is not |
|---|---|
| A way to judge a design on the device: real sizes, real keyboard, thumb reach, safe areas | A production app: no backend, no accounts, no push, no App Store |
| General: any single HTML file (Open Design, Claude artifacts, v0, Lovable, Bolt, hand-written) | An HTML → Figma tool |
| A development build for your own iPhone | A way to distribute the app to other people (that is TestFlight) |
| A local tool: nothing is uploaded, no telemetry | App Store material: the shell uses a runtime trick to hide the keyboard's Prev/Next bar that App Review would not accept |

> Independent project. Not affiliated with, endorsed or sponsored by Apple Inc., Anthropic or any of the
> prototype builders named here. iPhone, iOS and Xcode are trademarks of Apple Inc.

## What it does

1. **Checks your Mac** and stops, saying exactly what to fix, if something is missing.
2. **Asks for the app name and your logo** (PNG, JPG, HEIC, SVG or PDF) and shows you the icon.
3. **Tells you what kind of design it is** (phone mockup, mobile web, responsive, desktop, tablet) and what can
   and cannot work on a phone, with a proposal for each finding: done by the skill, by you in your builder
   (with a ready-to-paste instruction), or not possible. You approve what gets applied.
4. **Adapts a copy** of the prototype, never the original: removes the phone frame, fake status bar and fake
   keyboard; respects the safe areas; with the real keyboard up, only the input stays above it; sizes and
   places a floating tab bar like a native one; lets bottom sheets be dragged closed; makes the status bar
   follow the design.
5. **Checks every screen in the iOS simulator** with screenshots and a fixed checklist.
6. **Installs on your iPhone, after asking**, and only the version that passed the simulator check.
7. **Re-syncs** with one command when the design changes.

## Requirements

| Requirement | Why | If missing |
|---|---|---|
| A Mac | iOS apps are built on macOS | Not possible |
| Xcode (full, opened once) with an iOS simulator | Build and check the app | Stops and tells you how to install |
| [xcodegen](https://github.com/yonaskolb/XcodeGen) | Generate the Xcode project | Asks to run `brew install xcodegen` |
| Python 3.8+ | The scripts | Stops |
| The prototype as **one** `.html` file | Only one file is bundled | Stops; export it as a single file |
| An Apple ID in Xcode (free works) | Install on the iPhone | Simulator only |
| iPhone paired, unlocked, Developer Mode on | Install on the iPhone | Simulator only |
| An AI tool that loads skills and runs commands | Drives the steps | Not possible |

With a free Apple ID the app expires after 7 days; sync again to renew it. iOS only.

## Security

The prototype is treated as untrusted code. It never runs on your Mac, only in the simulator or on the phone.
Inside the app it cannot read files outside its own folder, navigate away or open other apps on its own, or use
plain `http://`. A link you tap opens in Safari, Mail or Phone. It talks to the native side only to report its
background color and to close the keyboard. The scripts validate every name, id and path, run commands without
a shell, never overwrite a folder that is not theirs, ask before installing tools or registering the app with
Apple, and never publish anything. Details:
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

Ask your tool: *"Put ~/Downloads/prototype.html on my iPhone"*, *"pasa este prototipo a mi teléfono"*, or
*"I changed the design, update the phone"*. It follows [`SKILL.md`](skills/proto-to-phone/SKILL.md) step by
step. Projects are created in `~/ProtoPhone/<name>`.

## Checks

```sh
python3 -m unittest discover tests
```

## License

[MIT](LICENSE).
