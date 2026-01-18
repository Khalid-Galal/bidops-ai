# 🚀 Fly.io Deployment Guide - BidOps AI

Deploy BidOps AI to Fly.io **100% FREE** (No credit card required initially).

---

## 📋 Step 1: Install Fly.io CLI

### Windows (PowerShell as Administrator):
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### Alternative (Using winget):
```bash
winget install flyctl
```

After installation, **close and reopen your terminal**.

Verify installation:
```bash
flyctl version
```

---

## 🔐 Step 2: Sign Up & Login

```bash
# Sign up (opens browser)
flyctl auth signup

# Or login if you have an account
flyctl auth login
```

**Note**: You may need to verify your email. Credit card **may not be required** for the free tier.

---

## 🗄️ Step 3: Create PostgreSQL Database

```bash
# Navigate to project
cd D:\Work\intercom\intercom_projects\Hassan\bidops-ai

# Create Postgres cluster (Free tier)
flyctl postgres create --name bidops-postgres --region fra --vm-size shared-cpu-1x --volume-size 1
```

**Choose these options when prompted:**
- Region: `fra` (Frankfurt) or closest to you
- Configuration: `Development - Single node, 1x shared CPU, 256MB RAM, 1GB disk`

**Save the output!** You'll get:
- Database name
- Username
- Password
- Connection string

---

## 📦 Step 4: Create Redis Instance

```bash
# Create Redis (Free tier)
flyctl redis create --name bidops-redis --region fra --no-replicas
```

**Choose:**
- Region: Same as PostgreSQL (`fra`)
- Plan: `Free` (256MB)

**Save the Redis URL!**

---

## 🚀 Step 5: Deploy Backend API

```bash
# Navigate to backend directory
cd backend

# Initialize Fly app (don't deploy yet)
flyctl launch --no-deploy

# When asked:
# - App name: bidops-api (or auto-generated)
# - Region: fra (same as database)
# - PostgreSQL: NO (we already created it)
# - Redis: NO (we already created it)
```

### Attach Database & Redis:
```bash
# Attach PostgreSQL
flyctl postgres attach bidops-postgres

# This sets DATABASE_URL automatically!
```

### Set Environment Variables:
```bash
# Set secret key (generates random string)
flyctl secrets set SECRET_KEY=$(openssl rand -hex 32)

# Set Redis URL (from Step 4)
flyctl secrets set REDIS_URL="redis://[YOUR-REDIS-URL-FROM-STEP-4]"

# Optional: Add Google API key
flyctl secrets set GOOGLE_API_KEY="your-api-key-here"
```

### Deploy Backend:
```bash
flyctl deploy
```

Wait ~5 minutes. You'll get a URL like: `https://bidops-api.fly.dev`

**Test it:**
```bash
curl https://bidops-api.fly.dev/api/v1/health
```

---

## 🌐 Step 6: Deploy Frontend

```bash
# Navigate to frontend directory
cd ../frontend

# Create Dockerfile build arg file
echo "ARG VITE_API_URL=https://bidops-api.fly.dev/api/v1" > .env.production

# Initialize Fly app
flyctl launch --no-deploy

# When asked:
# - App name: bidops-frontend
# - Region: fra (same as backend)
```

### Build with correct API URL:
Edit `frontend/Dockerfile` to use production env, or set build arg:

```bash
# Deploy with API URL
flyctl deploy --build-arg VITE_API_URL=https://bidops-api.fly.dev/api/v1
```

Wait ~3 minutes. You'll get: `https://bidops-frontend.fly.dev`

---

## 🧪 Step 7: Test Your Deployment

1. Visit: `https://bidops-frontend.fly.dev`
2. Login with:
   - **Email**: admin@example.com
   - **Password**: Admin123

3. If login page loads but can't connect:
   - Check CORS in backend/app/main.py (already set to allow all)
   - Verify API URL in browser console
   - Check backend logs: `flyctl logs -a bidops-api`

---

## 📊 Useful Commands

```bash
# View backend logs
flyctl logs -a bidops-api

# View frontend logs
flyctl logs -a bidops-frontend

# Check app status
flyctl status -a bidops-api

# SSH into backend
flyctl ssh console -a bidops-api

# Scale down to save resources (optional)
flyctl scale count 0 -a bidops-api  # Stop when not needed
flyctl scale count 1 -a bidops-api  # Start again
```

---

## 🔧 Troubleshooting

### Database Connection Error:
```bash
# Check database is attached
flyctl postgres list

# Check connection string
flyctl ssh console -a bidops-api
echo $DATABASE_URL
```

### Frontend can't reach backend:
1. Check API URL in frontend build:
   ```bash
   flyctl ssh console -a bidops-frontend
   cat /usr/share/nginx/html/assets/index-*.js | grep -o 'https://[^"]*api'
   ```

2. Update if needed:
   ```bash
   cd frontend
   flyctl deploy --build-arg VITE_API_URL=https://bidops-api.fly.dev/api/v1
   ```

### App not starting:
```bash
# View detailed logs
flyctl logs -a bidops-api

# Check machine status
flyctl machine list -a bidops-api
```

---

## 💰 Cost Breakdown

**Fly.io Free Tier:**
- ✅ 3 VMs (shared-cpu-1x, 256MB RAM) - **FREE**
- ✅ PostgreSQL (256MB, 1GB disk) - **FREE**
- ✅ Redis (256MB) - **FREE**
- ✅ 160GB outbound transfer - **FREE**

**Your Usage:**
- Backend: 1 VM
- Frontend: 1 VM
- Total: **$0/month** within free tier! 🎉

**Auto-stop**: Apps automatically stop when idle and start on request (cold start ~2 seconds).

---

## 🎁 Keep Apps Running (Prevent Cold Starts)

Use **UptimeRobot** (free):
1. Go to https://uptimerobot.com
2. Create monitor for: `https://bidops-api.fly.dev/api/v1/health`
3. Interval: 5 minutes
4. Keeps your app warm! ⚡

---

## 📧 Share with Customer

```
🎉 BidOps AI is Live!

🔗 https://bidops-frontend.fly.dev

Login:
📧 admin@example.com
🔑 Admin123

⚡ Hosted on Fly.io - Fast & Reliable!

Features:
✅ Create projects
✅ Manage suppliers
✅ Upload documents
✅ Create packages

Your feedback is valuable! 🚀
```

---

## 🔄 Update Deployment

```bash
# Make changes to code, then:
git add .
git commit -m "Update feature"
git push

# Deploy backend
cd backend
flyctl deploy

# Deploy frontend
cd ../frontend
flyctl deploy --build-arg VITE_API_URL=https://bidops-api.fly.dev/api/v1
```

---

## 🆘 Need Help?

- Fly.io Docs: https://fly.io/docs
- Community: https://community.fly.io
- Status: https://status.flyctl.com

---

## ✨ Next Steps After Deployment

1. **Custom Domain** (optional):
   ```bash
   flyctl certs add yourdomain.com -a bidops-frontend
   ```

2. **Monitoring**:
   ```bash
   flyctl dashboard -a bidops-api
   ```

3. **Backups** (PostgreSQL):
   ```bash
   flyctl postgres backup list -a bidops-postgres
   ```

Good luck! 🚀
