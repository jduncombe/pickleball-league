# Pickleball League Web

Next.js (App Router) interface for the league API, built as a static export
(`out/`) for S3 + CloudFront. See the [root README](../README.md) for setup and
[docs/architecture.md](../docs/architecture.md) for how it talks to the API.

```bash
npm install
cp .env.example .env.local   # API_URL=http://localhost:8000
npm run dev                  # http://localhost:3000, /api/* forwarded to API_URL
npm run lint                 # ESLint
npm run typecheck            # TypeScript
npm run format               # Prettier (format:check to only check)
npm run build                # static export to out/
BRAND=example npm run dev    # run with another brand (see docs/white-labelling.md)
```

| Path | Purpose |
| --- | --- |
| `src/app/page.tsx` | Default screen: live dashboard for the last-viewed league |
| `src/app/leagues/new/` | New league: setup step 1 (basics) |
| `src/app/league/` | Live dashboard for one league (`/league/?id=…`) |
| `src/app/league/teams/` | Teams & players (read-only once the league is created) |
| `src/app/league/setup/` | League setup steps 1–2, "Create the league", edit setup |
| `src/components/setup/` | Setup forms (basics, teams & players) |
| `src/app/league/matches/` | Schedule, result entry, standings |
| `src/app/league/sharing/` | Who the league is shared with; share by email, remove, leave |
| `src/app/login/` | Sign in: password, then authenticator setup or code |
| `src/app/users/` | Account management (admins) |
| `src/app/account/` | Change your password |
| `src/lib/auth.tsx` | Session context: redirects to sign-in, sign-out, the current user |
| `src/lib/api.ts` | Typed API client (same-origin `/api`, session cookie, `X-Requested-With`) |
| `src/lib/brand.ts` | The `Brand` type; the active brand is imported as `@brand/brand` |
| `brands/<name>/` | White-label brands: `brand.ts` (name, copy, logos), `theme.css` (colour/font tokens), images |
| `src/lib/routes.ts` | Builds league page URLs |
| `nginx.conf.template` | Serves `out/` and proxies `/api/*` in the Docker image |
