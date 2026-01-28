# 🚀 BidOps AI Deployment Cheat Sheet

## 📌 Quick Decision Tree

```
Do you want it FREE?
    ↓ YES → Use Render.com (See Method 1)
    ↓ NO  → Have own server?
              ↓ YES → Use Docker (See Method 2)
              ↓ NO  → Get VPS (See Method 2)
```

---

## Method 1: Render.com (FREE) - 5 minutes ⚡

### Step 1: Push to GitHub
```bash
git init && git add . && git commit -m "Deploy"
git remote add origin https://github.com/YOU/bidops-ai.git
git push -u origin main
```

### Step 2: On Render.com Dashboard

| Service | Type | Settings | Copy This |
|---------|------|----------|-----------|
| Database | PostgreSQL | Free plan | ✅ Internal DB URL |
| Cache | Redis | Free plan | ✅ Internal Redis URL |
| Backend | Web Service | Docker, Root: `backend` | ✅ Service URL |
| Frontend | Static Site | Root: `frontend`, Build: `npm ci && npm run build` | Final URL |

### Step 3: Environment Variables

**Backend:**
```
DATABASE_URL = [Paste DB URL]
REDIS_URL = [Paste Redis URL]
SECRET_KEY = [Generate]
GOOGLE_API_KEY = [Your key]
ENVIRONMENT = production
```

**Frontend:**
```
VITE_API_URL = [Backend URL]/api/v1
```

### Step 4: Initialize
Backend Shell → Run: `python create_admin.py`

**✅ Done!** Visit your frontend URL

---

## Method 2: VPS/Docker - 30 minutes 🖥️

### Quick Commands (Copy-paste entire block)

```bash
# 1. Update & Install Docker (Ubuntu 22.04)
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
apt install docker-compose git -y

# 2. Clone & Setup
git clone https://github.com/YOU/bidops-ai.git
cd bidops-ai

# 3. Create .env
cat > .env << EOF
POSTGRES_USER=bidops
POSTGRES_PASSWORD=$(openssl rand -base64 24)
POSTGRES_DB=bidops
SECRET_KEY=$(openssl rand -hex 32)
GOOGLE_API_KEY=your_key_here
ENVIRONMENT=production
DEBUG=false
EOF

# 4. Deploy
docker-compose up -d

# 5. Create Admin
docker-compose exec api python create_admin.py

# 6. Setup Firewall
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw --force enable

# ✅ Done! Visit: http://YOUR_SERVER_IP
```

---

## 🔐 Default Login (Change Immediately!)

```
Email: admin@example.com
Password: Admin123
```

---

## 🛠️ Essential Commands

### View Logs
```bash
docker-compose logs -f
docker-compose logs -f api      # Backend only
docker-compose logs -f frontend # Frontend only
```

### Restart Services
```bash
docker-compose restart
docker-compose restart api      # Restart backend only
```

### Update App
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Backup Database
```bash
docker-compose exec postgres pg_dump -U bidops bidops > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
cat backup.sql | docker-compose exec -T postgres psql -U bidops bidops
```

### Check Status
```bash
docker-compose ps
docker stats
```

### Clean Docker
```bash
docker system prune -a
docker volume prune
```

---

## 🌐 Setup Domain & SSL (Optional)

### Quick Nginx + Let's Encrypt

```bash
# Install
apt install nginx certbot python3-certbot-nginx -y

# Create config
cat > /etc/nginx/sites-available/bidops << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN.com;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
EOF

# Enable
ln -s /etc/nginx/sites-available/bidops /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx

# Get SSL
certbot --nginx -d YOUR_DOMAIN.com
```

**✅ Done!** Visit: https://YOUR_DOMAIN.com

---

## 📊 Service URLs

| Service | URL |
|---------|-----|
| Frontend | http://your-ip or http://domain |
| Backend API | http://your-ip:8000 |
| API Docs | http://your-ip:8000/docs |
| Health Check | http://your-ip:8000/api/v1/health |

---

## 🐛 Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| Backend won't start | `docker-compose logs api` |
| DB connection failed | Check DATABASE_URL in .env |
| Frontend 404 | Check VITE_API_URL env var |
| Port in use | Change ports in docker-compose.yml |
| Out of disk | `docker system prune -a` |
| Forgot password | `docker-compose exec api python create_admin.py` |

### Test Backend Health
```bash
curl http://localhost:8000/api/v1/health
# Should return: {"status":"healthy","database":"connected","redis":"connected"}
```

---

## 📋 Pre-Deployment Checklist

- [ ] Git repository created and code pushed
- [ ] Domain name configured (if using custom domain)
- [ ] Google Gemini API key obtained
- [ ] SMTP credentials ready (for emails)
- [ ] Server provisioned (for VPS deployment)
- [ ] SSH access confirmed (for VPS deployment)

---

## 📋 Post-Deployment Checklist

- [ ] Application accessible via URL
- [ ] Admin login works
- [ ] Changed default password
- [ ] Email sending works (if configured)
- [ ] SSL/HTTPS enabled (for custom domain)
- [ ] Firewall configured
- [ ] Backups scheduled
- [ ] Monitoring setup (UptimeRobot)
- [ ] Team/customer notified

---

## 💰 Cost Summary

| Provider | Monthly | RAM | Storage | Best For |
|----------|---------|-----|---------|----------|
| Render (Free) | $0* | 512MB | 1GB | Demos |
| DigitalOcean | $12 | 2GB | 50GB | Small |
| DigitalOcean | $24 | 4GB | 80GB | Medium |
| Hetzner | $5 | 2GB | 40GB | Best value |

*Free for 90 days, then $14/month

---

## 🆘 Emergency Contacts

| Issue | Action |
|-------|--------|
| Site down | Check `docker-compose ps` |
| DB corrupted | Restore from backup |
| Disk full | `docker system prune -a` |
| Memory leak | `docker-compose restart` |
| Can't login | Reset password via backend shell |

---

## 🔗 Quick Links

- Full Guide: [DEPLOYMENT-COMPLETE-GUIDE.md](./DEPLOYMENT-COMPLETE-GUIDE.md)
- Render Guide: [DEPLOY.md](./DEPLOY.md)
- Quick Start: [QUICKSTART.md](./QUICKSTART.md)
- API Docs: http://your-domain/docs

---

## 📱 Share with Customer

```
🎉 BidOps AI is now live!

🔗 [Your URL here]

Login:
📧 admin@example.com
🔑 Admin123 (please change!)

⚠️ Note: First load may take 30s (if on free tier)

Enjoy! 🚀
```

---

**Print this page for quick reference! 📄**

*Last updated: 2026-01-28*
