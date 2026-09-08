# Deployment

Two services, two hosts:

| Part | Host | Why |
|---|---|---|
| **Frontend** (Next.js) | **Vercel** | Native Next.js support, free, deploys on every push |
| **API** (FastAPI) | **Render** (Docker) | Needs the Tesseract binary and a real filesystem for uploads — neither of which a serverless function provides |

Deploy the **API first**, because the frontend needs its URL at build time.

---

## Why not put everything on Vercel

Worth knowing, because it is a reasonable question and the answer is specific:

- **Tesseract is a system binary.** Vercel's Python runtime installs pip packages, not
  `apt` packages. Without it the real-OCR path and the OCR arm of the evaluation cannot
  run — and that arm is the figure that actually characterises extraction.
- **The filesystem is ephemeral and read-only outside `/tmp`.** Uploaded PDFs are stored
  and re-read later by the document viewer; on a serverless function they would vanish
  between invocations.
- **SQLite needs a durable file.** Moving to Postgres is possible, but combined with the
  above it amounts to rearchitecting the backend for a demonstration that already runs.

Render's free tier gives a Docker container with `apt` and a writable disk, which is what
this application needs.

Vercel's import screen will nonetheless *offer* to deploy `backend/` as a FastAPI
serverless app, because it recognises the framework. Decline it — for the three reasons
above it would build and then fail at runtime.

---

## 1 · The API on Render

### Using the blueprint (recommended)

`render.yaml` at the repository root already describes the service.

1. <https://dashboard.render.com/blueprints> → **New Blueprint Instance**
2. Connect the GitHub repository → **Apply**
3. Wait for the first build (5–8 minutes; it installs Tesseract and the Python
   dependencies)

Render gives you a URL like `https://landtrust-connect-api.onrender.com`. Confirm it:

```bash
curl https://landtrust-connect-api.onrender.com/api/health
```

You should get `{"status":"ok",...}` with `extraction_backends` showing both `DEMO` and
`OCR` as available.

### Manually instead

**New → Web Service** → connect the repo → set:

| Setting | Value |
|---|---|
| Runtime | Docker |
| Dockerfile path | `./backend/Dockerfile` |
| Docker context | `.` (repository root — the build needs `backend/` and the data layout) |
| Health check path | `/api/health` |
| Instance type | Free |

Environment variables: `EXTRACTION_MODE=DEMO`, `CORS_ORIGINS=*` (tightened in step 3).

### What is baked into the image

The Dockerfile renders the synthetic corpus, runs the evaluation harness and seeds the
database **at build time**, not at boot. Three consequences worth knowing:

- A cold start finds a populated database, so it boots in seconds rather than re-seeding.
- `/research` shows real computed figures on the deployed instance. Without this it shows
  its empty state, because `data/metrics.json` is generated and therefore gitignored.
- The evaluation runs against a **throwaway** database that is deleted afterwards; the
  database the demo serves is seeded fresh. The harness asks the assistant questions and
  recomputes risk, so letting it touch the served database would mean a reviewer sees a
  file the evaluation had already poked at.

The **OCR arm is behind a flag**, `EVAL_OCR`, which `render.yaml` sets to `1`. Render
exposes a service's environment variables to the Docker build as build arguments, so it
reaches the `ARG` of the same name in the Dockerfile; setting it in the dashboard works
too, but the blueprint is the durable place for it.

It is a flag rather than unconditional because the cost varies enormously with the
machine: **43.6 s** on Render's free build machine, but tens of minutes on a throttled
VM, where it would make every rebuild painful. Leave it off there.

With it off, `/research` states plainly that the arm was not requested and how to run it
— it does not claim Tesseract was missing, which would be false on this image. CI runs
the OCR arm on every push regardless, and uploads `metrics.json` as an artefact, so the
figure is verified continuously either way.

### What the free tier means here

- **No persistent disk.** The container's copy of `/app/data` is reset on each restart, so
  anything you uploaded while exploring is cleared when the service sleeps and the demo
  always begins from the same known state.
- **Sleeps after 15 minutes idle**, and the next request takes ~50 seconds while the
  container starts. **Open `/api/health` a few minutes before a live demonstration** so
  the first click in the UI is instant. The frontend shows a specific "the API may be
  waking from sleep" message if it times out, rather than a generic error.

To remove both limitations, upgrade to a paid instance and add a disk mounted at
`/app/data`. Nothing in the code changes.

---

## 2 · The frontend on Vercel

