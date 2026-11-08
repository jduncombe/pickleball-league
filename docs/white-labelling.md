# White-labelling

The web app's name, copy, logos, favicon, colours, fonts, corner shape and
**terminology** (what a league, team, match… is called) all come from a
**brand**: a folder in [`web/brands/`](../web/brands). The brand
is chosen when the site is built, so each deployment is one brand, and pages
never flash a default name while a config file loads.

| Brand | What it is |
| --- | --- |
| `default` | The standard "Pickleball League" look. Used when no brand is given. |
| `example` | A sample brand ("Example Racquet Club"): different colours, fonts, corner radius, a wordmark logo with dark and compact variants, a footer, and its own terms (ladders, pairs, fixtures, club nights, rests, make-up rounds). It shows every option and doubles as a test that nothing is hard-coded. |

## Choosing a brand

| Where | How |
| --- | --- |
| Local dev | `BRAND=example npm run dev` (in `web/`) |
| Local build | `BRAND=example npm run build` |
| Docker | `BRAND=example docker compose up --build` |
| AWS deploy | Repository variable `BRAND` (see [deployment.md](deployment.md)) |

An unknown or incomplete brand fails the build, e.g.
`BRAND="acme": brands/acme/ is missing brand.ts, theme.css, terms.json`.

## Making a brand

Copy `web/brands/default` to `web/brands/<name>` and edit four things.

### 1. `brand.ts`: name, copy and images

```ts
import type { Brand } from "@/lib/brand";
import icon from "./icon.svg";
import logo from "./logo.svg";

export const brand: Brand = {
  name: "Acme Sports Club",        // page titles, header, footer
  shortName: "Acme",               // header on small screens
  description: "League nights at Acme: fixtures, courts and results.", // meta description
  logo,                            // header logo
  logoHeight: 28,                  // px; width follows the image's aspect ratio
  showNameInHeader: true,          // false if the logo already contains the name
  icon,                            // browser tab icon
  // Optional:
  // logoDark,                     // logo for dark mode, if `logo` lacks contrast
  // logoCompact: icon,            // narrower logo for phones (e.g. just the mark)
  // footer: { text: "Run by Acme", href: "https://acme.example" },
};
```

The full type, with comments, is in
[`web/src/lib/brand.ts`](../web/src/lib/brand.ts). Images can be SVG or PNG,
and are fingerprinted and cached by the build.

### 2. `theme.css`: colours, fonts and shape

Every colour, font and radius in the app is a CSS variable. Components only
use these, so a brand restyles the whole app by setting them, for light mode
and for dark mode:

| Token | Used for |
| --- | --- |
| `--bg`, `--surface`, `--text`, `--muted`, `--border` | Page background, cards and inputs, body text, secondary text, lines |
| `--accent`, `--accent-contrast` | Primary buttons, links, active tabs, winners; text on accent |
| `--live`, `--live-contrast` | Matches on court; text on it |
| `--danger` | Errors and invalid score boxes |
| `--dupr` | Teams whose players all have DUPR IDs |
| `--suggested-bg` | Highlighted "earliest round" matches |
| `--font-body`, `--font-heading`, `--font-size` | Body and heading typefaces, base size |
| `--radius`, `--radius-control` | Card corners; button and input corners |

Optional tokens. When a brand doesn't set them, they fall back as shown:

| Token | Falls back to | Used for |
| --- | --- | --- |
| `--accent-text` | `--accent` | The accent as **text** on surfaces: links, winners, "completed"/"verified" badges. Set this when the accent is a light colour that's fine as a button background but unreadable as text (e.g. lime on white). |
| `--header-bg`, `--header-text`, `--header-border` | `--surface`, `--text`, `--border` | The top bar |
| `--header-button-bg`, `--header-button-text` | `--accent`, `--accent-contrast` | The "New league" button in the top bar (so it stays visible on a coloured bar) |
| `--heading-weight`, `--heading-transform` | `700`, `none` | Heading weight and case (e.g. `uppercase`) |

See [`web/brands/default/theme.css`](../web/brands/default/theme.css) for the
defaults. A brand that wants a web font can add an `@import` (e.g. Google
Fonts) at the top of its `theme.css` and name the font in `--font-body` or
`--font-heading`.

