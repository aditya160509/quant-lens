# UI canon

Rules from the best design skills, books and design systems, reduced to what applies to Studio and the labs. `UI_GUIDE.md` covers layout, spacing, charts and the editor; this file adds polish, motion, interaction, accessibility, anti-slop bans and the reading list. Where the two disagree, `UI_GUIDE.md` wins for Studio.

Sources read (2026-11-17): Impeccable (pbakaus, craft floor + operate mode), Hallmark (Nutlope, the Floor), Taste Skill v2.5 (Leonxlnx), Emil Kowalski design-eng skills, Vercel Web Interface Guidelines, Make Interfaces Feel Better (Jakub Krehel), Stageshow (Benji Taylor), Uizze (800k real screens as references).

## 1. Studio is an "operate" surface

Impeccable splits surfaces into persuade, operate, read and experience. Every Studio and lab screen is **operate**: the user completes a task.

- Earned familiarity beats novelty. A user who knows TradingView or Linear trusts it without pausing. The tool disappears into the task.
- One sans family carries everything. Fixed rem scale, step ratio 1.125–1.2. No fluid (clamp) type.
- Restrained colour. Accent only for primary action, current selection and state.
- A second neutral layer for sidebar, toolbar and panels.
- Density is allowed: long tables, many labels.
- Same button, same control, same icon style on every screen. If "Save" looks different in two places, one is wrong.

## 2. Banned (anti-slop)

From Hallmark's Floor, Impeccable's refuse list and Taste Skill. Any one of these on a screen is a defect.

- Eyebrow labels above headings; labels in tracked capitals or small caps. Labels are the body face, one step smaller, sentence case.
- Section numbers (01 / 02 / 03) unless the order carries meaning.
- Same-size icon + heading + text cards as page structure. A card inside a card.
- The hero-metric template (big number, small label, stat row, accent) used as decoration rather than the actual answer.
- Gradient text; purple-to-blue gradients; glass or blur as decoration; zero-offset coloured glows.
- Coloured `border-left` / `border-right` over 1px on cards, rows, callouts or alerts.
- Decorative status dots; middle-dot-joined meta strings; arrows glued to link text; emoji as icons; icons in tinted squares.
- Sparklines, rings and soft rounded boxes standing in for content.
- Monospace as a costume. Mono is for code, tickers, hashes and figures only.
- One italic or coloured word inside a heading.
- Invented numbers, quotes or logos. Every number on screen comes from the data.
- `transition: all`. Animating `width`, `height`, `top`, `left`.
- A modal for a task that needs no interruption. Exhaust inline first.
- Helper text, taglines, secondary labels. If the screen needs them, fix the layout.

## 3. Interaction (Vercel guidelines)

- Every flow works by keyboard. `:focus-visible` ring on every focusable element, shown instantly, never covered by sticky bars.
- Hit target ≥ 24px desktop, ≥ 44px phone; extend small controls with a pseudo-element. Hit areas never overlap.
- Phone inputs at ≥ 16px font (stops iOS zoom). Never disable zoom or paste.
- Loading button keeps its label and adds a spinner. Spinner/skeleton waits ~150–300ms before showing and stays ≥ 300–500ms (no flicker).
- State in the URL: tabs, filters, selected run, expanded panels. Refresh and Back restore it, scroll position included.
- Optimistic updates with rollback or Undo. Destructive actions need confirm or Undo.
- "Rename…", "Running…", "Saving…" end with the ellipsis character `…`.
- Enter submits a single-field form; ⌘↵ submits a textarea or editor.
- Don't pre-disable submit; allow it and show errors beside the fields, focusing the first.
- Don't block typing in number fields; validate and explain.
- Links are `<a>`, so ⌘-click opens a new tab. Buttons are `<button>`.
- First tooltip in a group delays; neighbours open instantly.
- `overscroll-behavior: contain` in drawers, sheets and dialogs.
- Every drag or swipe has a click and keyboard alternative.
- Toasts and inline validation announce through polite `aria-live`.
- No dead ends: every empty, error or skipped state names the next step.

## 4. Motion (Emil Kowalski, Krehel, Vercel)

**Should it move at all?** By frequency:

| Seen | Decision |
|---|---|
| 100+ times a day (shortcuts, palette, tab switch) | Never animate |
| Tens of times (hover, list navigation) | Remove or cut to colour only |
| Occasional (dialog, drawer, toast) | Standard |
| Rare (first run) | May add delight |

Never animate a keyboard-initiated action.

**Easing:**
- Enter and exit: ease-out, `cubic-bezier(0.23, 1, 0.32, 1)`.
- Moving on screen: `cubic-bezier(0.77, 0, 0.175, 1)`.
- Sheets and drawers: `cubic-bezier(0.32, 0.72, 0, 1)`.
- Never ease-in for UI.

**Duration:**

| Element | Duration |
|---|---|
| Press | 100–160ms |
| Tooltip | 125–200ms |
| Dropdown | 150–250ms |
| Dialog or drawer | 200–300ms |

Keep everything under 300ms.

