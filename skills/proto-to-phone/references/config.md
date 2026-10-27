# phone.config.json

Lives in the project folder (`~/ProtoPhone/<slug>/phone.config.json`). Read by `adapt.py` on every sync.
All keys are optional. Unknown keys are ignored.

| Key | Type | What it does |
|---|---|---|
| `scroll` | `"app"` / `"page"` | `app`: the document never scrolls (one-viewport-tall design). `page`: native scrolling. Default: `app` when `frame.device` is set, otherwise `page` |
| `frame.container` | selector | Desktop canvas around the device: padding, gap and margin removed, `min-height: 100dvh` |
| `frame.device` | selector | The device element: full width and height (`100dvh`), no border, radius or shadow, `padding-top` = top safe area |
| `frame.background` | CSS value | Background for `body` (shows when the device does not cover it) |
| `hide` | selector list | `display: none !important` under the shell: fake status bar, keyboard, notch, home indicator, captions |
| `keyboardTargets` | selector list | Elements that get `kb-open` (and `--kbh: 0px`) while the real keyboard is up. `<html>` always does |
| `themeSource` | selector | Element whose background decides the status bar and keyboard appearance. Default: `frame.device`, else `body` |
| `sheetDrag` | object | `{ sheet, scrim, openClass?, skip? }`: drag a bottom sheet down to close it (see playbook) |
| `inlineLocalFiles` | boolean | Inline images and fonts referenced with relative paths (`src="img/a.png"`, `url(fonts/x.woff2)`) as data URIs in the bundled copy. Only files inside the prototype's folder; 5 MB each, 30 MB total. Local CSS/JS files are not inlined |
| `css` | string or list | Extra CSS, appended after the generic layer. Prefix rules with `:root.app-shell` |
| `js` | string or list | Extra JS, runs after `shell.js` |
| `patches` | list | Literal edits to the prototype source: `{ what, find, replace, all?, optional? }` |

Variables available to `css`: `--shell-top` and `--shell-bottom` (raw safe areas), `--shell-float-bottom`
(where a floating bar rests: `max(16px, inset - 10px)`).

## Worked example

A prototype drawn in a `#device` mockup on a `.canvas`, with a fake status bar and keyboard, a floating tab
bar (`.tabbar`) with a text field above it, a bottom sheet (`#sheet` over `#scrim`) and a toast:

```json
{
  "scroll": "app",
  "frame": { "container": ".canvas", "device": "#device", "background": "var(--bg)" },
  "hide": [".mockup-caption", ".statusbar", ".fake-keyboard"],
  "keyboardTargets": ["#device"],
  "sheetDrag": { "sheet": "#sheet", "scrim": "#scrim" },
  "css": [
    ":root.app-shell .tabbar{padding:12px 24px var(--shell-float-bottom)}",
    ":root.app-shell .tabbar-tab{min-height:48px}",
    ":root.app-shell .tabbar-button{width:56px;height:56px}",
    ":root.app-shell #device.kb-open .tabbar{padding-bottom:8px}",
    ":root.app-shell .toast{bottom:calc(var(--shell-float-bottom) + 92px)}",
    ":root.app-shell .sheet-content{padding-bottom:max(34px,calc(env(safe-area-inset-bottom) + 16px))}",
    ":root.app-shell .sheet{max-height:min(85%,calc(100% - env(safe-area-inset-top) - 12px))}"
  ]
}
```
