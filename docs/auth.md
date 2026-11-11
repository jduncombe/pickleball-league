# Accounts, sign-in & permissions

Every page and API endpoint (except `/health` and the sign-in endpoints) needs
a signed-in account. Sign-in is an email and password **plus a code from an
authenticator app** (TOTP); there's no way to turn the second step off.

## Roles

| Role | Web app | Leagues | Scoring app (`/scoring/*`) | Accounts |
| --- | --- | --- | --- | --- |
| **Admin** | Yes | All of them, including ones made before accounts existed | Any league | Create, change, deactivate, reset |
| **User** | Yes | The leagues they create, and ones shared with them | Those leagues | – |
| **Umpire** | No (the sign-in page refuses them) | – | Any **active** league: claim a court, follow its match, record its score | – |

Details:

- A league belongs to the user who creates it (`leagues.owner_id`). Leagues
  that existed before accounts have no owner, so only admins see them.
- **Sharing:** the owner (or an admin) can share a league with other user
  accounts, by email, on the league's **Sharing** tab. They then run it like
  the owner (setup, schedule, results, the scoring app), but only the owner
  and admins can delete the league or change who it's shared with. Someone
  it's shared with can leave it. Leagues can't be shared with umpires (they
  already score every active league) or admins (they see every league).
- An umpire can record a score only for the match on a court **they have
  claimed**, while it's in progress. They can release only their own claims.
  The league's organiser and admins can release any claim, e.g. one held by a
  lost tablet, and can correct any result.
- What a role or owner can't see is answered with **404**, the same as
  something that doesn't exist: it doesn't reveal what's there, and CloudFront
  turns 403s into the site's 404 page anyway (see [deployment.md](deployment.md)).
  Not being signed in, or an expired session, is **401**.

## First admin

There's no self sign-up: an admin creates every account. The first admin is
created from the command line, where the API runs:

```bash
# Local (in api/, with the virtualenv active)
python -m app.cli create-user --email you@example.com --name "Your Name"

# docker-compose
docker compose exec api python -m app.cli create-user --email you@example.com --name "Your Name"
```

