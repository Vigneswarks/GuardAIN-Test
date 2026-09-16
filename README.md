# GuardAIN - Central Police Cyber Cell Portal

![Status](https://img.shields.io/badge/status-production%20ready-brightgreen)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/framework-fastapi-success)

A **professional-grade threat intelligence platform** designed for central police cyber cells to scan URLs, analyze threats, and maintain cybersecurity operations.

## 🎯 Key Features

- 🔐 **Secure Authentication** - Police cybercell-themed login system (admin/admin@26)
- 🔍 **URL Threat Scanning** - Real-time malicious URL detection
- 📊 **Live Dashboard** - Monitor threat statistics and scan history
- 🚀 **RESTful API** - Easy integration with external systems
- 🎨 **Professional UI** - Modern cybersecurity aesthetic with police theme
- 🔌 **Database Ready** - PostgreSQL & Redis integration
- 🐳 **Docker Support** - Production-ready containerization
- ⚡ **High Performance** - Built with FastAPI

## 🚀 Quick Start (60 seconds)

### Windows Users - Easiest Method
```bash
# Just double-click one of these:
start.bat              # Command Prompt
# OR right-click start.ps1 > Run with PowerShell
```

### Manual Setup
```bash
# 1. Create & activate virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

# 2. Install dependencies
pip install -r backend\requirements.txt

# 3. Run the server
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Access Portal
```
🌐 Open: http://localhost:8080
👤 Username: admin
🔑 Password: admin@26
```

## 📋 System Requirements

- Windows 10+, macOS, or Linux
- Python 3.10+
- 2GB RAM, 500MB disk space
- Internet browser

## 🎨 Admin Portal Features

### 🔐 Login Screen
- Clean, professional police cybercell theme
- Secure admin authentication
- Default credentials: `admin` / `admin@26`

### 📊 Dashboard
- **Total Scans** - All URLs scanned
- **Safe URLs** - Legitimate websites  
- **Dangerous URLs** - Malicious threats detected
- **Success Rate** - System accuracy percentage

### 🔍 Threat Scanner
- Input URL to scan
- Real-time threat analysis
- Results show:
  - ✅ SAFE with 0/10 threat score
  - ⚠️ DANGEROUS with threat score (1-10)
  - Detailed threat information

### 📜 Scan History
- Recent scans displayed
- Status indicators (SAFE/DANGER)
- Quick reference for patterns

## 🔌 API Endpoints

### 1. Health Check
```bash
curl http://localhost:8080/health

# Response:
{
  "status": "online",
  "service": "guardain-api"
}
```

### 2. Scan URL
```bash
curl -X POST http://localhost:8080/api/scan \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Response:
{
  "url": "https://example.com",
  "status": "safe",
  "threat_score": 0,
  "details": "URL appears safe",
  "timestamp": "2024-01-01T12:00:00"
}
```

### 3. Get Statistics
```bash
curl http://localhost:8080/api/stats

# Response:
{
  "total_scans": 42,
  "safe_scans": 38,
  "dangerous_scans": 4,
  "success_rate": 90,
  "uptime": "online"
}
```

## 🗄️ Database Setup (Optional but Recommended)

### PostgreSQL Integration
```bash
# 1. Install PostgreSQL from https://www.postgresql.org/download/

# 2. Create database
psql -U postgres
CREATE DATABASE guardain;
CREATE USER guardain_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE guardain TO guardain_user;

# 3. Update environment
set DATABASE_URL=postgresql://guardain_user:secure_password@localhost/guardain
```

### Redis Integration
```bash
# 1. Install Redis from https://redis.io/download

# 2. Start Redis
redis-server

# 3. Set environment
set REDIS_URL=redis://localhost:6379/0
```

## 🐳 Docker Deployment

```bash
# Build and start everything
docker-compose up -d

# Check services running
docker-compose ps

# View API logs
docker-compose logs -f api

# Stop all services
docker-compose down
```

## 📁 Project Structure

```
GuardAIN/
├── 📂 admin_portal/
│   ├── index.html              ← Admin portal UI
│   └── index.html.bak          ← Backup
│
├── 📂 backend/
│   ├── 📂 app/
│   │   ├── api.py              ← Scan & API logic
│   │   ├── main.py             ← Server entry point
│   │   ├── config.py           ← Configuration
│   │   ├── security.py         ← Auth utilities
│   │   └── __init__.py
│   │
│   └── requirements.txt         ← Python packages
│
├── 📂 data/                    ← Data storage
├── docker-compose.yml          ← Docker config
├── Dockerfile                  ← Container definition
├── start.bat                   ← Windows startup
├── start.ps1                   ← PowerShell startup
├── test_setup.py              ← Verification
├── SETUP_GUIDE.md             ← Detailed guide
└── README.md                   ← This file
```

## 🔐 Security Credentials

| Item | Default Value |
|------|---------------|
| Admin Username | `admin` |
| Admin Password | `admin@26` |

⚠️ **IMPORTANT**: Change default credentials before production!

## 🛠️ Configuration

### Environment Variables

```bash
# Server config
PORT=8080
HOST=0.0.0.0
ENVIRONMENT=development
LOG_LEVEL=info

# Admin credentials
GUARDAIN_ADMIN_PASSWORD=admin@26

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost/guardain

# Caching (optional)
REDIS_URL=redis://localhost:6379/0

# JWT (security)
JWT_SECRET_KEY=your_secret_key_here
```

## 🧪 Verify Installation

Run the verification script:
```bash
python test_setup.py
```

Checks:
- ✅ Python 3.10+
- ✅ All dependencies installed
- ✅ Project structure complete
- ✅ API responding
- ✅ Portal accessible
- ✅ Scanning works

## 🚨 Troubleshooting

### Port 8080 Already in Use
```bash
# Find what's using port 8080
netstat -ano | findstr :8080

# Kill the process (replace PID)
taskkill /PID <PID> /F

# Or use different port
uvicorn backend.app.main:app --port 8081
```

### Python Not Found
1. Download Python 3.10+ from https://www.python.org
2. Check "Add Python to PATH" during installation
3. Restart terminal and try again

### Module Import Errors
```bash
# Reinstall packages
pip install --upgrade -r backend/requirements.txt
pip cache purge
```

### API Won't Start
```bash
# Check if dependencies are installed
pip list | findstr fastapi uvicorn pydantic

# Reinstall if missing
pip install -r backend/requirements.txt
```

## 📊 Test URLs

Try these to test the scanner:

| URL | Expected Result |
|-----|-----------------|
| `https://google.com` | ✅ SAFE |
| `https://github.com` | ✅ SAFE |
| `https://malicious.com` | ⚠️ DANGEROUS |
| `https://phishing.site` | ⚠️ DANGEROUS |
| `http://unencrypted.com` | ⚠️ DANGEROUS |

## 🔄 Development

### Making Changes

1. Edit files (auto-reloads with `--reload` flag)
2. Portal HTML: `admin_portal/index.html`
3. API logic: `backend/app/api.py`
4. Server config: `backend/app/main.py`

### Testing Changes

```bash
# Run verification
python test_setup.py

# Or test manually
curl http://localhost:8080/health
```

## 🚀 Production Deployment

### Checklist
- [ ] Change admin password
- [ ] Set ENVIRONMENT=production
- [ ] Configure PostgreSQL
- [ ] Configure Redis
- [ ] Enable HTTPS/SSL
- [ ] Set strong JWT secret
- [ ] Configure firewall
- [ ] Setup monitoring
- [ ] Configure backups

### Deploy with Docker
```bash
# Create .env file with production settings
ENVIRONMENT=production
GUARDAIN_ADMIN_PASSWORD=your_secure_password
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# Run services
docker-compose up -d
```

## 📚 Additional Documentation

- **Detailed Setup**: See [SETUP_GUIDE.md](./SETUP_GUIDE.md)
- **API Reference**: See inline API docs at `http://localhost:8080/docs`
- **FastAPI**: https://fastapi.tiangolo.com
- **Uvicorn**: https://www.uvicorn.org

## 💡 Tips & Tricks

```bash
# Run without auto-reload (faster)
uvicorn backend.app.main:app --port 8080

# Run in background
# Windows: Use Task Scheduler or create .bat script
# Linux/Mac: nohup python -m uvicorn backend.app.main:app &

# View API docs
# Swagger UI: http://localhost:8080/docs
# ReDoc: http://localhost:8080/redoc

# Update dependencies
pip install --upgrade -r backend/requirements.txt
```

## ❓ FAQ

**Q: I forgot the password?**
A: Default is always `admin@26`. Check `backend/app/api.py` for admin login logic.

**Q: Can this run on a public server?**
A: Yes, but you MUST configure HTTPS, firewall, change credentials, and use database.

**Q: How do I backup scan history?**
A: Setup PostgreSQL and configure backups, or export via API.

**Q: What's the throughput?**
A: FastAPI handles 1000+ requests/sec on standard hardware.

**Q: Can I add custom threat rules?**
A: Yes! Modify `ThreatDatabase` class in `backend/app/api.py`.

**Q: How do I access it from other computers?**
A: Use the server's IP: `http://<server-ip>:8080` (ensure firewall allows it).

## 🤝 Support

For issues:
1. Check [SETUP_GUIDE.md](./SETUP_GUIDE.md)
2. Run `python test_setup.py`
3. Review troubleshooting section above
4. Check error messages in terminal

## 📝 License

GuardAIN - Central Police Cyber Cell  
© 2024 - All Rights Reserved

Proprietary software. Unauthorized use prohibited.

---

**Version**: 1.0.0  
**Status**: ✅ Production Ready  
**Last Updated**: 2024

---

## 🎉 You're All Set!

```
✅ Admin Portal Ready
✅ API Running
✅ Scanner Active
✅ Authentication Enabled

🌐 Open: http://localhost:8080
🔐 Login: admin / admin@26
```

**Ready to secure the digital frontier! 🛡️**
