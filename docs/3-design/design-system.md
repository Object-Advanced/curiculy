# Design system

One set of design tokens, two looks: **parents get "Morning Light"** (calm, natural, social-app modern with light whimsy), and **kids get "Sticker Book"** (chunky, bright, collectible). Both were chosen at the Phase 2 style-tile review on 2026-10-10.

## How it's built
- **`static/css/tokens.css`** is the only place raw colors, sizes, spacing, radii, shadows and motion are defined. Everything else uses its custom properties (`var(--…)`).
- **Three switches, all attributes on the `<html>` element:**

| Switch | Values | What changes |
|---|---|---|
| `data-theme` | `dark` (or absent for light) | Dark mode: deep forest and charcoal, not blue-grey |
| `data-persona` | `parent` / `kid` | The kid look: cream and grape colors, Fredoka and Nunito fonts, thick outlines, raised buttons, bigger corners |
| `data-season` | `autumn`, `winter`, `spring`, `summer` | A few decorative accent tokens only. Status colors never change. |

- **Guardrails, enforced by tests:**
  - `tests/test_design_tokens.py` fails if `app.css` gains a raw hex color or a font size off the scale.
  - The browser accessibility scan (`e2e/a11y-baseline.json`) fails if serious or critical issues grow. **Today every screen has 0.**

## Parent look: "Morning Light"
| Token | Value | Use |
|---|---|---|
| Paper | `#FBFBF9` | Page background |
| Ink | `#16181A` | Headings |
| Moss | `#3E7A55` | Primary buttons, rings (white text 5.1:1) |
| Moss, darker | `#2F6B49` | Accent text and links (6.3:1) |
| Sky | `#DCEBF5` | Info |
| Sunbeam | `#F2C14E` | Highlights |
| Muted text | `#5B6168` | Secondary text (6.0:1 on paper) |

**Fonts:**
- **Figtree** for everything.
- **Newsreader** (serif) for greetings and page headlines: "Good afternoon, Schroeder Family".

## Kid look: "Sticker Book"
| Token | Value | Use |
|---|---|---|
| Cream | `#FFF8E7` | Page background |
| Ink | `#2A2140` | Text and 3 px outlines |
| Grape | `#6B4BD8` | Primary buttons (white text 5.8:1) |
| Tomato | `#D64530` | Cheers, hearts |
| Leaf | `#2E9E5B` | "Done" |
| Sun | `#FFC93C` | Stars, stickers |

**Fonts:**
- **Fredoka** for headings.
- **Nunito** for text.

**Shapes:**
- outlined cards
- buttons that look raised and press down (`--kid-raise`)
- check boxes of at least 28 px

## Type scale
8 steps, replacing 31 one-off sizes:

| Token | Size |
|---|---|
| `--text-2xs` | 12 px |
| `--text-xs` | 13 px |
| `--text-sm` | 14 px |
| `--text-md` | 16 px |
| `--text-lg` | 18 px |
| `--text-xl` | 22 px |
| `--text-2xl` | 28 px |
| `--text-3xl` | 36 px |

There's also a `--text-display` size for big headlines.

## Other tokens
- **Spacing:** a 4 px grid, `--space-1` to `--space-12`.
- **Corners:** `--radius-sm` 8, `-md` 12, `-lg` 18, `-xl` 24 px. In the kid look they're bigger.
- **Shadows:** `--shadow-1` to `--shadow-3`.
- **Motion:** `--duration-fast`, `-base`, `-slow`, and `--ease-spring` for check-off pops. Motion turns off for people who prefer reduced motion.
- **Status colors:** scheduled is amber, done is green, overdue is red, each with light and dark versions (all at least 7:1).

## Fonts are self-hosted
The site's security policy only allows fonts from Curiculy itself, so the Latin subsets live in `static/fonts/` with their OFL licenses:
- Figtree, 20 KB
- Newsreader, 58 KB (and 64 KB italic)
- Fredoka, 30 KB
- Nunito, 39 KB

The service worker stores all five on every device once (about 240 KB), so the app keeps its look offline. The page itself preloads only Figtree.

## Voice
- **Parents:** short, warm, plain words, with at most one light seasonal line per screen.
- **Kids:** encouraging and concrete ("Hi Ada!", "1 of 2 done today", "Grab your copy"). Point to their real materials.
- **Never** say the app teaches, and never use internal words (see [Glossary](../1-overview/glossary.md)).

## What's next (Phase 3)
- **Tailwind v4** `@theme` reads these same tokens.
- **Radix-based components** come re-skinned in both looks.
- **Storybook** shows each component in light, dark, kid and seasonal versions.
- **Icons:** Lucide for app chrome, plus a curated set of stickers and illustrations for the kid look.
