# Render Deployment Guide

## Quick Deploy to Render

### Option 1: Deploy via Dashboard (Recommended)

1. **Create Account**
   - Go to https://render.com
   - Sign up with GitHub

2. **Create PostgreSQL Database**
   - Click "New +"
   - Select "PostgreSQL"
   - Name: `kasparro-db`
   - Database: `etl_db`
   - User: `etl_user`
   - Region: Oregon (Free)
   - Plan: Free
   - Click "Create Database"
   - **Copy the Internal Database URL** (starts with `postgresql://`)

3. **Create Web Service**
   - Click "New +"
   - Select "Web Service"
   - Connect your GitHub repository: `Pseudo-CS/kasparro-backend-saandeep-sijo`
   - Name: `kasparro-etl-api`
   - Region: Oregon (Free)
   - Branch: `main`
   - Runtime: Docker
   - Plan: Free
   - Click "Create Web Service"

4. **Configure Environment Variables**
   
   Go to Environment tab and add:
   
   ```
   DATABASE_URL=<paste Internal Database URL from step 2>
   API_KEY_SOURCE_1=<your-coinpaprika-api-key>
   API_KEY_SOURCE_2=<your-coingecko-api-key>
   API_URL_SOURCE_1=https://api.coinpaprika.com/v1/tickers
   API_URL_SOURCE_2=https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1&sparkline=false
   RSS_FEED_URL=https://cointelegraph.com/rss
   CSV_SOURCE_PATH=/app/data/sample_data.csv
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   ETL_RATE_LIMIT_CALLS=100
   ETL_RATE_LIMIT_PERIOD=60
   ETL_SCHEDULE_ENABLED=true
   ETL_SCHEDULE_INTERVAL=21600
   ```

5. **Deploy**
   - Click "Manual Deploy" → "Deploy latest commit"
   - Wait for build to complete (~5 minutes)
   - Your API will be available at: `https://kasparro-etl-api.onrender.com`

### Option 2: Deploy with Blueprint (render.yaml)

1. **Push render.yaml to repository**
   ```bash
   git add render.yaml
   git commit -m "Add Render deployment config"
   git push origin main
   ```

2. **Create Blueprint on Render**
   - Go to https://dashboard.render.com/blueprints
   - Click "New Blueprint Instance"
   - Connect repository: `Pseudo-CS/kasparro-backend-saandeep-sijo`
   - Render will auto-detect `render.yaml`
   - Set environment variables that are marked as `sync: false`:
     - `API_KEY_SOURCE_1`
     - `API_KEY_SOURCE_2`
   - Click "Apply"

3. **Wait for Deployment**
   - Database will be created first
   - Then web service will deploy
   - Check logs for any errors

---

## Verify Deployment

### 1. Check Health
```bash
curl https://kasparro-etl-api.onrender.com/health
```

**Expected:**
```json
{
  "status": "healthy",
  "database_connected": true,
  "etl_status": "running",
  "timestamp": "2025-12-25T13:00:00.000000"
}
```

### 2. Test API Endpoints
```bash
# Get data
curl https://kasparro-etl-api.onrender.com/data?limit=10

# Get stats
curl https://kasparro-etl-api.onrender.com/stats

# Get metrics
curl https://kasparro-etl-api.onrender.com/observability/metrics/json
```

### 3. Check Logs
- Go to Render Dashboard
- Click on your service
- Go to "Logs" tab
- Look for:
  - Database connection success
  - ETL scheduler started
  - No errors

---

## Troubleshooting

### Database Connection Issues

**Error:** `connection to server at "localhost" failed`

**Solution:** Ensure `DATABASE_URL` is set in environment variables:
1. Go to Render Dashboard → Your Service → Environment
2. Add/Update `DATABASE_URL` with the Internal Database URL
3. **Important:** Use the **Internal** URL, not External
4. Save and redeploy

**Get Internal Database URL:**
1. Go to your PostgreSQL database in Render
2. Under "Connections"
3. Copy "Internal Database URL"
4. Format: `postgresql://user:password@hostname/dbname`

### Build Failures

**Error:** Docker build timeout

**Solution:**
1. Check Dockerfile is in repository root
2. Ensure requirements.txt is up to date
3. Try manual deploy: "Manual Deploy" → "Clear build cache & deploy"

### ETL Not Running

**Error:** No data ingestion happening

**Solution:**
1. Check environment variables are set:
   - `API_KEY_SOURCE_1`
   - `API_URL_SOURCE_1`
   - `RSS_FEED_URL`
