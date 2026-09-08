# Prediction mail delivery component (not enabled)

Implemented locally: plain-text template builder, TLS SMTP transport, explicit
enable/confirmation gate, immutable recipient, date freshness guard, persistent
at-most-once attempt ledger, preview CLI. No live credentials have been set and
no email has been sent. This component is not yet connected to the public UI or
the prediction selection pipeline. No recurring scheduler has been installed.

Recipient: `tsutsumi41@gmail.com`. Preview plan: `{ "date": "YYYY-MM-DD",
"picks": [{ "team": "阪神", "opponent": "横浜", "giving_team": "阪神",
"handicap": "1.0", "amount": 300000 }] }`. Amounts are virtual points, displayed
in units of 10,000; handicap is displayed only on the explicit giving side.

Preview: `python scripts/preview_prediction_mail.py --plan private/mail-plan.json
--sender owner@example.com` (one command line). Preview never sends mail.

Secure runtime configuration needed: SMTP_HOST, SMTP_PORT, SMTP_SECURITY
(`ssl` or `starttls` only), SMTP_USER, SMTP_PASSWORD, and confirmed From address.
Use a mail-specific credential, not an ordinary account password. Store only in
deployment secret storage. `PREDICTION_MAIL_ENABLED=true` and `confirmed=True`
are both required to send. Ledger must live on persistent private storage.

When SMTP fails or a process stops during delivery, the entry remains uncertain
or sending. Do not automatically retry or delete it: check provider delivery
logs first. `sent` means SMTP accepted the message, not verified inbox delivery.

Before scheduled integration, resolve: positive-balance reduced amount;
probability-to-amount mapping; zero-balance behavior; whether weekend/holiday
mail is one digest before the first game or separate batches. Agreed basis:
weekly summaries with all previous-week cumulative profit carried forward;
Tuesday-Friday 17:20 JST, Mondays excluded; weekends/holidays 40 minutes before
game start; >55% top three, otherwise top two with reduced cap. Do not invent
missing amounts or use stale/after-start predictions. Activate only after sender
setup, an explicitly authorized test email, and end-to-end integration tests.
