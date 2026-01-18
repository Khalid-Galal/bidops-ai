# 🚀 Render.com Deployment Guide - BidOps AI

This guide will help you deploy BidOps AI to Render.com for **FREE**.

## 📋 Prerequisites

1. GitHub account
2. Render.com account (sign up at https://render.com)
3. Google API key for Gemini (optional but recommended)

---

## 🎯 Step 1: Push Code to GitHub

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit for deployment"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/bidops-ai.git
git branch -M main
git push -u origin main
```

---

## 🗄️ Step 2: Create PostgreSQL Database

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name**: `bidops-postgres`
   - **Database**: `bidops`
   - **User**: `bidops`
   - **Region**: Choose closest to you
   - **Plan**: **Free** (90 days free, then $7/month or recreate)
4. Click **"Create Database"**
5. **Copy the "Internal Database URL"** - you'll need this!

---

## 📦 Step 3: Create Redis Instance

1. Click **"New +"** → **"Redis"**
2. Configure:
   - **Name**: `bidops-redis`
   - **Region**: Same as database
   - **Plan**: **Free** (90 days free)
3. Click **"Create Redis"**
4. **Copy the "Internal Redis URL"** - you'll need this!

---

## 🔧 Step 4: Deploy Backend API

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `bidops-api`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Docker`
   - **Plan**: **Free** (spins down after 15 min inactivity)

4. **Environment Variables** (click "Advanced"):
   ```
   DATABASE_URL = [Paste Internal Database URL from Step 2]
   REDIS_URL = [Paste Internal Redis URL from Step 3]
   SECRET_KEY = [Click "Generate" to create a random key]
   ENVIRONMENT = production
   DEBUG = false
   GOOGLE_API_KEY = [Your Google Gemini API key - optional]
   HOST = 0.0.0.0
   PORT = 8000
   ```

5. Click **"Create Web Service"**
6. Wait for deployment (5-10 minutes)
7. **Copy the service URL** (e.g., `https://bidops-api.onrender.com`)

---

## 🌐 Step 5: Deploy Frontend

1. Click **"New +"** → **"Static Site"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `bidops-frontend`
   - **Branch**: `main`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm ci && npm run build`
   - **Publish Directory**: `dist`

4. **Environment Variables**:
   ```
   VITE_API_URL = [Your backend URL from Step 4]/api/v1
   ```
   Example: `https://bidops-api.onrender.com/api/v1`

5. Click **"Create Static Site"**
6. Wait for deployment (3-5 minutes)
7. **Your app is live!** 🎉

---

## 🔐 Step 6: Initialize Database & Create Admin User

1. Go to your backend service: `https://bidops-api.onrender.com`
2. Click **"Shell"** tab
3. Run these commands:

```bash
# Initialize database tables
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"

# Create admin user
python create_admin.py
```

If `create_admin.py` doesn't exist, I'll create it for you.

---

## 🧪 Step 7: Test Your Deployment

1. Visit your frontend URL: `https://bidops-frontend.onrender.com`
2. Login with:
   - **Email**: `admin@example.com`
   - **Password**: `Admin123`
3. Test creating a project
4. **Send this URL to your customer!** 🚀

---

## ⚙️ Important Notes

### Free Tier Limitations:
- ⏱️ **Backend spins down after 15 minutes** of inactivity
  - First request after idle = ~30 seconds cold start
  - Solution: Use https://uptimerobot.com (free) to ping every 14 minutes

- 📅 **Database & Redis are free for 90 days**
  - After 90 days: $7/month or export data and recreate

- 💾 **No persistent file storage on free tier**
  - Uploaded files will be lost on restart
  - Solution: Use AWS S3 free tier or Cloudinary

### Performance Tips:
- Backend will be slow on first request (cold start)
- Keep a browser tab open during customer demo
- Or use UptimeRobot to keep service warm

---

## 🔄 Auto-Deploy Updates

Any push to `main` branch will automatically redeploy! 🎯

```bash
git add .
git commit -m "Update feature"
git push origin main
```

---

## 🆘 Troubleshooting

### Backend won't start:
- Check logs in Render dashboard
- Verify DATABASE_URL is correct
- Ensure all required env vars are set

### Frontend shows errors:
- Check VITE_API_URL includes `/api/v1`
- Verify backend is running
- Check browser console for CORS errors

### Database connection fails:
- Use **Internal Database URL** not External
- Ensure backend and database are in same region

---

## 💰 Cost Summary

- **Total Cost**: **$0/month** (for 90 days)
- After 90 days: ~$14/month (or recreate for free)
- Alternative: Migrate to Railway.app with $5/month credit

---

## 🎁 Bonus: Keep Service Awake

Create a free UptimeRobot monitor:
1. Go to https://uptimerobot.com
2. Create account
3. Add monitor:
   - Type: HTTP(s)
   - URL: `https://bidops-api.onrender.com/api/v1/health`
   - Interval: 5 minutes
4. This prevents cold starts during demo! ✨

---

## 📧 Share with Customer

Send them this message:

```
🎉 BidOps AI Demo is ready!

🌐 URL: https://bidops-frontend.onrender.com

🔐 Login:
Email: admin@example.com
Password: Admin123

⚠️ Note: First load may take 30 seconds (free tier),
subsequent loads will be fast!

Try:
✅ Creating a new project
✅ Uploading documents
✅ Managing suppliers
✅ Creating packages

Feedback welcome! 🚀
```

---

Need help? Check Render docs: https://render.com/docs
