# 🚀 Deploy to Railway.app - Quick Guide

## 💰 Cost: FREE ($5 credit, no credit card with GitHub)

---

## Step 1: Sign Up (2 minutes)

1. Go to: https://railway.app
2. Click **"Login"**
3. Select **"Login with GitHub"**
4. Authorize Railway
5. ✅ You get **$5 free credit**! (Enough for 2+ weeks of demo)

---

## Step 2: Deploy from GitHub (1 minute)

1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Find and select: **`Khalid-Galal/bidops-ai`**
4. Railway will start deploying automatically!

---

## Step 3: Configure (2 minutes)

### Set Environment Variables:

1. Click on your service
2. Go to **"Variables"** tab
3. Add these:

```bash
DATABASE_URL=sqlite+aiosqlite:////app/storage/database/bidops.db
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=your-random-secret-key-change-this
```

To generate SECRET_KEY:
```bash
# Run this in your terminal
openssl rand -hex 32
```

---

## Step 4: Generate Domain (1 minute)

1. Go to **"Settings"** tab
2. Click **"Generate Domain"**
3. You'll get: `https://bidops-ai-production.up.railway.app`
4. ✅ **Copy this URL!**

---

## Step 5: Wait for Deployment (~5 minutes)

Watch the **"Deployments"** tab.

When you see:
- ✅ Build successful
- ✅ Deploy successful
- Status: Active

Your app is LIVE! 🎉

---

## Step 6: Test It!

1. Visit: `https://your-app.up.railway.app`
2. Login with:
   - **Email**: admin@example.com
   - **Password**: Admin123

---

## ⚡ Pro Tips

### View Logs:
```bash
# Install Railway CLI (optional)
npm install -g @railway/cli

# Login
railway login

# View logs
railway logs
```

### Monitor Usage:
- Go to **"Metrics"** tab
- See CPU, RAM, Network usage
- Track your $5 credit

### Estimated Runtime:
- Backend (256MB RAM): ~$0.20/day
- **Total runtime**: ~25 days on $5 credit! 🎉

---

## 🔄 Update Your App

```bash
# Make changes
git add .
git commit -m "Update feature"
git push

# Railway auto-deploys! 🚀
```

---

## 📧 Share with Customer

```
🎉 BidOps AI Demo is Ready!

🔗 https://your-app.up.railway.app

Login:
📧 admin@example.com
🔑 Admin123

Features to test:
✅ Create projects
✅ Manage suppliers
✅ Upload documents
✅ Create packages

Feedback welcome! 🚀
```

---

## 🆘 Troubleshooting

### App not loading?
- Check **"Deployments"** for errors
- View logs in **"Observability"** tab

### Database error?
- Ensure DATABASE_URL uses `/app/storage/`
- Check if storage directory exists

### Out of credit?
- Railway shows usage in **"Usage"** tab
- Can add credit card for $5/month if needed
- Or export data and redeploy on new account

---

Need help? Railway docs: https://docs.railway.app
