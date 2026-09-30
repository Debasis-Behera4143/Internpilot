# 🚀 Deploying InternPilot to Render

This project is configured for seamless deployment on [Render](https://render.com) (both Free and Paid tiers).

---

## ⚡ Option 1: Automatic Blueprint Deployment (Recommended)

Render can automatically detect and configure everything using the included [`render.yaml`](file:///c:/Users/debas/Desktop/MONIR%20PRO/internpilot/render.yaml) blueprint file.

1. **Push your code to GitHub / GitLab:**
   ```bash
   git add .
   git commit -m "Configure Render deployment"
   git push origin main
   ```
2. **Log into Render:**
   - Go to [dashboard.render.com](https://dashboard.render.com).
3. **Deploy with Blueprint:**
   - Click **New +** > **Blueprint**.
   - Connect your GitHub repository.
   - Render reads [`render.yaml`](file:///c:/Users/debas/Desktop/MONIR%20PRO/internpilot/render.yaml) automatically and sets up the Web Service.
   - Click **Apply**.

---

## 🛠️ Option 2: Manual Web Service Setup

If you prefer to configure the service manually in the Render dashboard:

1. In Render Dashboard, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure the following fields:

| Field | Value |
| :--- | :--- |
| **Name** | `internpilot` (or your choice) |
| **Region** | Oregon (US West) or closest to you |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start Command** | `gunicorn -w 1 -k uvicorn.workers.UvicornWorker backend.api.app:app --bind 0.0.0.0:$PORT --timeout 120` |
| **Plan** | Free (or Starter) |

4. Scroll down to **Advanced** > **Environment Variables** and add:

| Key | Recommended Value | Notes |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Ensures consistent modern Python build |
| `APP_ENV` | `production` | Production mode |
| `DEBUG` | `False` | Disables debug reloading |
| `HOST` | `0.0.0.0` | Binds to all network interfaces |
| `JWT_SECRET_KEY` | *(Click "Generate" or enter 32+ characters)* | JWT token signing key |
| `ADMIN_EMAIL` | `admin@example.com` | Default admin login |
| `ADMIN_PASSWORD` | *(Set your secure admin password)* | Default admin password |
| `AUTO_INGEST_ON_STARTUP` | `True` | Runs opportunity aggregator on start |
| `ENABLE_SAMPLE_FALLBACK` | `True` | Ensures immediate job availability |

5. Under **Health Check Path**, enter:
   `/api/health`

6. Click **Create Web Service**.

---

## 💡 Important Tips for Render Free Tier

1. **Worker Threads**: Render's free tier has 512MB RAM. Using `-w 1` (`gunicorn -w 1 -k uvicorn.workers.UvicornWorker ...`) keeps memory usage well under the limit while handling async FastAPI requests effortlessly.
2. **Free Tier Cold Starts**: On the free tier, Render puts web services to sleep after 15 minutes of inactivity. When you visit your URL after dormancy, it may take 30–50 seconds to spin back up.
3. **Persistent SQLite / Disk (Optional)**: On the free tier, files written to `./data` persist between requests while running, but reset on redeployments. If you want permanent database storage across redeploys, either:
   - Add a persistent Render Disk mounted at `/data` (available on Starter plan), or
   - Point `DATABASE_URL` to Render's free PostgreSQL instance.