2. Check logs for API rate limiting
3. Verify CSV file exists: `/app/data/sample_data.csv`

### Free Tier Limitations

**Render Free Tier:**
- Services spin down after 15 minutes of inactivity
- First request after spindown takes ~1 minute (cold start)
- 750 hours/month per service
- PostgreSQL: 1GB storage, shared CPU

**Workarounds:**
1. Use external monitoring (every 14 minutes):
   - https://uptimerobot.com (free)
   - Ping: `https://your-app.onrender.com/health`
2. Upgrade to paid plan ($7/month) for always-on

---

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host/db` |
| `API_KEY_SOURCE_1` | CoinPaprika API key | `your-api-key` |
| `API_URL_SOURCE_1` | CoinPaprika API endpoint | `https://api.coinpaprika.com/v1/tickers` |
| `RSS_FEED_URL` | RSS feed URL | `https://cointelegraph.com/rss` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY_SOURCE_2` | None | CoinGecko API key (optional) |
| `API_URL_SOURCE_2` | None | CoinGecko API endpoint |
| `CSV_SOURCE_PATH` | `/app/data/sample_data.csv` | Path to CSV data |
| `ENVIRONMENT` | `production` | Environment name |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ETL_RATE_LIMIT_CALLS` | `100` | Rate limit calls per period |
| `ETL_RATE_LIMIT_PERIOD` | `60` | Rate limit period (seconds) |
| `ETL_SCHEDULE_ENABLED` | `true` | Enable scheduled ETL runs |
| `ETL_SCHEDULE_INTERVAL` | `21600` | ETL interval (6 hours) |

---

## Scheduled ETL Runs

The application has a built-in scheduler that runs ETL every 6 hours (configurable via `ETL_SCHEDULE_INTERVAL`).

**Check if scheduler is running:**
```bash
# View logs
curl https://kasparro-etl-api.onrender.com/stats | jq '.recent_runs'
```

**Manual trigger (if needed):**
Add a new endpoint or use Render Cron Jobs:
1. Go to Render Dashboard
2. Click "New +"
3. Select "Cron Job"
4. Command: `curl https://kasparro-etl-api.onrender.com/trigger-etl`
5. Schedule: `0 */6 * * *` (every 6 hours)

---

## Production Checklist

Before going live:

- [ ] Database connected and healthy
- [ ] All environment variables set
- [ ] API keys configured (for external APIs)
- [ ] Health check passing: `/health`
- [ ] Data endpoint working: `/data?limit=5`
- [ ] Stats endpoint working: `/stats`
- [ ] Metrics endpoint working: `/observability/metrics/json`
- [ ] ETL scheduler running (check logs)
- [ ] No errors in logs for past 10 minutes
- [ ] Set up monitoring (UptimeRobot, Render metrics)
- [ ] Configure alerts (email, Slack)

---

## Monitoring & Logs

### View Logs in Real-time
```bash
# Using Render CLI
render logs -f kasparro-etl-api

# Or use Dashboard → Logs tab
```

### Key Log Messages

**Healthy:**
```
INFO - Starting ETL Backend Service
INFO - Database connected successfully
INFO - ETL scheduler started
INFO - Health check: healthy
```

**Issues:**
```
ERROR - Database connection failed
ERROR - API rate limit exceeded
WARNING - Schema drift detected
```

### Metrics Dashboard

Access built-in observability:
- Prometheus: `https://your-app.onrender.com/observability/metrics`
- JSON: `https://your-app.onrender.com/observability/metrics/json`

---

## Cost Estimate

**Free Tier:**
- Web Service: Free (with spindown)
- PostgreSQL: Free (1GB)
- Total: $0/month

**Paid (Always-On):**
- Web Service: $7/month
- PostgreSQL: $7/month (better performance)
- Total: $14/month

---

## Support

**Render Documentation:**
- https://render.com/docs
- https://render.com/docs/docker
- https://render.com/docs/databases

**This Project:**
- Issues: https://github.com/Pseudo-CS/kasparro-backend-saandeep-sijo/issues
- README: https://github.com/Pseudo-CS/kasparro-backend-saandeep-sijo

---

## Alternative: Deploy with Docker Compose

If you prefer self-hosting or need more control, use the provided `docker-compose.yml`:

```bash
# On your server
git clone https://github.com/Pseudo-CS/kasparro-backend-saandeep-sijo.git
cd kasparro-backend-saandeep-sijo
cp .env.example .env
# Edit .env with your configuration
docker-compose up -d
```

See [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md) for AWS/GCP/Azure options.
