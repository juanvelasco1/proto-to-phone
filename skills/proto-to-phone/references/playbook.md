# Playbook: a prototype on a real phone

Each section is a problem seen on real prototypes, how to recognize it, and the fix. Fixes are CSS or JS in
`phone.config.json` (`css`, `js`, `hide`, ...), scoped under `:root.app-shell` so the prototype still works
in a desktop browser. Values are in CSS px = iOS points.

What the generic layer already does for every prototype (you do not repeat it):

| Done by | What |
|---|---|
| `adapt.py` | Viewport `width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover` (the last two stop iOS zooming in when a field is focused); no tap highlight, no callout, no text selection except in fields; `-webkit-text-size-adjust: 100%`; `--shell-top`, `--shell-bottom`, `--shell-float-bottom` variables |
| `shell.js` | Sets `kb-open` while the real keyboard is up; dismisses the keyboard when focus moves off a field without blurring it; reports the page background to the native side (status bar and keyboard appearance follow the design, light or dark); optional sheet drag |
| Native shell | Shrinks the web view to the space above the keyboard; removes the Prev/Next/Done bar; opens `http(s)`, `mailto:` and `tel:` links outside the app; shows `alert()` and `confirm()`; reloads if the web process dies |

## 1. A phone mockup on a desktop canvas

**Recognize:** the scan lists `frame`, `statusbar`, `notch`, `home-indicator`, `caption`, `canvas`, and a
fixed `width: 390px` on the device. On a phone the design shows inside a smaller phone, with a fake clock.

**Fix:** make the device the whole screen and hide the fake chrome.

```json
{
  "scroll": "app",
  "frame": { "container": ".canvas", "device": "#device", "background": "var(--bg)" },
  "hide": [".mockup-caption", ".statusbar", ".home-indicator"]
}
```

`frame.device` gets `100% x 100dvh`, no border, radius or shadow, and `padding-top: env(safe-area-inset-top)`
so content starts under the real status bar. If the fake status bar was part of the layout (content has a
fixed `top: 54px`), read the CSS and compensate in `css`. Use `scroll: "app"` when the device is one viewport
tall and inner areas scroll; omit it for a normal scrolling page.

## 2. Safe areas

**Recognize:** a bar or composer anchored to the bottom (`position: absolute|fixed; bottom: ...`) that sits on
the home indicator, or content under the notch. `env(safe-area-inset-*)` is not used (scan: 0).

**Fix:** anchor against the inset, never add to it blindly.

| Anchored thing | Rule |
|---|---|
| Plain bar flush with the edge | `padding-bottom: max(16px, env(safe-area-inset-bottom))` (reach the inset, do not float 50pt above it) |
| Floating bar (pill) | `padding-bottom: var(--shell-float-bottom)`, see section 4 |
| Bottom sheet body | `padding-bottom: max(34px, calc(env(safe-area-inset-bottom) + 16px))` |
| Sheet height | `max-height: min(85%, calc(100% - env(safe-area-inset-top) - 12px))` so a sheet never climbs under the status bar |
| Toast / snackbar above a bar | `bottom: calc(var(--shell-float-bottom) + <bar height + gap>)` |

If the prototype already uses `env(safe-area-inset-*)`, check it is not counted twice inside the shell.

## 3. The keyboard

**Recognize:** the scan lists `keyboard` / `kb` elements, functions such as `showKeyboard()`, and the CSS has
`.kb-open` rules.

How it works here: the native keyboard shrinks the web view. Nothing needs lifting, so `--kbh` is always `0`.
`shell.js` toggles `kb-open` on `<html>` and on every element in `keyboardTargets`. The design uses that
class to rearrange itself, which is what makes "tab bar steps aside, only the input stays" work.

**Fix:**

1. Hide the simulated keyboard: `"hide": [".fake-keyboard"]`. Do **not** patch the prototype's keyboard function; with the
   keyboard hidden its measured height is 0, which is the right value.
2. Put `kb-open` where the design's rules expect it: if the CSS says `#device.kb-open .tabbar ...`, then
   `"keyboardTargets": ["#device"]`.
3. Remove the gap under an input that rests on the keyboard:
   `:root.app-shell #device.kb-open .tabbar{padding-bottom:8px}`.

**Check:** with the keyboard up, only the input is visible above it. Not the tab row, no empty band, no
Prev/Next/Done bar. After it goes down the bar is back and nothing jumped.

