# Using the SDK, step by step

The SDK sends errors, feedback and tickets from your app to a PQ product, and reports crashes by itself once hooked in. The same steps, with your own address filled in, are on each product's **API** page (`/products/<id>/api/`, section "Use the SDK").

The package is called **`pq-befu`** on both PyPI (Python, imported as `pq_sdk`) and npm (Node). It is *not* `pq-sdk`.

## 1. Make an API key

Open the product, go to **API keys**, create one. It is shown once; copy it. Keys belong to one product, can expire, and a wrong or revoked key answers `403`.

## 2. Keep the key and address in the environment

```bash
export PQ_API_KEY="your key"
export PQ_BASE_URL="https://crm.beforth.in"
```

Never commit the key or ship it in browser code.

## 3. Install and hook in, by framework

### Python (plain)
```bash
pip install pq-befu
```
```python
import os
from pq_sdk import PQClient
pq = PQClient(api_key=os.environ["PQ_API_KEY"], base_url=os.environ["PQ_BASE_URL"])

try:
    risky()
except Exception as exc:
    pq.capture_exception(exc)
    raise
```
Or `with capture_exceptions(pq): ...` / `@auto_capture(pq)` from `pq_sdk.hooks`.

### Django
`pip install "pq-befu[django]"`
```python
MIDDLEWARE = [..., "pq_sdk.integrations.django.DjangoMiddleware"]
PQ_SDK = {"api_key": os.environ["PQ_API_KEY"], "base_url": os.environ["PQ_BASE_URL"], "environment": "production"}
```

### Flask
`pip install "pq-befu[flask]"`
```python
from pq_sdk.integrations.flask import FlaskIntegration
FlaskIntegration(app, pq)
```

### FastAPI
`pip install "pq-befu[fastapi]"`
```python
from pq_sdk.integrations.fastapi import FastAPIMiddleware
app.add_middleware(FastAPIMiddleware, client=pq)
```

### Node: Express, Fastify, Koa, NestJS
`npm install pq-befu` (NestJS also `@nestjs/common rxjs`)
```js
const { PQClient } = require("pq-befu");
const pq = new PQClient({ apiKey: process.env.PQ_API_KEY, baseUrl: process.env.PQ_BASE_URL });
```
- **Express:** `const { middleware, errorHandler } = pqExpress({ client: pq })` from `pq-befu/integrations/express`; `app.use(middleware)` before routes, `app.use(errorHandler)` after.
- **Fastify:** `await app.register(pqFastify, { client: pq })` from `pq-befu/integrations/fastify`.
- **Koa:** `app.use(pqKoa(pq))` from `pq-befu/integrations/koa`, before routes.
- **NestJS:** `PqSdkModule.forRoot({ apiKey, baseUrl, environment })` from `pq-befu/integrations/nestjs` in `AppModule.imports`.

### Electron
Create the client and call `pqElectronMain(pq)` (from `pq-befu/integrations/electron`) in the **main** process only; use `preload: require.resolve("pq-befu/preload")` and call `window.pq.captureException(err)` in the renderer. The key never reaches the renderer.

### Browser / worker
`import { PQBrowserClient } from "pq-befu/browser"`. Only with a key you accept being public; prefer reporting from your server.

## 4. Send the other things

```python
pq.send_feedback(rating=5, comment="Great product!")
pq.create_ticket(title="Invoice PDF is blank", description="From billing", ticket_type="bug")
```
Node: `await pq.sendFeedback({ rating: 5 })`, `await pq.createTicket({ title, ticketType: "bug" })`, and `await pq.flush()` before the process exits.

## 5. Check it works

Trigger a test error, then open **Errors** on the product. It appears within a second, grouped with matching errors. Nothing? Check the key is active and the base URL is reachable from your server.
