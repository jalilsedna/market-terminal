# TradingView integration (ROADMAP G3)

Two integration layers, plus one honest limitation.

## Reality check — what's possible

- ❌ **Auto-importing your saved Pine scripts / strategies is NOT possible.**
  TradingView exposes **no API** to read the Pine code saved in your account.
  Nothing can log in and pull your strategies programmatically.
- ✅ **Live signals via webhooks** — Pine `alert()` calls and strategy entries/
  exits can POST a webhook. This is the supported way to get *signals* out.
- ✅ **Pine → Python port (manual)** — paste a strategy's Pine to the maintainer/
  Claude and re-implement its *logic* as a native signal in the terminal.
- ✅ **Embedded charts** — the **Chart tab** already embeds TradingView's Advanced
  Chart; a paid TradingView login in your browser unlocks your indicators there.

## 1. Webhook signals → terminal → Alice (shipped)

Flow: TradingView alert → `POST /webhook/tradingview` → stored in SQLite →
surfaced in the **Chart tab** ("TradingView Signals" panel) and over MCP
(`tradingview_signals`), so **Alice can read your TV signals** (research only —
the terminal never auto-executes).

### Setup
1. **Set a secret** (TradingView can't send auth headers, so the webhook is
   secret-gated instead of Bearer-gated):
   ```
   TV_WEBHOOK_SECRET=<openssl rand -hex 16>
   ```
   Add it in Railway → Variables (or `.env` locally). Unset → the webhook is
   **disabled** (returns 404).

2. **In TradingView**, create an alert → **Notifications → Webhook URL**:
   ```
   https://<your-app>.up.railway.app/webhook/tradingview?token=<TV_WEBHOOK_SECRET>
   ```
   (TradingView Pro+ is required for webhook alerts.)

3. **Alert message** — send JSON so the fields are parsed (ticker/action/price/
   text). Example for a strategy:
   ```json
   {"ticker":"{{ticker}}","action":"{{strategy.order.action}}","price":"{{close}}","text":"{{strategy.order.comment}}"}
   ```
   Or for a study `alert()`:
   ```json
   {"ticker":"{{ticker}}","price":"{{close}}","text":"RSI crossed 30"}
   ```
   A plain-text message also works (stored as `text`); put the token in the URL
   in that case. You can also pass the secret in the body as `"token":"..."`.

### Verify
- After an alert fires, open the **Chart tab** → the "TradingView Signals" panel
  lists it; or `GET /tradingview/signals`; or ask Alice to call `tradingview_signals`.
- Quick manual test:
  ```bash
  curl -X POST "https://<app>.up.railway.app/webhook/tradingview?token=$TV_WEBHOOK_SECRET" \
    -H "Content-Type: application/json" \
    -d '{"ticker":"AAPL","action":"buy","price":"191.2","text":"manual test"}'
  ```
  Expect `{"ok":true,...}`. A wrong/missing token → 403; no secret configured → 404.

## 2. Pine → Python port (manual, on request)

For a strategy you want the terminal to compute *natively* on its own data
(rather than only receiving signals), paste the Pine source and we re-implement
the logic as a Python signal module (a future `signals/`), surfaced as a panel +
MCP tool. There's no auto-sync — you port the ones that matter.

## Security notes

- The webhook is the **only** unauthenticated route besides `/health` — it's
  protected by the shared secret (constant-time compared) and only ever
  **stores** data; it cannot place orders or read other endpoints.
- Rotate `TV_WEBHOOK_SECRET` like any other secret; update the TradingView alert
  URL to match.