**Rules:**
- Nothing appears from nothing: start from `scale(0.95)` with `opacity: 0`, never `scale(0)`.
- Popovers scale from their trigger (`transform-origin`); dialogs stay centred.
- Buttons press to `scale(0.96)` on `:active`. Never smaller than 0.95.
- Use CSS transitions for state changes, because they can be interrupted; use keyframes only for one-off sequences.
- Exits are softer than enters: a small `translateY`, not the full height.
- No entrance animation on first page load. A product loads into a task.
- Animate only `transform`, `opacity`, `filter`, `clip-path`. Use `will-change` only when the first frame stutters.
- Every animation has a `prefers-reduced-motion` variant.
- Data being read never moves; charts don't animate on refresh.

## 5. Surface detail (Krehel, Vercel)

- Concentric radius: outer = inner + padding. The same radius on parent and child is the most common thing that "feels off".
- Align optically, not geometrically: icon buttons, play triangles, ±1px.
- Depth comes from layered shadows (ambient + direct, at least 2 layers), and only on floating layers. Combine them with a semi-transparent border for a crisp edge.
- Images get `outline: 1px rgba(0,0,0,.1)` in light mode and `rgba(255,255,255,.1)` in dark mode. Pure black or white, never tinted.
- On a coloured surface, tint borders, shadows and secondary text toward that hue, never plain grey.
- Hover, active and focus states have more contrast than the rest state.
- Set `color-scheme: dark` on `<html>` in dark mode, plus a `theme-color` meta that matches the background.
- Root gets `-webkit-font-smoothing: antialiased`. Headings get `text-wrap: balance`; prose gets `text-wrap: pretty`.
- `tabular-nums` on every number that updates.
- Use curly quotes, the `…` character, and a non-breaking space between number and unit (`10&nbsp;MB`, `⌘&nbsp;K`).
- Keep line length at 65–75ch for prose; tables can run wider.
- Give a native `<select>` an explicit background and colour (Windows dark-mode bug).

## 6. States and resilience

- Every component has default, hover, focus, active, disabled, loading, error, plus empty, sparse and dense data.
- Skeletons mirror the final layout exactly, so nothing shifts.
- Break it on purpose (Emil "break-ui"): one-letter and 60-character tickers, 0 / 1 / 10,000 rows, negative and NaN values, a missing date, a very long error message.
- Overlays escape their container through a portal, `<dialog>`, the popover API or `position: fixed`, never clipped by `overflow: hidden`.
- Dates, numbers and currency use `Intl` for the user's locale. Show currency with 0 or 2 decimals per context, never mixed.

## 7. Product UI shown inside the app (Stageshow)

For previews, onboarding shots or demo cards of Studio itself:

- Use the real screen, simplified: 3–7 real strings, with placeholder bars for the rest.
- Crop to where the story is; never shrink a whole window into a card with even margins.
- One focal object with one action and one payoff. Every motion has a cause.
- Design at display size (about 720×340 beside copy, 400×300 in a card); never narrower than 320px.

## 8. References before building (Uizze idea)

Before a new screen, look at 3–5 real products that solve the same task, then copy their structure, not their skin:

| Screen | Look at |
|---|---|
| Charts | TradingView |
| Strategy editor | QuantConnect, VS Code |
| Tables and runs | Linear, Vercel dashboard |
| Data density | Bloomberg, Koyfin |
| Command palette | Raycast |
| Settings | Stripe |

## 9. Design systems to borrow from

| System | Take from it |
|---|---|
| Vercel Geist | Grey scale steps, Geist Mono for figures, dense tables |
| Linear | Dim chrome, LCH theme generation, keyboard-first |
| Radix Colors / Primitives | 12-step scales (1–2 backgrounds, 3–5 components, 6–8 borders, 9–10 solid, 11–12 text); accessible primitives |
| IBM Carbon | Data tables, data-viz palette and chart rules |
| Shopify Polaris | Content guidelines, empty and error states |
| Atlassian | Spacing tokens, elevation model |
| Material 3 | State layers (hover 8%, press 12%), motion tokens |
| Apple HIG | Hit targets, motion purpose, clarity/deference/depth |
| GitHub Primer | Dense developer UI, accessibility patterns |

## 10. Books

**Interface and craft**
- *Refactoring UI*, by Wathan & Schoger. Hierarchy by weight and colour, spacing scales, fewer borders.
- *Don't Make Me Think*, by Krug. Self-evident UI, scanning not reading.
- *The Design of Everyday Things*, by Norman. Affordances, signifiers, feedback, mapping.
- *About Face*, by Cooper. Goal-directed design, posture of sovereign apps (Studio is one).
- *Designing Interfaces*, by Tidwell. Patterns for dense and data-heavy apps.
- *Laws of UX*, by Yablonski. Fitts, Hick, Jakob, Miller, Doherty (respond under 400ms).
- *Universal Principles of Design*, by Lidwell et al.
- *Microinteractions*, by Saffer. Trigger, rules, feedback, loops.