Check text contrast in both modes (`--accent-contrast` on `--accent`,
`--text` on `--surface`, `--accent-text` on `--surface`, `--header-text` on
`--header-bg`, and so on). Aim for WCAG AA, 4.5:1.

### 3. Images

Put the logo, icon and any variants in the brand folder and import them in
`brand.ts`.

### 4. `terms.json`: terminology

The domain words in the UI and in API messages come from a terminology
table. A brand's `terms.json` lists only the words it changes. Each entry
can set the singular (`one`), the plural (`other`, which defaults to `one`
plus "s") and the indefinite article (`article`: "a", "an", or "").

```json
{
  "league": { "one": "ladder", "other": "ladders" },
  "team": { "one": "pair", "other": "pairs" },
  "match": { "one": "fixture", "other": "fixtures" },
  "week": { "one": "club night", "other": "club nights" },
  "bye": { "one": "rest", "other": "rests" },
  "catchUpRound": { "one": "make-up round", "other": "make-up rounds" }
}
```

| Key | Default | Where it appears |
| --- | --- | --- |
| `league` | league / leagues | Navigation, league lists, setup, banners |
| `season` | season | Setup summary ("…in the season") |
| `week` | week / weeks | Week tabs and picker, "matches per week", headers |
| `round` | round / rounds | Round cards, "R1" labels (first letter), suggestions |
| `catchUpRound` | catch-up round | Odd team counts: last round of the week |
| `bye` | bye | Round cards ("Bye: …"), setup summary |
| `team` | team / teams | Everywhere teams are listed, counted or validated, and the "Team 4" fallback name |
| `player` | player / players | Setup, teams page, validation |
| `match` | match / matches | Fixtures between two teams: live view, schedule, setup |
| `game` | game / games | Scoring ("games are first to 11", score errors) |
| `court` | court / courts | Live view, setup, header |
| `ratingSystem` | DUPR | Rating-system name in hints ("…player's DUPR profile") |
| `ratingId` | DUPR ID / DUPR IDs | Player ID field, legend |
| `rating` | rating | Teams page column |

The defaults are in
[`web/src/lib/default-terms.json`](../web/src/lib/default-terms.json).
Components use the helpers in [`web/src/lib/terms.ts`](../web/src/lib/terms.ts):
`term("team", n)` gives "team" or "teams", `Term()` capitalises, `count(3,
"team")` gives "3 teams", and `a("league")` gives "a league" (or "an event").
**New UI text must use these helpers rather than hard-coding a domain word.**

**The API uses the same table** (`api/app/terms.py`, same keys and defaults; a
test keeps the two in sync). That covers the "Team 4" fallback name, setup
validation ("Pair 2 needs at least one player"), conflict messages ("No free
courts") and score errors. The API loads the brand's `terms.json` from:
- docker-compose: the `TERMS_FILE` setting, pointed at the mounted
  `web/brands/<BRAND>/terms.json` automatically;
- AWS: the `TERMS_JSON` setting, which Terraform's `brand` variable fills from
  the same file;
- local: `TERMS_FILE=../web/brands/<name>/terms.json uvicorn app.main:app`.

Terminology covers domain nouns. General UI words ("Save", "Edit setup",
"Standings", "Verify") and pickleball's scoring rules aren't terms.

## API name

The API's docs page title (`/api/docs`) uses `APP_NAME` (default
"Pickleball League"). Set it to match the brand:
- docker-compose: `APP_NAME="Acme Sports Club" docker compose up`;
- AWS: the `APP_NAME` repository variable, passed to Terraform as `app_name`.

## What isn't branded

- **General UI words and scoring rules** (see above).
- **URLs** (`/leagues`, `/league/teams/…`) stay the same for every brand.
- **Infrastructure names** (`project` in Terraform, Docker image names) are
  separate from the brand.

## CI

CI builds **every** brand folder on every PR, so a broken brand fails the
PR. For the `example` brand it also checks the page title, and
fails if the default name ("Pickleball League") appears anywhere in the
output, which would mean something branded was hard-coded. The API tests
check that the API's default terms match the web app's, and that a brand's
terms reach API messages.
