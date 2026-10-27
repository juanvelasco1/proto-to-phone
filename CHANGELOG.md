# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-27

First release.

### Added

- Scripts: `doctor` (requirements, stops with the exact fix), `init` (project with name and logo icon),
  `set_icon`, `scan` (mockup chrome, edge-anchored bars, risks, and an ASSESSMENT of format, verdict and
  feasibility per finding), `adapt` (generic layer + `phone.config.json` on a copy of the prototype), `shots`
  (simulator screenshots, records the checked version), `sync` (build, install, launch).
- Native shell template: a full-screen, locked-down `WKWebView`; the real keyboard shrinks the view and drives
  `kb-open`; no Prev/Next/Done bar; status bar and keyboard follow the page theme.
- Playbook of fixes: phone mockup removal, safe areas, keyboard, native-sized floating tab bar, bottom-sheet
  drag, viewport height, touch differences, scroll mode, literal patches.
- `inlineLocalFiles`: images and fonts next to the prototype are inlined into the bundled copy.
- iPhone gates in `sync.py`: `--confirm-device` before the first install, and only the exact version checked
  with `shots.py` can be installed.
- Security: navigation limited to the app's own folder; tapped links open outside; code-initiated navigation
  and other apps' URL schemes are cancelled; validated bridge messages; escaped config CSS/JS; validated input;
  `references/security.md`.
- Tests for adapt, scan, the device gates, validation and repository hygiene.
