# White-labelling

The web app's name, copy, logos, favicon, colours, fonts and corner shape all
come from a **brand**: a folder in [`web/brands/`](../web/brands). The brand
is chosen when the site is built, so each deployment is one brand, and pages
never flash a default name while a config file loads.

| Brand | What it is |
| --- | --- |
| `default` | The standard "Pickleball League" look. Used when no brand is given. |
| `example` | A sample brand ("Example Racquet Club"): different colours, fonts, corner radius, a wordmark logo with dark and compact variants, and a footer. It shows every option and doubles as a test that nothing is hard-coded. |

## Choosing a brand

| Where | How |
| --- | --- |
| Local dev | `BRAND=example npm run dev` (in `web/`) |
| Local build | `BRAND=example npm run build` |
| Docker | `BRAND=example docker compose up --build` |
| AWS deploy | Repository variable `BRAND` (see [deployment.md](deployment.md)) |

An unknown brand fails the build: `BRAND="acme": no brands/acme/brand.ts`.

## Making a brand

Copy `web/brands/default` to `web/brands/<name>` and edit three things.

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

See [`web/brands/default/theme.css`](../web/brands/default/theme.css) for the
defaults. A brand that wants a web font can add an `@import` (e.g. Google
Fonts) at the top of its `theme.css` and name the font in `--font-body` or
`--font-heading`.

Check text contrast in both modes (`--accent-contrast` on `--accent`,
`--text` on `--surface`, and so on).

### 3. Images

Put the logo, icon and any variants in the brand folder and import them in
`brand.ts`.

## API name

The API's docs page title (`/api/docs`) uses `APP_NAME` (default
"Pickleball League"). Set it to match the brand:
- docker-compose: `APP_NAME="Acme Sports Club" docker compose up`;
- AWS: the `APP_NAME` repository variable, passed to Terraform as `app_name`.

## What isn't branded

- **Sport and domain wording** ("league", "court", "DUPR ID", pickleball
  scoring) is product language, not brand, so it's in the components.
  Renaming those terms per brand (e.g. "ladder" instead of "league") would
  need a terminology table in the brand. That's not done yet.
- **Infrastructure names** (`project` in Terraform, Docker image names) are
  separate from the brand.

## CI

CI builds the `example` brand on every PR. It checks the page title, and
fails if the default name ("Pickleball League") appears anywhere in the
output, which would mean something branded was hard-coded.
