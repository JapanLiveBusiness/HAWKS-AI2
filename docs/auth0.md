# Auth0 login and security

Canonical application URL: https://ai-baseball.f-polaris.jp/

## Access policy

The requested policy is `all_verified`: any Auth0 registration with a verified
email may enter. Auth0 authentication alone does not grant access before email
verification. Each user sees only their own BET file. Existing legacy history is
never assigned to the first person who registers.

The application fails closed if Auth0 is disabled, missing, or invalid. There is
no automatic unauthenticated single-user fallback. Existing signed sessions are
checked on navigation/reruns and every 60 seconds while the app remains open.
Sessions require unexpired identity claims and expire no later than eight hours
after authentication (or issuance when auth_time is absent). Browser background
throttling can delay the periodic check; every full page rerun checks again.
Logout clears app state and the Streamlit identity cookie; it does not terminate
the separate Auth0 dashboard/SSO session. prompt=login requires fresh login.

## Reuse the existing Auth0 application

Reuse the tenant and social connections already used by the existing
MY AI BASEBALL login at the canonical URL. Do not create a new tenant or
replace the current provider before inspecting its configuration. The new
Streamlit integration requires a **Regular Web Application** client. If the
existing client has a different application type, use a separate Regular Web
Application client within that same tenant and retain its social connections.
The entry screen follows the supplied black/lime MY AI BASEBALL design.

- Allowed Callback URLs: `https://ai-baseball.f-polaris.jp/oauth2callback`
- Allowed Logout URLs: `https://ai-baseball.f-polaris.jp/`
- Allowed Web Origins: `https://ai-baseball.f-polaris.jp`
- Preserve existing callback/logout entries still required by the older app;
  append the Streamlit callback rather than replacing an unknown integration.
- Enable the intended database/social connection and email verification delivery.
- Enable Auth0 brute-force protection and suspicious-IP throttling.
- Configure MFA according to the tenant's available plan; prefer requiring it.
  Confirm enrollment and recovery with the operator before enforcement.

Use exact URLs, not wildcard callbacks. The IP HTTP URL is no longer an app entry
point after deployment: port 8501 is bound to loopback for health checks and
Traefik serves the HTTPS hostname. Existing Tailscale/Cloudflare access policies
remain additional restrictions; this change does not grant public network access.

## Secrets and activation

Set these four GitHub Actions secrets via Settings > Secrets and variables > Actions:

- AUTH0_DOMAIN (tenant Domain, without protocol)
- AUTH0_CLIENT_ID
- AUTH0_CLIENT_SECRET
- AUTH0_COOKIE_SECRET (cryptographically random, at least 32 characters)

Do not paste secret values into chat, code, issues, or logs. Alternatively mount
`/opt/hawks-ai/auth0/secrets.toml`, owned by the operator with mode 0600, using
`.streamlit/secrets.toml.example` as the template. The workflow writes the requested
`all_verified` policy. For a private membership deployment use `allowlist` with
exact `allowed_subjects` or verified `allowed_emails` arrays.

The deployment validates the mounted configuration in the new container image
before stopping the existing app. Missing or malformed configuration stops
deployment and leaves the old container running. This means an unsuccessful
activation does **not** secure the old deployment: verify the login gate after a
successful deployment. Do not merge the activation PR until credentials and
callback settings are ready.

Authentication uses Streamlit OIDC with Authlib, including protocol-level
signature/issuer/audience/state/nonce validation. Application code consumes the
validated identity; access/ID tokens are not exposed. CORS/XSRF stay enabled.
Traefik adds nosniff, frame denial, no-referrer and HSTS headers. The app container
drops Linux capabilities and forbids privilege escalation. Secrets and personal
BET files are excluded from the image build context.

## Existing history

The legacy `/app/data/bet_records.json` is retained. It is not visible to new
accounts. After the owner has registered, verify their exact Auth0 user_id/sub
and preview a migration on the server:

```bash
python scripts/migrate_legacy_bets.py --auth0-sub 'auth0|verified-owner-id'
```

After verifying the intended owner and record count, add `--apply`. Existing
target records require `--merge`. The source remains intact. Never derive the
owner from the first registration or an unverified email.

## Acceptance checks

1. Confirm all CI tests and Docker startup checks pass.
2. In a fresh browser session, open the HTTPS home page and direct page URLs:
   no BET data or export is available before login.
3. Register an account: unverified email is refused, verified email succeeds.
4. Verify login/logout and expiry, including an already-open tab.
5. Use two authorized test accounts to check isolated histories and exports.
6. Confirm the HTTP Tailscale IP:8501 endpoint is no longer accessible, while
   HTTPS and the local health check work.
7. Verify MFA/attack protection in Auth0 and inspect tenant login failure logs.

References:
- https://docs.streamlit.io/develop/api-reference/user/st.login
- https://docs.streamlit.io/develop/concepts/connections/authentication
- https://auth0.com/docs/get-started/applications/application-settings