Known traps: `scrollIntoView()` can move the whole page under the keyboard (prefer scrolling the container);
a sheet closing hands focus to a button and the keyboard stays: handled by `shell.js`; fields under 16px
zoom the page on iOS unless `maximum-scale=1` (set) — if the user cares about pinch-zoom accessibility, use
16px fields instead.

## 4. The tab bar: size and position like a native one

**Recognize:** the user says the bar "looks off", "too small", "too high", or "not like an iPhone app". The
common mistakes are a 44-48pt pill hugging 16pt side margins and floating 34pt above the bottom (inset added
on top of padding).

The target (measured on a native floating tab bar, 440pt-wide screen; it follows the screen corners, so side
and bottom margins match):

| Part | Value |
|---|---|
| Pill height | 56 (4 padding + 48 tab) |
| Separate circle button (account, inbox) | 56 x 56 |
| Gap between pill and circle | 8 |
| Side margin | 24 |
| Distance to the bottom edge | `max(16px, env(safe-area-inset-bottom) - 10px)` = 24 on phones with a home indicator, so the bar sits just over it, not 34 above |
| Active tab | inset 4-5 inside the pill, height 48 |
| Icons | 22-24 |
| Touch targets | at least 44 x 44 (stretch the hit area with `::after{inset:-2px}` if the visible control is smaller) |

Recipe (rename the selectors to the prototype's wrapper, tab, secondary button and circle):

```json
"css": [
  ":root.app-shell .tabbar{padding:12px 24px var(--shell-float-bottom)}",
  ":root.app-shell .tabbar-tab{min-height:48px}",
  ":root.app-shell .tabbar-button{width:56px;height:56px}"
]
```

Everything stacked above the bar moves with it: quick-action bars and toasts use
`calc(var(--shell-float-bottom) + <56 + gap>)`; a composer in the same wrapper shares the 24 side margin so
its edges line up with the bar. Verify with a screenshot of each screen that has the bar, with and without
a composer above it.

## 5. Viewport height

**Recognize:** `100vh` in the CSS (scan: `uses_100vh`) and content cut or a gap when the keyboard or the
browser bars change the height. **Fix:** `100dvh` in the shell scope, or `height: 100%` chains from a
`100dvh` root.

## 6. Bottom sheets

Drag to close: `"sheetDrag": { "sheet": "#sheet", "scrim": "#scrim", "openClass": "on" }`. It claims the
finger only for a downward drag with the inner scroller at the top, and closes by clicking the scrim.
`skip` lists selectors that must keep their own gestures (fields, canvases, time wheels, maps).

## 7. Things that behave differently on touch

| Symptom | Cause | Fix |
|---|---|---|
| Hover styles stick after a tap | `:hover` applies on touch | Wrap in `@media (hover: hover)` in `css` overrides, only where visible |
| Text selected on long press | Default | Already off; fields keep selection |
| Links open inside the app | n/a | They open outside by design (Safari, Mail, Phone) |
| State survives a relaunch | `localStorage` persists | Normal. The simulator test runs with `-resetState`; delete the app to reset on the phone |
| Images/fonts missing | Only `index.html` is bundled | Inline them as data URIs |
| `http://` resource blocked | App Transport Security | Use `https://` |
| Camera / photos / microphone | Usage strings are in Info.plist | Works; edit the strings in the project's `App/Info.plist` if needed |
| Push, geolocation prompts, haptics | Not wired by the shell | Out of scope; say so |

## 8. Scroll mode

`"app"`: the document never scrolls and the shell pins the scroll offset to zero (WebKit otherwise lifts the
whole app to reveal a focused field). `"page"`: native scrolling. Wrong mode symptoms: "app" on a long page
= cannot scroll; "page" on a fixed-height app = the page wobbles or jumps under the keyboard.

## 9. Literal patches

Last resort for prototype JS or HTML that cannot be fixed with CSS, written as anchored literals:

```json
"patches": [
  { "what": "stop auto-focus on load", "find": "input.focus();", "replace": "/* input.focus(); */" }
]
```

`find` must occur exactly once (`"all": true` for every occurrence, `"optional": true` to skip when absent).
A miss stops the build with the patch name: that is the point; a redesign that moved the anchor is caught
before it reaches the phone.
