# tri-buddy-agent

Phase 1 scaffold for a lightweight bot service.

## Files
- bot.py: Flask app exposing health and message endpoints.
- telegram_client.py: small helper for talking to the Telegram Bot API.
- requirements.txt: Python dependencies.

## Local run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```

## Endpoints
- GET / -> service status
- GET /health -> liveness plus OpenRouter status (see below)
- POST /message -> forwards a message to Telegram
- POST /api/webhook/telegram -> production Telegram webhook

### /health

Public by default and safe to expose, because it reports booleans only:

```json
{"status":"ok","openrouter":{"configured":true,"reachable":true,"key_valid":true},
 "models":{"chain_length":4,"all_free":false},"detail":"public"}
```

Set `HEALTH_TOKEN` and pass it as `?token=<...>` or an `X-Health-Token` header to also get
the key label, credit limit, remaining free requests and the resolved model chain. Those are
gated because the endpoint is reachable from the internet on Render.

The key check calls OpenRouter's `GET /key`, which validates auth **without** spending
model quota, so it is safe on every health check. To confirm generation end to end, add
`&probe=model` -- that makes a model request, which may incur a charge if Llama 3.1 70B
answers. The probe is token-gated and never automatic.

`status` becomes `degraded` when the key is missing or rejected, but the HTTP code stays
**200**: the service itself is still healthy and degrades gracefully, so a non-2xx would only
make Render restart a working process. Add `?strict=1` for a monitor that wants 503 instead.

After a deploy:

```bash
curl "https://<your-host>/health?token=<HEALTH_TOKEN>&probe=model"
```

## Agent model (Hermes)

The live system prompt lives in `app/agent/prompt.py`. The agent uses Llama 3.1 70B as its
primary OpenRouter model (which may incur charges), then falls back to free models. It
replies in whichever language the user wrote in (Bengali in -> Bengali out, English in ->
English out).

Model fallback chain, tried in order:

1. `meta-llama/llama-3.1-70b-instruct` - primary; may incur charges
2. `nvidia/nemotron-3-ultra-550b-a55b:free`
3. `qwen/qwen3.8-27b:free`
4. `apodex/apodex-1.1-mini:free`

`app/services/models.py` walks the chain, skipping any model that returns 402/403/408/429/5xx
or an empty body. If every model fails due to quota or rate limits the user is told to retry
shortly; any other outage falls back to the deterministic orchestrator reply.
The system prompt reads this same chain at request time, so its model and cost instructions
stay accurate when these environment variables change.

Configuration:

- `OPENROUTER_MODELS` - comma-separated chain. Overrides the default chain; include paid
  models only when you intend to allow their charges.
- `OPENROUTER_MODEL` - single primary prepended to the default chain. **Ignored unless it is
  a `:free` model**, so a stale paid value cannot override the configured primary.
- `OPENROUTER_TIMEOUT` - per-attempt timeout in seconds (default 25).

Known commands are matched *before* the model runs, so they actually write to the database:

```
Add lead: <details>
Remember that my <thing> is <value>
What do you know
Draft a proposal email for <client>   ->  then: Approve <id>
```

Anything else goes to Hermes.

Task assignment, team reports, Slack messaging, automatic lead capture, and pull-request
reviews are not enabled in this release. Leads can still be added explicitly with
`Add lead: <details>`.

## Storage

SQLite by default. Set `DATABASE_URL` to a Supabase (or any Postgres) connection string
and the same code runs on Postgres instead - Supabase *is* Postgres, so there is nothing
Supabase-specific here.

**This app never shares a schema with anything else.** Its table names - `leads`, `tasks`,
`reports`, `memories` - are exactly what a business product would also use, so every table
lives in `DB_SCHEMA` (default `tri_buddy`) and `search_path` is pinned to it on each
connection. Pointing `DATABASE_URL` at a database that also holds the Babosayee product
is therefore safe: nothing unqualified can reach another schema's tables.

Using `public` is refused outright unless `DB_ALLOW_PUBLIC_SCHEMA=1`, and the schema name
is validated against an identifier pattern before it is ever interpolated into SQL.

**Use the session pooler or a direct connection, not the transaction pooler.** In Supabase
that means the port 5432 string rather than 6543. `search_path` is passed as a connection
startup option so it survives pooling, but transaction-mode pooling can still reassign
statements between backend sessions, and anything that drops `search_path` would let
unqualified table names resolve against `public` - the exact collision the schema is there
to prevent.

On the free Supabase plan a project pauses after about 7 days of low activity, which this
bot will not hit - it queries on every message. Free projects get 500 MB, far more than
this needs.

Switching backends does not copy data. Nothing currently lives long enough on Render's
ephemeral disk for that to matter, but a Postgres switch does start empty.

A failed database init does not stop the app. A wrong `DATABASE_URL` would otherwise
take the whole service down at boot - including `/health`, leaving no way to see why - so
the error is logged, `/health` reports `database.connected: false` with the reason, and
`status` becomes `degraded`.

Tests run on SQLite. To exercise the Postgres path, point `TEST_DATABASE_URL` at a
throwaway database:

```bash
TEST_DATABASE_URL=postgresql:///some_scratch_db python -m pytest tests/test_postgres.py
```

Those tests create and drop their own `tri_buddy_test` schema and assert that nothing
lands in `public`.

## Seeing images and web pages

Send the bot a photo on Telegram and it reads it; the caption becomes the question. Images
go to a separate free vision chain (`OPENROUTER_VISION_MODELS`, default
`qwen/qwen3.8-27b:free`, then gemma, then `openrouter/free`), with the same fallback
behaviour as the text chain. Images over 5MB are rejected.

Put a link in a message and the page is fetched and included as context, up to three links
per message and 12k characters per page. The bot cannot search, browse, or follow links
found inside a fetched page - it only ever sees pages someone linked explicitly.

Fetching is guarded against SSRF: loopback, private, link-local and reserved addresses are
refused before any request is made, so the bot cannot be used to read cloud metadata or
anything else inside the network. Non-HTTP schemes and non-text responses are refused too.

Fetched text and image contents are framed in the prompt as source material, never as
instructions, and the prompt tells the model to report rather than obey any directions
found inside them.

Slack image uploads are *not* supported - that needs the `files:read` scope, which the app
does not have.

## Telegram setup
1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the bot token into `TELEGRAM_BOT_TOKEN`.
2. Set `TELEGRAM_WEBHOOK_SECRET` to a private value containing 1-256 letters, numbers, underscores, or hyphens. This is required: production rejects webhook updates without the matching secret header.
3. For the production engine (`app.main:app`), point Telegram's webhook at `https://<your-host>/api/webhook/telegram`:
   ```bash
   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://<your-host>/api/webhook/telegram" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```
   On Render, registration happens automatically at startup when `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, and `RENDER_EXTERNAL_URL` are configured. Check `GET /api/webhook/telegram`: `registration_ready` must be `true` and `registration_status` should be `registered`. A `failed` status means startup logs will have the registration error; a service restart retries registration. The bot replies to the chat that sent each update; `TELEGRAM_CHAT_ID` is not needed for webhook replies.

Long replies are split into messages within Telegram's 4,096-character limit.
