# Vercel Git deployment

GamePulse is deployed as one Vercel Git project. The root Next.js service serves
the public UI at `/`; the FastAPI service serves `/api` using Neon/Postgres via
`DATABASE_URL`. Use Git-connected builds and the Vercel **Services** framework
preset; do not use one-off file-upload deployments.

## Project settings

- Connect the repository through Vercel Git integration.
- Set the project root to the repository root (`.`).
- Set the production branch to `main` (or the release branch approved by the
  curator).
- Set Framework Preset to **Services**.
- Keep the service definitions in the root `vercel.json`.

The `web` service uses entrypoint `.` and route prefix `/`. The `api` service
uses `api/service.py` and route prefix `/api`. Services may strip `/api` before
calling the FastAPI app; the adapter preserves the existing local `/api/*`
routes and accepts both `/health` and `/api/health` at the service boundary.

## Environment variables

Configure these in Vercel Project Settings, never in Git:

- Required: `DATABASE_URL`, `CRON_SECRET`
- Optional: `MISTRAL_API_KEY`

Twitch and StreamsCharts credentials are not required for the production web
runtime. Visitor Steam Web API keys remain request-scoped and must not be added
as Vercel environment variables.
