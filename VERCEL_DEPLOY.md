# 🚀 Free Deployment Guide - SQLite Version

## Important Note About Free Hosting

After researching truly FREE platforms (no credit card), here are your best options:

### ⭐ Recommended: Railway.app
- **$5 free credit per month** (no CC if verified with GitHub)
- Supports Docker + SQLite
- Perfect for 2-week demos
- **STATUS**: FREE for demos

### 🥈 Alternative: Koyeb.com
- Truly free tier (no CC)
- Supports Docker
- 512MB RAM free
- **STATUS**: 100% FREE

---

## 🚀 Deploy to Railway.app (Recommended)

### Step 1: Sign Up
1. Go to https://railway.app
2. Click "Login" → Sign in with GitHub
3. Verify with GitHub (no credit card needed!)

### Step 2: Deploy from GitHub

```bash
# Install Railway CLI (optional)
npm install -g @railway/cli

# Or use web dashboard:
# 1. Click "New Project"
# 2. Select "Deploy from GitHub repo"
# 3. Choose: Khalid-Galal/bidops-ai
# 4. Railway auto-detects Docker!
```

### Step 3: Configure

Railway will detect `docker-compose.yml`. Configure:

**Environment Variables:**
```
DATABASE_URL=sqlite+aiosqlite:////app/storage/database/bidops.db
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=[Railway generates this]
```

**Settings:**
- Root Directory: `/`
- Port: 8000

### Step 4: Deploy!

Click "Deploy" - Done in 5 minutes! 🎉

You'll get:
- Backend: `https://bidops-api.railway.app`
- Frontend served from backend

---

## 🥈 Alternative: Deploy to Koyeb.com (100% Free)

### Step 1: Sign Up
1. Go to https://koyeb.com
2. Sign up with GitHub (FREE, no CC!)

### Step 2: Create Service

1. Click "Create App"
2. Select "GitHub" → Choose repo
3. Configure:
   - **Name**: bidops-ai
   - **Builder**: Docker
   - **Dockerfile**: `backend/Dockerfile.prod`
   - **Port**: 8000

### Step 3: Environment Variables

```
DATABASE_URL=sqlite+aiosqlite:////koyeb/storage/bidops.db
ENVIRONMENT=production
SECRET_KEY=[auto-generated]
```

### Step 4: Deploy

Click "Deploy" - Live in 5 minutes!

URL: `https://bidops-ai-[your-name].koyeb.app`

---

## 📱 Simplest Option: PythonAnywhere (FastAPI not ideal)

Actually, PythonAnywhere doesn't support FastAPI well.

---

## ✨ Ultimate Simple Solution: Replit.com

### Why Replit?
- ✅ 100% FREE
- ✅ No credit card
- ✅ Run full FastAPI + React
- ✅ SQLite works perfectly
- ✅ Always-on (with Hacker plan, but Basic is fine for demos)

### Deploy to Replit:

1. Go to https://replit.com
2. Sign up with GitHub
3. Click "Create Repl"
4. Import from GitHub: `https://github.com/Khalid-Galal/bidops-ai`
5. Replit auto-configures everything!
6. Click "Run"

Done! 🎉

---

## 🎯 My Recommendation

**For a 2-week customer demo:**
→ Use **Railway.app** ($5 free credit, plenty for 2 weeks)

**For longer-term free hosting:**
→ Use **Replit.com** (100% free, works great)

Would you like me to help you deploy to **Railway.app** or **Replit.com**?
