# Presenting the assessment

`scan.py` ends with an ASSESSMENT: a format, a verdict and findings marked `feasible` (yes / partial / no) and
`by` (skill / designer / none). It is a heuristic. Before showing it, read the CSS and JS around each finding:
drop false positives, add what it missed (look at the screens in the simulator if unsure).

## Formats

| Format | What it means on a phone |
|---|---|
| `phone-mockup` | Designed for a phone, drawn inside a phone frame. The best case: the frame goes, the design stays |
| `mobile-web` | A phone-width page without a frame. Works; bars and fields need the same checks |
| `responsive` | Has mobile breakpoints. Works at phone width; check the mobile layout is the one shown |
| `desktop` | Built for a computer screen. It runs, but shrunk or overflowing: it does not show how a phone version would feel |
| `tablet-mockup` | Designed for an iPad. The app is iPhone-only, so it is squeezed |

## Verdicts

| Verdict | Say | Next |
|---|---|---|
| `ready-to-adapt` | It can work well on the phone with the proposed adaptations | Approve the proposals |
| `works-with-limits` | It works; some things will not (listed) | Approve, knowing the limits |
| `possible-but-not-a-phone-design` | It runs, but it is not a phone design, so it will not show what the person wants to see | Recommend asking the builder for a phone version first; continue only if they still want it |
| `needs-changes-first` | Something breaks unless the prototype changes (separate files, a server, http) | Give the instruction for the builder; stop unless they accept the breakage |

## The table to show

| What I found | What I propose | Possible | Who |
|---|---|---|---|
| Drawn inside a phone frame with a fake status bar | Make the design the whole screen and hide the fake parts | Yes | The skill |
| Menus that open on hover | On a phone there is no hover; they need a tap | Partly | You, in your builder |
| Calls to `/api/...` | The app has no server; use mock data | No, as is | You, in your builder |

Then ask which proposals to apply. Nothing in "the skill" column is applied without that OK.

## Instructions for the designer's builder

For each "designer" row, give a ready-to-paste instruction, short and concrete, naming the screen or element.
Templates:

- **Desktop → phone:** "Make a phone version of these screens at 390 px wide: one column, the navigation in a
  bottom tab bar, controls at least 44 px tall, text fields at 16 px."
- **Separate files:** "Export the prototype as a single self-contained HTML file: inline the CSS, the JS, the
  images (as data URIs) and the fonts."
- **Server calls:** "Replace the calls to /api/... with mock data defined in the file, so it works offline."
- **Hover:** "Every menu or action that appears on hover must also open on tap."
- **http resources:** "Load every external resource over https://."
- **Small tap targets:** "Make every tappable element at least 44 × 44 px, even if the icon stays small."