**Data display**
- *The Visual Display of Quantitative Information* and *Envisioning Information*, by Tufte.
- *Information Dashboard Design* and *Show Me the Numbers*, by Few. Dashboards fit one screen; no gauges for decoration.
- *The Functional Art* and *How Charts Lie*, by Cairo.
- *Fundamentals of Data Visualization*, by Wilke (free online).
- *Visualization Analysis and Design*, by Munzner. Channel effectiveness ranking: position > length > angle > area > colour.

**Type and grids**
- *The Elements of Typographic Style*, by Bringhurst.
- *Practical Typography*, by Butterick (free online).
- *Thinking with Type*, by Lupton.
- *Grid Systems in Graphic Design*, by Müller-Brockmann.

**Motion and engineering**
- Emil Kowalski, *Animations on the Web*. Easing and duration as above.
- Rauno Freiberg, "Invisible Details of Interaction Design".
- Josh Comeau, CSS for JS developers. Layout and shadows.

## 11. Checklist (run with UI_GUIDE §11)

- [ ] Nothing from §2 on the screen.
- [ ] Keyboard path works and focus is visible; hit targets 24 / 44px.
- [ ] State is in the URL; refresh restores it.
- [ ] Frequent actions don't animate; the rest is under 300ms, ease-out, with a reduced-motion variant.
- [ ] Radii concentric; shadows only on floating layers.
- [ ] Every state (empty, loading, error, skipped, dense) designed, and broken with worst-case data.
- [ ] Copy: verbs on buttons, `…` on pending states, errors say how to fix.

## 12. What the best products do (screenshots in `refs/`)

Captured 2026-11-17 at 1440×900. Signed-in app screens are not public, so these show each product's own shots of its UI and its docs.

| Product | Screenshot | What to copy |
|---|---|---|
| QuantConnect | `refs/quantconnect-docs.png`, `refs/quantconnect.png` | Backtest result layout: a full-width stat strip of 8 figures in mono with green/red sign colour, then the equity chart (wide, with 1m/3m/1y/All ranges and a daily-return bar strip beneath), then a narrow right column with chart picker and ranking. Docs layout: left tree, content at ~730px, right "in this page" rail |
| Linear | `refs/linear.png` | Inverted-L chrome: sidebar ~220px, dimmer than the work area; 13px labels with 16px icons; a header row with ID, title, star and `1 / 84` pager with ↑↓; side panel opens over the content, not beside it |
| Koyfin | `refs/koyfin.png` | Dashboard of small titled panels on a dark frame: news table, currency table with right-aligned price, change and % columns, checkbox per row to add to the chart; 12px rows, no card padding wasted |
| Raycast | `refs/raycast.png` | Command palette as the main navigation: one search box for every item and action, shortcut shown on the right of each row |
| Stripe docs | `refs/stripe-docs.png` | Calm reference layout; code and prose side by side |
| Vercel Geist | `refs/geist.png` | Grey scale, Geist Sans/Mono, the system Studio's tokens most resemble |
| TradingView Pine | `refs/tradingview-pine.png` | Editor docs; the Pine editor docks under the chart, results in the same frame |

### Rules learned from them

- **Rank the data, don't hide it** (Koyfin team, DIXI). Investors want more on screen, not less. Removing data to "look clean" sends them back to a spreadsheet.
- **Whitespace can kill a pro tool.** A portfolio analytics firm blamed its stalled growth on a "modern" white-space-heavy web app beside the Bloomberg terminal (HN 19153875). Studio's density target is Bloomberg and Koyfin, not a SaaS landing page.
- **Show how fresh every number is.** Mark delayed or end-of-day data and keep its date visible (Koyfin). For Studio: "data ends 2026-02-01" on every live figure.
- **Colour only for direction, and never alone.** Pair red and green with a sign or arrow; 1 in 12 men are colour-blind.
- **Number columns don't move.** Use fixed-width figures and no tick animation, so the eye never re-finds a number (BridgeIQ trading UI).
- **No transitions on live data panels.** Drop padding and fades on panels that update.
- **Separate dark panels by background steps.** Use 4 steps about 6–7 hex points apart (`#0a0a0a / #111 / #161616 / #1c1c1c`), add `rgba(255,255,255,.06)` borders only where needed, and use two scales per semantic colour: green `#22c55e` dark and `#16a34a` light (pixel-show, trading journal).
- **One search for everything.** One box finds tickers, runs, pages and actions (Koyfin, Raycast, Bloomberg `<GO>`).
- **Let users save their own views.** Column sets, screens and layouts are per user, saved and shareable.
- **Change gradually.** Bloomberg ships UI changes in small steps over months and releases on Friday nights, so users adapt over the weekend. For Studio, redesign one page at a time and keep shortcuts and positions stable.
- **Keyboard first.** Bloomberg, Linear and Raycast all reach every function from the keyboard, which is what makes a tool feel like an extension of the user.
- **Backtest page order** follows QuantConnect: stat strip → equity with drawdown or returns strip → tabs (orders, trades, logs, insights, report). Studio's Backtest hero already matches; keep the stat strip to a single row of at most 8 figures.
