# Cloudflare Access front-door authentication

## Goal

Protect `https://ai-baseball-studio.f-polaris.jp/` before requests reach Streamlit. Authentication and identity-provider credentials stay in Cloudflare; the application does not store user passwords, OAuth client secrets, or login tokens.

## Request flow

```text
Browser
  -> Cloudflare DNS / proxy
  -> Cloudflare Access policy
       -> identity provider login
       -> allow/deny decision
  -> origin / Streamlit :8501
```

Deployment remains separate:

```text
GitHub Actions
  -> Tailscale (TAILSCALE_AUTHKEY)
  -> SSH (DEPLOY_SSH_KEY)
  -> production server
  -> Docker / Streamlit
  -> Cloudflare Access service token health check
```

## Cloudflare configuration

Create a Cloudflare Zero Trust Access self-hosted application for:

- Application domain: `ai-baseball-studio.f-polaris.jp`
- Path: all paths
- Session duration: choose an organization-appropriate duration

Create an `Allow` policy for the people who should be able to use the application. Prefer an existing organization identity provider (for example Google or Microsoft) and restrict by explicit users/groups or the organization's email domain. Do not use a public `Everyone` allow rule for the protected application.

Also create a Cloudflare Access Service Token for GitHub Actions. Add a Service Auth policy that permits only that service token to this application. GitHub Actions uses it only for the post-deploy health check.

## GitHub Actions secrets

Add these repository/environment secrets in GitHub. Never commit their values:

- `CF_ACCESS_CLIENT_ID`
- `CF_ACCESS_CLIENT_SECRET`

Existing deployment secrets remain unchanged:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PORT`
- `TAILSCALE_AUTHKEY`

The protected-site verification sends the service-token credentials in these headers:

- `CF-Access-Client-Id`
- `CF-Access-Client-Secret`

## Safe rollout order

1. Merge/deploy this repository change first. Until the two Cloudflare service-token secrets exist, the protected public health check is intentionally skipped so the current deployment is not broken during migration.
2. In Cloudflare Zero Trust, create the self-hosted Access application and human `Allow` policy.
3. Create the Access Service Token and its Service Auth policy.
4. Store its client ID and secret in GitHub as `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET`.
5. Run the production deployment workflow and confirm `Verify protected public site` succeeds.
6. Open the site in a private browser window and confirm Cloudflare prompts for authentication before Streamlit is visible.
7. Confirm an unauthorized identity is denied.

## Security boundary

Cloudflare Access is the authentication boundary. Streamlit remains responsible for application behavior, not primary authentication. This minimizes application changes and avoids handling passwords inside `main.py` or `app.py`.

Do not expose the origin directly on a public hostname or public port that bypasses Cloudflare Access. Network/firewall rules should allow only the intended Cloudflare/origin path and administrative access through Tailscale.

## Token handling

Human identity-provider tokens/cookies are issued and validated by Cloudflare Access and are not persisted by this repository.

The CI service-token secret is stored in GitHub Actions Secrets and injected into the health-check step at runtime. The verification script does not print the values. Rotate the Service Token in Cloudflare and update both GitHub secrets if it is ever exposed.
