# CardSnap app-auth API

Base URL: `https://<crm-host>/api/app-auth/` · JSON in, JSON out · HTTPS only.
Errors are always `{"code": "...", "message": "..."}`.

**Tokens.** `access_token` is a JWT (HS256, 15 min, claims `sub` = user id, `token_version`). `refresh_token` is an opaque
string (30 days, rotated on every use). Send `Authorization: Bearer <access_token>`. Store both in the platform
secure storage (Keychain / Keystore).

Every successful sign-in (`register`, `login`, `google`) and `refresh` returns:

```json
{"access_token": "eyJ...", "refresh_token": "Zk3...", "token_type": "Bearer", "expires_in": 900,
 "user": {"id": "uuid", "email": "ann@example.com", "name": "Ann", "avatar_url": "", "auth_provider": "password", "status": "active"}}
```
(`refresh` returns only the four token fields.)

## Endpoints

| Method + path | Body / query | Success | Errors |
|---|---|---|---|
| `POST register` | `{email, password (min 8), name}` | 201 sign-in payload + `"email_verified": false` | 400 `invalid_email`, `weak_password`; 409 `email_exists`; 429 `rate_limited` |
| `POST login` | `{email, password}` | 200 sign-in payload | 401 `invalid_credentials` ("Invalid email or password", same for unknown email); 403 `account_revoked`; 429 |
| `POST google` | `{id_token}` | 200 sign-in payload | 401 `invalid_google_token`; 403 `account_revoked`; 429 |
| `POST refresh` | `{refresh_token}` | 200 new token pair (old one is dead) | 401 `invalid_refresh_token` (unknown, expired, revoked or **reused**); 403 `account_revoked` |
| `POST logout` | `{refresh_token}` | 200 `{"ok": true}` (always) | |
| `POST forgot-password` | `{email}` | 200 `{"ok": true, "message": ...}` (identical whether or not the email exists) | 429 |
| `POST reset-password` | `{token, new_password}` | 200 `{"ok": true}`; all sessions end | 400 `invalid_token` (bad, expired >30 min, or already used), `weak_password` |
| `GET verify-email?token=` | | 200 plain text (open from the email link) | 400 |
| `POST apple` | `{identity_token, name?}` | 200 sign-in payload | 400 `email_missing`; 401 `invalid_apple_token`; 403 `account_revoked`; 429 |
| `GET me` | Bearer | 200 `{id, email, name, avatar_url, auth_provider, status}` | 401 `invalid_token`; 403 `account_revoked` |

### Client behaviour
- On any 401 from an API call: call `refresh` once, retry; if `refresh` also fails, sign the user out locally.
- On 403 `account_revoked` (anywhere): sign out locally and show "Your account has been disabled".
- A reused refresh token revokes that whole login family, so never retry `refresh` with an old token.
- `register` on an existing email returns 409. If that account was created with Google (no password yet), tell the
  user to use Google, or "Forgot password" to add a password.
- Reset email carries a token (and a link `APPAUTH_RESET_URL?token=...` when configured): pass it to `reset-password`.

### Rate limits (per IP and per email, 10-minute window; `429 rate_limited`)
login 30/IP, 10/email · register 30/IP, 5/email · forgot-password 30/IP, 3/email · google 30/IP · reset 30/IP.

## Account management (all need `Authorization: Bearer <access_token>`)

**Re-authentication.** Delete and change-password prove it is the owner, not just a holder of a token. Send **one** of:
`current_password` (password users) · `id_token` (a *fresh* Google ID token, same account) · `identity_token` (a *fresh* Apple
token, same account). Missing proof is 400 `reauth_required`; wrong proof is 403 `reauth_failed` (not 401, so your refresh
logic does not loop). Limit: 10 attempts per 10 minutes.

### Delete account: `DELETE me`
Body: the re-auth field above, e.g. `{"current_password": "..."}` or `{"id_token": "..."}`.
Returns `200 {"ok": true}`. The account is closed (soft delete) and every session ends at once. The same email can never
sign in again with that account. Clear all local data and tokens in the app. Apple users: Apple also asks apps to revoke
the Sign-in-with-Apple token on deletion; this server does not do that yet.

### Change / set password: `POST change-password`
Body: `{"new_password": "min 8", ...re-auth field}`.
- Password users: `{"current_password": "old", "new_password": "new"}`.
- **Google or Apple-only users have no password.** To set one they send a fresh provider token instead:
  `{"id_token": "<fresh google token>", "new_password": "new"}` (Apple: `identity_token`). They can also use
  forgot-password then reset-password. After this they can sign in either way.
- Ends **every** session, including this device's. The response is `200 {"ok": true, access_token, refresh_token,
  token_type, expires_in}`: replace your stored tokens with these. Other devices get 401 and must sign in again.
- Errors: 400 `weak_password`, `reauth_required`; 403 `reauth_failed`.

### Sign out everywhere: `POST logout-all`
No body. Returns `200 {"ok": true}`. All refresh tokens are deleted and every access token (this device's too) stops
working, so clear local tokens and go to the sign-in screen.

### Sign in with Apple: `POST apple`
Body: `{"identity_token": "<from Apple>", "name": "<optional>"}`. Returns the normal sign-in payload.
- Verified server-side: signature (Apple keys), issuer, expiry, and audience = the app bundle ID (`APPLE_CLIENT_ID`).
- **Hidden email:** if the user chooses "Hide My Email", the email is an `@privaterelay.appleid.com` address. It is
  stored as their account email. It is already verified by Apple, but it only forwards mail from domains registered with
  Apple, so verification and password-reset emails to it may not arrive. Apple users should sign in with Apple.
- **Real email:** if the email matches an existing account, Apple is linked to it (no duplicate).
- **Email only comes the first time.** Later tokens may carry no email; the account is then found by Apple's stable
  user id. If a token has no email and no account exists yet, you get 400 `email_missing`: tell the user to remove the
  app from their Apple ID settings (Sign in with Apple) and try again.
- **Name is one-time.** Apple gives the full name only to the app, only on the first sign-in, and never inside the
  token. Send it as `name` on that first call. It is display-only, cut to 255 characters, and ignored once the account exists.
- Flutter: `sign_in_with_apple`, send `credential.identityToken` and, on first sign-in, `givenName + familyName`.

## Google Sign-In
Flutter (`google_sign_in`): create the sign-in with `serverClientId: <GOOGLE_WEB_CLIENT_ID>`, read
`(await account.authentication).idToken`, and POST it as `id_token`. The server verifies signature (Google JWKS), `iss`,
`exp`, `aud` (web, Android or iOS client ID from env) and `email_verified`; name/avatar/email come from the verified
token, never from the client. A Google email that matches an existing account links to it.

## Admin
Staff only (Django `is_staff`): `/app-users/` list, stats, signups chart, filters, CSV export; `/app-users/<id>/` detail with
Revoke (with reason), Restore, Force logout, Delete (soft). Every action writes an `app_auth_events` row.