It prompts for the password (12 to 256 characters). `--role user` or
`--role umpire` makes other kinds of account. On AWS, run the same command as a
one-off ECS task (or with ECS Exec) using the API's task definition; see
[deployment.md](deployment.md#first-admin).

Then sign in at `/login/`. The first sign-in shows a QR code to add to an
authenticator app (Google Authenticator, Microsoft Authenticator, 1Password,
…); entering a code from it finishes the setup.

Admins manage everyone else on the **Users** page (`/users/`): add an account
with a temporary password, change its role, set a new password, reset its
authenticator, or deactivate it.

## Signing in

```
POST /auth/login       {email, password, client}        → {mfa_token, mfa_setup_required}
POST /auth/mfa/setup   {mfa_token}                      → {secret, otpauth_uri, qr_data_uri}   (first sign-in only)
POST /auth/mfa/verify  {mfa_token, code, client}        → {user, expires_at, access_token?}
```

1. The password step returns a **5-minute, single-use MFA token**. It proves
   the password only, so it isn't accepted as a session anywhere else.
2. Accounts without an authenticator get a new TOTP secret from
   `/auth/mfa/setup`. Each call replaces the previous unconfirmed one; once a
   code has been accepted, setup is refused until an admin resets it.
3. A current 6-digit code starts the session:
   - **`client: "web"`** (the web app): the access token is set as an
     **HttpOnly, Secure, SameSite=Strict** cookie (`__Host-session`). It's never
     in the response body, so page scripts can't read it.
   - **`client: "app"`** (the scoring app): the access token is returned in the
     body, to send as `Authorization: Bearer <token>`.

Sessions last 8 hours (`ACCESS_TOKEN_TTL_SECONDS`); there are no refresh
tokens, so after that you sign in again. `POST /auth/logout` revokes the token
at once. `GET /auth/me` is the signed-in account. `POST /auth/password`
(current password, new password and a code) changes your password and signs
you out everywhere.

```bash
# The scoring app's flow, with curl
STEP=$(curl -s localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "ump@example.com", "password": "…", "client": "app"}')
TOKEN=$(curl -s localhost:8000/auth/mfa/verify -H 'Content-Type: application/json' \
  -d "{\"mfa_token\": \"$(echo "$STEP" | jq -r .mfa_token)\", \"code\": \"123456\", \"client\": \"app\"}" \
  | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" localhost:8000/scoring/leagues
```

## How credentials are protected

| What | How |
| --- | --- |
| Passwords | **Argon2id** (argon2-cffi, RFC 9106 parameters), salted per password; rehashed at sign-in when the parameters change. 12 to 256 characters. Never logged or returned. |
| Tokens | **PASETO v4.local**: XChaCha20 encryption with a BLAKE2b MAC, so they can't be forged, altered or read by the client. Each carries the account, an expiry, a unique id (`jti`) and the account's token version. The token's purpose (`access` or `mfa`) is bound in as the PASETO implicit assertion, so an MFA-step token can't be used as a session or the reverse. |
| Revocation | Sign-out stores the token's id until it would have expired. Changing a password, role or active flag, or resetting MFA, bumps the account's token version, which signs it out everywhere at once. |
| TOTP | RFC 6238 (6 digits, 30 seconds), 160-bit secrets, one step of clock drift allowed. A code is accepted **once**: the last used time step is stored, so a code can't be replayed. Secrets are **encrypted at rest** with AES-256-GCM, bound to the account id. |
| Keys | One master secret, `AUTH_SECRET_KEY`, from which HKDF-SHA256 derives the token key and the TOTP encryption key. In AWS it's generated into Secrets Manager by Terraform and injected by ECS. Without it (local and docker-compose), a key is generated once into `AUTH_SECRET_FILE` (`./data/auth_secret`, mode 0600). Changing it signs everyone out and makes every authenticator need resetting. |
| Guessing | Wrong passwords and wrong codes both count towards a **lockout**: 5 in a row lock the account for 15 minutes. Sign-in attempts are also **rate-limited per client IP** (20 a minute) against password spraying. |
| Enumeration | A wrong email and a wrong password get the same message and take the same time (a dummy hash is checked). Only someone who knows the password learns that an account is locked. |
| CSRF | The session cookie is SameSite=Strict, and requests that change data with the cookie must also send `X-Requested-With: fetch`, which a cross-site form can't and a cross-site script can't without a CORS preflight the API refuses. |
| Caching | Sign-in responses are `Cache-Control: no-store`. |

The rate limit counts per API process (in memory), and needs to know which
`X-Forwarded-For` entry to trust: `TRUSTED_PROXY_HOPS` is 2 in AWS (CloudFront
then the ALB), 1 in docker-compose (nginx) and 0 when the API is reached
directly. In docker-compose the API's own port 8000 is also published for
convenience; requests sent straight to it can set their own
`X-Forwarded-For`, so the per-IP limit only holds for traffic through the web
container (the account lockout always applies).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | – | Master secret (at least 32 characters). Set it in production; Terraform does. |
| `AUTH_SECRET_FILE` | `./data/auth_secret` | Where a generated key is kept when `AUTH_SECRET_KEY` is unset |
| `ACCESS_TOKEN_TTL_SECONDS` | `28800` (8 hours) | How long a sign-in lasts |
| `COOKIE_SECURE` | `true` | Secure session cookie (`__Host-session`). Browsers accept it on `http://localhost`; set `false` only to sign in over plain HTTP from another host (the cookie is then `session`). |
| `TRUSTED_PROXY_HOPS` | `0` | Proxies in front of the API that append to `X-Forwarded-For` |
| `LOGIN_ATTEMPTS_PER_MINUTE` | `20` | Sign-in attempts per client IP per minute |

## Not done yet

- A league can't be handed over to another owner, and sharing has one level
  (co-organiser); there's no read-only access.
- Umpires can score any active league; there's no per-league umpire list.
- No self-service password reset by email; an admin sets a new password.
- No recovery codes: a lost authenticator needs an admin to reset it (and
  ideally a new password too, since the password alone then gets as far as
  enrolling a new authenticator).
- The rate limit is per API process; with more than one API task, put AWS
  WAF rate limiting in front (see [deployment.md](deployment.md)).
