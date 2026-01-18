# 🚀 Quick Deploy to Render.com (5 Minutes)

## Step 1: Push to GitHub (2 min)
```bash
git init
git add .
git commit -m "Deploy to Render"
git remote add origin https://github.com/YOUR_USERNAME/bidops-ai.git
git push -u origin main
```

## Step 2: Create Services on Render.com (3 min)

### A. Create Database
1. New → PostgreSQL
2. Name: `bidops-postgres`, Plan: **Free**
3. **Copy Internal URL**

### B. Create Redis
1. New → Redis
2. Name: `bidops-redis`, Plan: **Free**
3. **Copy Internal URL**

### C. Create Backend
1. New → Web Service
2. Connect GitHub → Select repo
3. Settings:
   - Name: `bidops-api`
   - Root: `backend`
   - Runtime: **Docker**
   - Dockerfile: `Dockerfile.prod`
   - Plan: **Free**

4. Environment Variables (see `.env.render`):
   ```
   DATABASE_URL = [Paste Internal DB URL - change postgresql:// to postgresql+asyncpg://]
   REDIS_URL = [Paste Internal Redis URL]
   SECRET_KEY = [Click Generate]
   ENVIRONMENT = production
   DEBUG = false
   HOST = 0.0.0.0
   PORT = 8000
   ```

5. Deploy! (Wait ~5 min)
6. **Copy service URL**: `https://bidops-api-xxxx.onrender.com`

### D. Create Frontend
1. New → Static Site
2. Connect GitHub → Select repo
3. Settings:
   - Name: `bidops-frontend`
   - Root: `frontend`
   - Build: `npm ci && npm run build`
   - Publish: `dist`
   - Plan: **Free**

4. Environment Variable:
   ```
   VITE_API_URL = [Your backend URL]/api/v1
   ```
   Example: `https://bidops-api-xxxx.onrender.com/api/v1`

5. Deploy! (Wait ~3 min)

## Step 3: Test & Share 🎉

1. Visit: `https://bidops-frontend-xxxx.onrender.com`
2. Login:
   - Email: `admin@example.com`
   - Password: `Admin123`
3. **Share URL with customer!**

---

## ⚡ Pro Tips

**Prevent Cold Starts:**
- Sign up at https://uptimerobot.com (free)
- Create monitor: Ping your backend `/api/v1/health` every 5 minutes
- No more 30-second wait times!

**Cost:**
- First 90 days: **$0**
- After 90 days: ~$14/month or recreate services for free

**Auto-Deploy:**
Any `git push` will automatically redeploy! 🚀

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend won't start | Check DATABASE_URL starts with `postgresql+asyncpg://` |
| Frontend shows 404 | Verify VITE_API_URL ends with `/api/v1` |
| First load slow | Normal! Free tier spins down. Use UptimeRobot |
| CORS errors | Backend allows all origins (check main.py line 59) |

---

## 📧 Send to Customer

```
🎉 BidOps AI is live!

🔗 https://bidops-frontend-xxxx.onrender.com

Login:
📧 admin@example.com
🔑 Admin123

⚠️ First load takes ~30 sec (free hosting)
After that, it's fast! ⚡

Test features:
✅ Create projects
✅ Upload documents
✅ Manage suppliers
✅ Create packages

Your feedback is valuable! 🚀
```

---

Need help? Read full guide: [DEPLOY.md](./DEPLOY.md)
