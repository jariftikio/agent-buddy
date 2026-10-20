# tri-buddy-agent

Phase 1 scaffold for a lightweight bot service.

## Layout

The production engine is `app.main:app` -- that is what the Procfile and Render start
command run, and the only stack that serves Telegram.

- `main.py` - local entry point; serves `app.main:app` on `$PORT`.
- `app/main.py` - the Flask app and the Telegram webhook handler.
- `app/agent/` - `orchestrator.py` (the deterministic commands) and `prompt.py` (Hermes'
  system prompt).
- `app/services/` - `models.py` (the text model chain), `vision.py` (the image chain),
  `memory.py` (stored facts).
- `app/tools/` - `web.py` (link fetching, SSRF-guarded), `leads.py`, `approvals.py`,
  `email_drafts.py`.
- `app/db/session.py` - SQLite by default, Postgres when `DATABASE_URL` is set.
- `telegram_client.py` - Telegram Bot API helper and the 4,096-character splitter.

`app.py`, `routes/`, `services/`, `utils/` and `openrouter_client.py` are an earlier
scaffold that builds a *separate* Flask app and is not what runs in production. Editing
them has no effect on the bot -- note that `services/` and `app/services/` are different
packages. They are dead weight and the next thing worth deleting.

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then fill it in; .env is gitignored, .env.example is not
python3 main.py
```

`load_dotenv()` reads `.env` and nothing else, so values left in `.env.example` are never
loaded.

Tests run on SQLite regardless of what is in your `.env` -- `tests/conftest.py` clears
`DATABASE_URL` so a real connection string cannot redirect the suite at production.
`pytest` lives in `requirements-dev.txt`, which Render does not install:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

There is no CI. The suite is the only gate before a deploy, so run it yourself.

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

Hermes is a general-purpose assistant and second brain for the team that runs it: it
reasons over whatever is in the message, reads images and explicitly linked pages, recalls
saved facts, and drafts, reviews, analyses and writes code. It replies in whichever
language the user wrote in (Bengali in -> Bengali out, English in -> English out). The live
system prompt is `app/agent/prompt.py`.

**Llama 3.1 70B always answers first.** `PRIMARY_MODEL` in `app/services/models.py` is
pinned at the head of the chain and no environment variable can displace it, so the paid
model always gets the first attempt and a stale dashboard value cannot quietly demote it
behind a free one. It is paid, so **it may incur charges on every message** -- that is the
deliberate trade for the best model answering first.

Chain, tried in order:

1. `meta-llama/llama-3.1-70b-instruct` - primary, always first; paid, may incur charges
2. `nvidia/nemotron-3-ultra-550b-a55b:free`
3. `nvidia/nemotron-3-super-120b-a12b:free`
4. `google/gemma-4-31b-it:free`

`app/services/models.py` walks the chain, skipping any model that returns 402/403/408/429/5xx
or an empty body. If every model fails due to quota or rate limits the user is told to retry
shortly; any other outage falls back to the deterministic orchestrator reply.
The system prompt reads this same chain at request time, so its model and cost instructions
stay accurate when these environment variables change.

Configuration:

- `OPENROUTER_MODELS` - comma-separated **fallback** list, replacing the defaults. The
  primary is prepended regardless and deduplicated out of this list, so it cannot be
  dropped or reordered. A value that parses to nothing keeps the default fallbacks rather
  than leaving the primary with none. Include paid models here only when you intend to
  allow their charges.
- `OPENROUTER_MODEL` - adds one free model as the **first fallback**, after the primary.
  It used to set the primary; the primary is no longer something the environment decides.
  **Ignored unless it is a `:free` model**, so an unreviewed paid model cannot join the
  chain by accident.
- `OPENROUTER_TIMEOUT` - per-attempt timeout in seconds (default 25).
- `OPENROUTER_BUDGET` - ceiling in seconds for the *whole* chain (default 45). The
  chain stops early rather than spending `OPENROUTER_TIMEOUT` on every model: four
  attempts at 25s outlast both the gunicorn worker timeout and Telegram's wait for
  the webhook, and a worker killed mid-request sends no reply at all. Keep it
  comfortably below the `--timeout` in the start command.

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
connection. Pointing `DATABASE_URL` at a database that also holds another product
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
`nvidia/nemotron-3.5-super-vl:free`, then gemma, then `openrouter/free`), with the same fallback
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

## How a Telegram update is handled

Telegram only waits so long for the webhook to answer, and it redelivers the update when
it does not. Running the model chain inside the request therefore produced duplicate
replies at best, and at worst none at all: gunicorn's default worker timeout is 30s, so a
worker walking a four-model chain was killed before it ever called `sendMessage`.

So the request does the cheap part only -- check the secret, parse the update, pull out the
text and any photo `file_id` -- and returns `200 {"status": "accepted"}` straight away.
Everything slow (photo download, page fetches, commands, the model chain, sending the
reply) runs on a background worker. Nothing is waiting on that half, so it logs its own
failures and always sends *something*: the command result, the model's answer, the
rate-limit notice, or a plain error.

Two time limits keep a reply from being cut off:

- `OPENROUTER_BUDGET` (45s) caps the whole model chain, and `FETCH_BUDGET` (20s, in
  `app/tools/web.py`) caps link fetching, so neither can starve the other.
- `--graceful-timeout 60` in the start command must outlast those, or a deploy kills
  replies that are still in flight.

Concurrency:

- `WEBHOOK_WORKERS` (4) - updates processed at once. The pool is FIFO, so a burst of slow
  model calls does delay whatever is queued behind it.
- `WEBHOOK_MAX_PENDING` (32) - queue depth. Past it the sender is told to retry rather than
  having the backlog grow unbounded on a small instance.

An update is acknowledged before it is processed, so a worker that dies mid-reply loses
that update instead of having Telegram redeliver it. That is the deliberate trade for not
being redelivered on every slow request.

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