1. <https://vercel.com/new> → import the GitHub repository
2. **Root Directory → Edit → `frontend`.** This is the step that matters. Vercel's
   monorepo detection offers to deploy `backend/` as a second serverless app; scoping
   the project to `frontend/` drops that offer and lets Vercel's zero-config Next.js
   detection do the rest. `frontend/vercel.json` then supplies only the region.
3. Before the first deploy, add one environment variable:

   | Name | Value | Environments |
   |---|---|---|
   | `NEXT_PUBLIC_API_URL` | your Render URL, no trailing slash | Production, Preview, Development |

4. **Deploy**

> `NEXT_PUBLIC_*` variables are inlined at build time. If you add or change this
> variable after deploying, you must **redeploy** — restarting is not enough. This is the
> single most common reason a deployed frontend shows "could not reach the API".

---

## 3 · Lock down CORS

Once the Vercel URL exists, go back to Render → **Environment** → set:

```
CORS_ORIGINS=https://landtrust-connect.vercel.app
```

Add any custom domain as a comma-separated second value. Render redeploys automatically.

Leaving `*` works and exposes nothing sensitive — the corpus is synthetic and the API is
read-mostly — but narrowing it is good practice and takes ten seconds.

---

## 4 · Verify

```bash
API=https://landtrust-connect-api.onrender.com

curl -s $API/api/health | head -c 120
curl -s $API/api/properties | python -m json.tool | head -20
```

Then in the browser, on the deployed frontend:

1. `/dashboard` — six properties, 31 documents, charts populated
2. `/properties/LTC-PR-0002?tab=claims` — the Claim–Evidence Matrix; click the Property
   Area row and confirm the evidence drawer opens
3. `/properties/LTC-PR-0002?tab=risk` — 73.8, HIGH, HOLD; click *Initiate payment* and
   confirm it is refused
4. `/research` — the computed metrics, including the OCR arm at 98.36 %

If the dashboard is empty but `/api/health` responds, `NEXT_PUBLIC_API_URL` is missing or
was set after the build — redeploy the frontend.

---

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request:

- installs Tesseract, generates the synthetic corpus, seeds the database through the real
  pipeline
- runs all 93 tests
- runs the Review-2 acceptance sequence with `-s`, so a failure shows the exact trace
- runs the evaluation harness including the OCR arm and uploads `metrics.json` as an
  artefact

The badge is worth putting in a review slide: it demonstrates that the acceptance sequence
is verified on every commit, not only on your laptop.

---

## Local development after cloning

```bash
git clone https://github.com/seelammiddavandla2023-boop/landtrust-connect.git
cd landtrust-connect

npm install          # the one-command runner
npm run setup        # backend requirements + frontend packages
npm run seed         # generate the corpus and seed the database
npm run dev          # API on :8000, UI on :3000
```

No environment file is needed locally: with `NEXT_PUBLIC_API_URL` unset, `next.config.mjs`
proxies `/api` to the local backend and CORS never applies.

Optional, for the OCR path:

- **Windows** — <https://github.com/UB-Mannheim/tesseract/wiki>, then add the install
  directory to `PATH`
- **macOS** — `brew install tesseract`
- **Linux** — `sudo apt install tesseract-ocr`

Without it the prototype runs in text-layer mode and `npm run eval:ocr` reports the OCR arm
as unavailable, with a message saying so. Nothing else changes.

---

## Alternatives to Render

The API is a plain Docker container listening on `$PORT`, so it runs unmodified on:

| Host | Notes |
|---|---|
| **Railway** | `railway up` from the repo root. Paid after the trial credit; no sleep. |
| **Fly.io** | `fly launch --dockerfile backend/Dockerfile`. Add a volume at `/app/data` for persistence. |
| **Google Cloud Run** | Generous free tier, scales to zero, similar cold start. |
| **A college VM** | `docker compose up --build` runs both services; useful if the review room has no internet. |

`docker-compose.yml` at the repository root brings up both services locally with one
command, which is the safest fallback if the hosted demo is unreachable on the day.

---

## What is safe to make public

The repository contains no secrets and no real data. Every person, survey number, document
number and institution in the corpus is invented, and the documents are generated by
`backend/app/seed/documents.py` rather than collected. There are no API keys anywhere: the
prototype is designed to run without them.

`.gitignore` excludes the SQLite database, uploaded files and `data/metrics.json`, all of
which are regenerated by `npm run seed` and `npm run eval`.
