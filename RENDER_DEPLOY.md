# Render deployment checklist (backend)

## Create Web Service
- Runtime: **Python 3.12**
- Build command: `pip install -r requirements.txt`
- Start command: `bash scripts/start.sh`
- Health check path: `/health`
- Plan: Free works for demos (sleeps after ~15 min idle)

## Required env vars
| Key | Notes |
|---|---|
| `DATABASE_URL` | Supabase URI (`postgresql://...` is auto-normalized to `postgresql+psycopg://` + `sslmode=require`) |
| `SECRET_KEY` | JWT/app secret (long random) |
| `CRON_SECRET` | Same value as cron-job.org header `X-Cron-Secret` |
| `RSA_PRIVATE_KEY` | PEM; paste with `\n` escaped or real newlines |
| `RSA_PUBLIC_KEY` | PEM |
| `FRONTEND_URL` | Netlify URL, e.g. `https://your-app.netlify.app` |
| `PUBLIC_BASE_URL` | Your Render URL, e.g. `https://social-ai-backend.onrender.com` |
| `REDIS_URL` | Upstash **`rediss://...`** (TLS required) |
| `META_*` | App id/secret + `META_REDIRECT_URI=https://<render>/api/v1/instagram/callback` |
| `GOOGLE_*` | Client id/secret + `GOOGLE_REDIRECT_URI=https://<render>/api/v1/auth/google/callback/` |
| `CLOUDINARY_*` | Cloud name, key, secret |
| `BREVO_API_KEY` | From Brevo → SMTP & API → API keys |
| `EMAIL_FROM` | Verified sender, e.g. `AI Platform <noreply@yourdomain.com>` |
| `COHERE_API_KEY` | RAG embeddings |
| LLM keys | Per `LLM_PROVIDER` (`OPENAI_API_KEY`, `GROQ_API_KEY`, etc.) |

## External consoles (must match env)
1. **Google Cloud OAuth** — authorized redirect URI = `GOOGLE_REDIRECT_URI`
2. **Meta / Facebook** — Valid OAuth Redirect URI = `META_REDIRECT_URI`
3. **Netlify FE** — API base URL = `PUBLIC_BASE_URL`
4. **cron-job.org**
   - `POST https://<render>/api/v1/internal/generate-content` every 15 min
   - `POST https://<render>/api/v1/internal/publish-content` every 2 min
   - Header: `X-Cron-Secret: <CRON_SECRET>`
   - Enable retries (cold start on free tier)

## Important limitations (Free Render)
- Service **sleeps** after inactivity → first request / cron may take 30–60s
- **No persistent disk** → Chroma under `storage/chroma` is wiped on redeploy/restart (re-upload knowledge or move vectors later)
- Use **1 uvicorn worker** (already in `scripts/start.sh`) so BackgroundTasks keep working
- Build can be slow/heavy (`chromadb` / `onnxruntime`); if OOM, upgrade plan or slim deps

## Smoke test after deploy
```bash
curl https://YOUR.onrender.com/health

curl -X POST https://YOUR.onrender.com/api/v1/internal/generate-content \
  -H "X-Cron-Secret: YOUR_CRON_SECRET"
```
