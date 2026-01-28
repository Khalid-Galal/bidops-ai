# 🚀 Complete Deployment Guide - BidOps AI

This comprehensive guide covers **all deployment options** for BidOps AI, from free hosting to production servers.

---

## 📋 Table of Contents

1. [Quick Comparison](#quick-comparison)
2. [Option 1: Render.com (FREE)](#option-1-rendercom-free)
3. [Option 2: VPS with Docker (Recommended for Production)](#option-2-vps-with-docker-recommended-for-production)
4. [Option 3: Railway.app](#option-3-railwayapp)
5. [Option 4: Local/On-Premise Server](#option-4-localon-premise-server)
6. [Post-Deployment Steps](#post-deployment-steps)
7. [SSL/HTTPS Setup](#sslhttps-setup)
8. [Monitoring & Maintenance](#monitoring--maintenance)

---

## 🎯 Quick Comparison

| Option | Cost | Complexity | Best For | Setup Time |
|--------|------|------------|----------|------------|
| **Render.com** | Free for 90 days | Easy | Demos, Testing | 5-10 min |
| **VPS (DigitalOcean)** | $12-50/month | Medium | Production | 30 min |
| **Railway.app** | $5/month credit | Easy | Small teams | 5 min |
| **Local Server** | Hardware only | Medium | On-premise | 20 min |

---

## 🆓 Option 1: Render.com (FREE)

**Best for:** Demos, testing, MVPs
**Cost:** Free for 90 days, then $14/month
**Limitations:** Cold starts (30s), limited resources

### Quick Steps

See detailed guide: **[QUICKSTART.md](./QUICKSTART.md)** or **[DEPLOY.md](./DEPLOY.md)**

**Summary:**
1. Push code to GitHub
2. Create PostgreSQL + Redis on Render
3. Deploy backend as Web Service
4. Deploy frontend as Static Site
5. Configure environment variables
6. Done! ✅

**Pros:**
- ✅ Completely free for 90 days
- ✅ Auto-deploy on git push
- ✅ Built-in SSL/HTTPS
- ✅ No server management

**Cons:**
- ❌ Cold starts (30s wait after inactivity)
- ❌ Limited to free tier resources
- ❌ No persistent file storage on free tier

---

## 🖥️ Option 2: VPS with Docker (Recommended for Production)

**Best for:** Production deployments, full control
**Cost:** $12-50/month (DigitalOcean, Linode, AWS, Azure)
**Limitations:** Requires server management

### Prerequisites

- VPS server (Ubuntu 22.04 recommended)
- Domain name (optional but recommended)
- SSH access to server

### Step-by-Step Deployment

#### 1. Provision a VPS

**Recommended Providers:**
- **DigitalOcean** - $12/month (2GB RAM, 50GB SSD)
- **Linode** - $12/month (2GB RAM, 50GB SSD)
- **AWS Lightsail** - $12/month
- **Vultr** - $12/month
- **Hetzner** - €4.5/month (Best price!)

**Minimum Requirements:**
- 2GB RAM
- 2 CPU cores
- 50GB storage
- Ubuntu 22.04 LTS

#### 2. Initial Server Setup

SSH into your server:

```bash
ssh root@your-server-ip
```

**Update system:**
```bash
apt update && apt upgrade -y
```

**Install Docker:**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

**Create deployment user (optional but recommended):**
```bash
adduser bidops
usermod -aG docker bidops
usermod -aG sudo bidops

# Switch to new user
su - bidops
```

#### 3. Clone Your Project

```bash
# Install git if not present
sudo apt install git -y

# Clone your repository
cd /home/bidops
git clone https://github.com/YOUR_USERNAME/bidops-ai.git
cd bidops-ai
```

#### 4. Configure Environment Variables

Create production `.env` file:

```bash
nano .env
```

**Add the following:**

```env
# Database
POSTGRES_USER=bidops
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD_HERE
POSTGRES_DB=bidops

# Redis (no password needed for internal use)

# Backend API
SECRET_KEY=YOUR_SUPER_SECRET_KEY_AT_LEAST_32_CHARS
ENVIRONMENT=production
DEBUG=false

# Google Gemini API (for AI features)
GOOGLE_API_KEY=your_gemini_api_key_here

# Email Configuration (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourdomain.com

# Frontend
VITE_API_URL=/api/v1

# OpenAI (optional, if using OpenAI instead of Gemini)
OPENAI_API_KEY=your_openai_key_here
```

**Generate secure keys:**
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate POSTGRES_PASSWORD
openssl rand -base64 24
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

#### 5. Deploy with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check if services are running
docker-compose ps

# View logs
docker-compose logs -f
```

**Services will start on:**
- Frontend: `http://your-server-ip:80`
- Backend API: `http://your-server-ip:8000`
- PostgreSQL: Internal (port 5432)
- Redis: Internal (port 6379)

#### 6. Initialize Database & Create Admin User

```bash
# Access the backend container
docker-compose exec api bash

# Initialize database
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"

# Create admin user
python create_admin.py

# Exit container
exit
```

#### 7. Test Your Deployment

```bash
# Test backend health
curl http://localhost:8000/api/v1/health

# Test frontend
curl http://localhost:80
```

Visit: `http://your-server-ip`

**Default login:**
- Email: `admin@example.com`
- Password: `Admin123`

#### 8. Setup Firewall (Important!)

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Check status
sudo ufw status
```

#### 9. Setup Domain (Optional)

**A. Point your domain to server:**
- Create an A record pointing to your server IP
- Example: `bidops.yourdomain.com` → `123.45.67.89`

**B. Setup Nginx reverse proxy with SSL:**

```bash
# Install Nginx
sudo apt install nginx certbot python3-certbot-nginx -y

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/bidops
```

**Add this configuration:**

```nginx
server {
    listen 80;
    server_name bidops.yourdomain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable site and restart Nginx:**

```bash
sudo ln -s /etc/nginx/sites-available/bidops /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**C. Setup SSL with Let's Encrypt (Free):**

```bash
sudo certbot --nginx -d bidops.yourdomain.com

# Follow prompts to setup SSL
# Choose option 2 to redirect all HTTP to HTTPS
```

**D. Test your site:**
Visit: `https://bidops.yourdomain.com` ✅

#### 10. Auto-Restart on Reboot

Docker Compose services are already set to restart automatically (`restart: unless-stopped`).

To ensure Docker starts on boot:

```bash
sudo systemctl enable docker
```

---

## 🚂 Option 3: Railway.app

**Best for:** Quick deployment, small teams
**Cost:** $5/month credit (can cover small apps)

### Deployment Steps

1. **Sign up at https://railway.app**

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your repository

3. **Add PostgreSQL**
   - Click "Add Service"
   - Select "PostgreSQL"
   - Railway will auto-provision

4. **Add Redis**
   - Click "Add Service"
   - Select "Redis"
   - Railway will auto-provision

5. **Configure Backend Service**
   - Railway auto-detects the backend Dockerfile
   - Add environment variables:
     ```
     DATABASE_URL = ${{Postgres.DATABASE_URL}}
     REDIS_URL = ${{Redis.REDIS_URL}}
     SECRET_KEY = [Generate random]
     ENVIRONMENT = production
     DEBUG = false
     GOOGLE_API_KEY = your_key_here
     ```

6. **Configure Frontend Service**
   - Add environment variable:
     ```
     VITE_API_URL = ${{backend.RAILWAY_PUBLIC_DOMAIN}}/api/v1
     ```

7. **Deploy!**
   - Railway automatically builds and deploys
   - Get your public URL

**Auto-deploy:** Every git push to main automatically redeploys!

---

## 🏠 Option 4: Local/On-Premise Server

**Best for:** Companies with existing infrastructure, data privacy requirements

### Deployment on Windows Server

#### Prerequisites
- Windows Server 2019/2022
- Docker Desktop for Windows
- 4GB RAM minimum
- 100GB storage

#### Steps

1. **Install Docker Desktop**
   - Download from https://www.docker.com/products/docker-desktop
   - Install and restart

2. **Clone Repository**
   ```powershell
   git clone https://github.com/YOUR_USERNAME/bidops-ai.git
   cd bidops-ai
   ```

3. **Configure .env file**
   - Copy `.env.example` to `.env`
   - Update values

4. **Deploy**
   ```powershell
   docker-compose up -d
   ```

5. **Access Application**
   - Frontend: http://localhost
   - Backend: http://localhost:8000

### Deployment on Linux Server (Ubuntu)

Same as Option 2 VPS deployment above, but on your local network.

**Access from other computers:**
- Use server's local IP: `http://192.168.x.x`
- Or setup internal DNS

---

## ✅ Post-Deployment Steps

### 1. Create Admin User

If not created during deployment:

```bash
# Access backend container
docker-compose exec api python create_admin.py

# Or manually via Python
docker-compose exec api python
>>> from app.auth.password import hash_password
>>> from app.models.user import User, UserRole
>>> # Create user in database
```

### 2. Configure Email (Optional)

Update `.env` with SMTP settings:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourdomain.com
```

**For Gmail:**
1. Enable 2-factor authentication
2. Generate App Password
3. Use that password in SMTP_PASSWORD

### 3. Setup File Storage (Production)

For production, configure S3 or similar:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
```

### 4. Configure Backups

**Database Backup Script:**

Create `backup.sh`:

```bash
#!/bin/bash
# Backup PostgreSQL database

BACKUP_DIR="/home/bidops/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="bidops_backup_$DATE.sql"

mkdir -p $BACKUP_DIR

docker-compose exec -T postgres pg_dump -U bidops bidops > "$BACKUP_DIR/$FILENAME"
gzip "$BACKUP_DIR/$FILENAME"

# Keep only last 7 days
find $BACKUP_DIR -name "bidops_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $FILENAME.gz"
```

**Make executable and schedule:**

```bash
chmod +x backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/bidops/bidops-ai/backup.sh
```

---

## 🔒 SSL/HTTPS Setup

### Option A: Let's Encrypt (Free)

Already covered in VPS deployment above (using Certbot).

### Option B: Cloudflare (Free + CDN)

1. **Sign up at https://cloudflare.com**
2. **Add your domain**
3. **Update nameservers** at your domain registrar
4. **Enable SSL/TLS:** Set to "Full" mode
5. **Benefits:**
   - Free SSL certificate
   - DDoS protection
   - CDN (faster loading)
   - Analytics

### Option C: Custom SSL Certificate

If you have your own certificate:

```nginx
server {
    listen 443 ssl http2;
    server_name bidops.yourdomain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    # ... rest of nginx config
}
```

---

## 📊 Monitoring & Maintenance

### 1. Health Checks

**Backend health endpoint:**
```bash
curl http://your-domain.com/api/v1/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### 2. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f frontend
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 api
```

### 3. Monitor Resource Usage

```bash
# Check Docker stats
docker stats

# Check disk space
df -h

# Check memory
free -h
```

### 4. Uptime Monitoring

**Use UptimeRobot (Free):**
1. Go to https://uptimerobot.com
2. Create account
3. Add monitor:
   - Type: HTTP(s)
   - URL: `https://your-domain.com/api/v1/health`
   - Interval: 5 minutes
4. Get alerts via email/SMS when site is down

### 5. Update Application

```bash
# Pull latest code
cd /home/bidops/bidops-ai
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### 6. Database Maintenance

```bash
# Backup database
docker-compose exec postgres pg_dump -U bidops bidops > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U bidops bidops < backup.sql

# Vacuum database (cleanup)
docker-compose exec postgres psql -U bidops bidops -c "VACUUM ANALYZE;"
```

---

## 🐛 Troubleshooting

### Issue: Backend won't start

**Check logs:**
```bash
docker-compose logs api
```

**Common causes:**
- Database connection failed
- Missing environment variables
- Port already in use

**Solution:**
```bash
# Check environment variables
docker-compose exec api env | grep DATABASE_URL

# Restart services
docker-compose restart
```

### Issue: Frontend shows 404 errors

**Check:**
- VITE_API_URL is correct
- Backend is running
- Nginx configuration (if using)

**Solution:**
```bash
# Rebuild frontend
docker-compose up -d --build frontend
```

### Issue: Database connection errors

**Check:**
- PostgreSQL is running: `docker-compose ps postgres`
- Credentials are correct in `.env`
- Database exists

**Solution:**
```bash
# Recreate database
docker-compose down
docker volume rm bidops-ai_postgres_data
docker-compose up -d
```

### Issue: Out of disk space

**Check space:**
```bash
df -h
```

**Clean Docker:**
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused containers
docker container prune
```

---

## 💰 Cost Comparison

| Provider | Monthly Cost | Resources | Best For |
|----------|--------------|-----------|----------|
| **Render (Free)** | $0 (90 days) | 512MB RAM, Shared CPU | Demos, Testing |
| **Railway** | $5 credit | 512MB RAM, 1GB Storage | Small apps |
| **DigitalOcean** | $12 | 2GB RAM, 50GB SSD | Small production |
| **DigitalOcean** | $24 | 4GB RAM, 80GB SSD | Medium production |
| **Linode** | $12 | 2GB RAM, 50GB SSD | Small production |
| **Hetzner** | €4.5 (~$5) | 2GB RAM, 40GB SSD | Best value! |
| **AWS Lightsail** | $12 | 2GB RAM, 60GB SSD | AWS ecosystem |

---

## 📧 Share with Your Team

Once deployed, share this information:

```
🎉 BidOps AI is now live!

🔗 URL: https://your-domain.com
   or http://your-server-ip

🔐 Admin Login:
📧 Email: admin@example.com
🔑 Password: Admin123

⚠️ IMPORTANT: Change the default password immediately!

📖 User Manual: [Link to docs]

💬 Support: your-email@example.com
```

---

## 🎓 Next Steps

After successful deployment:

1. **✅ Change default admin password**
2. **✅ Configure email settings**
3. **✅ Setup SSL/HTTPS**
4. **✅ Configure backups**
5. **✅ Setup monitoring**
6. **✅ Test all features**
7. **✅ Train users**
8. **✅ Create user accounts**

---

## 📞 Support

For deployment issues:
- Check logs: `docker-compose logs -f`
- Review troubleshooting section above
- Check Render docs: https://render.com/docs
- Check Docker docs: https://docs.docker.com

---

**Congratulations! Your BidOps AI application is now deployed! 🚀**

For questions or issues, check the logs and documentation above.
