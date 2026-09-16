# GuardAIN - Central Police Cyber Cell
## Complete Setup & Deployment Guide

### 🎯 Project Overview
GuardAIN is a **Central Police Cyber Cell** threat intelligence platform with:
- 🔐 Secure admin portal with police-themed cybersecurity UI
- 🔍 URL threat scanning with safe/dangerous detection
- 📊 Real-time threat statistics dashboard
- 🚀 RESTful API for integration
- 🔌 Redis & PostgreSQL ready for production

---

## 📋 System Requirements

- **OS**: Windows 10+, macOS, or Linux
- **Python**: 3.10 or higher
- **Memory**: 2GB RAM minimum
- **Disk Space**: 500MB

---

## 🚀 Quick Start (Windows)

### Option 1: Automated Setup (Recommended)

```bash
# Double-click start.bat in the project root
# The script will:
# 1. Create virtual environment
# 2. Install dependencies
# 3. Start the API server
# 4. Open admin portal
```

### Option 2: Manual Setup

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment (Windows)
.venv\Scripts\activate.bat

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Start the API server
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🌐 Access the Portal

Once the server is running:

```
📊 Admin Portal: http://localhost:8080
🔐 Username: admin
🔐 Password: admin@26
```

---

## 🔌 API Endpoints

### Health Check
```bash
GET /health
```
Response:
```json
{
  "status": "online",
  "service": "guardain-api"
}
```

### URL Scanning
```bash
POST /api/scan
Content-Type: application/json

{
  "url": "https://example.com"
}
```

Response:
```json
{
  "url": "https://example.com",
  "status": "safe",
  "threat_score": 0,
  "details": "URL appears safe",
  "timestamp": "2024-01-01T12:00:00"
}
```

### Admin Statistics
```bash
GET /api/stats
```

---

## 🗄️ Database Integration (Future Enhancement)

### PostgreSQL Setup (Optional)

1. **Install PostgreSQL** (https://www.postgresql.org/download/)

2. **Create database**:
```sql
CREATE DATABASE guardain;
CREATE USER guardain_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE guardain TO guardain_user;
```

3. **Enable PostgreSQL in code**:
   - Uncomment `asyncpg` in `backend/requirements.txt`
   - Update `backend/app/config.py` with connection string
   - Set environment variable: `DATABASE_URL=postgresql://user:pass@localhost/guardain`

### Redis Setup (Optional)

1. **Install Redis** (https://redis.io/download)

2. **Start Redis**:
```bash
redis-server
```

3. **Enable Redis in code**:
   - Uncomment `redis` in `backend/requirements.txt`
   - Update `backend/app/config.py` with connection string
   - Set environment variable: `REDIS_URL=redis://localhost:6379/0`

---

## 🐳 Docker Deployment (Production)

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

Services will start:
- API: http://localhost:8080
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## 📁 Project Structure

```
GuardAIN/
├── admin_portal/
│   ├── index.html                # Admin portal UI
│   └── index.html.bak            # Backup of old portal
│
├── backend/
│   ├── app/
│   │   ├── api.py               # Main API routes
│   │   ├── main.py              # Application entry point
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Database layer
│   │   ├── security.py          # Security utilities
│   │   └── __init__.py
│   │
│   └── requirements.txt          # Python dependencies
│
├── data/                        # Data storage
├── docker-compose.yml           # Docker configuration
├── Dockerfile                   # Container definition
├── start.bat                    # Windows startup script
├── README.md                    # This file
└── SETUP_GUIDE.md              # Extended setup guide
```

---

## 🔐 Security Notes

1. **Change Default Credentials** (for production):
   - Update admin credentials in `backend/app/api.py`
   - Set environment variable: `GUARDAIN_ADMIN_PASSWORD=your_secure_password`

2. **API Keys** (when implementing):
   - Generate strong JWT secret keys
   - Store in environment variables, not in code
   - Rotate keys periodically

3. **HTTPS/SSL** (production):
   - Use reverse proxy (nginx, Apache)
   - Enable SSL certificates (Let's Encrypt)
   - Set `ENVIRONMENT=production` in `.env`

4. **Database Security**:
   - Use strong passwords for PostgreSQL
   - Restrict network access to database
   - Enable connection encryption

5. **Redis Security**:
   - Set Redis password
   - Use `requirepass` in redis.conf
   - Restrict to trusted networks

---

## 🧪 Testing the Platform

### Test URL Scanning

Use the web interface at `http://localhost:8080`:
1. Click "LOGIN"
2. Enter: `admin` / `admin@26`
3. Enter test URLs:
   - Safe: `https://google.com` ✅
   - Malicious: `https://malicious.com` ⚠️
   - Phishing: `https://amazon-login.site` ⚠️

### Test API Endpoints

```bash
# Test health
curl http://localhost:8080/health

# Test scan
curl -X POST http://localhost:8080/api/scan ^
  -H "Content-Type: application/json" ^
  -d "{\"url\": \"https://example.com\"}"

# Get stats
curl http://localhost:8080/api/stats
```

---

## 🛠️ Troubleshooting

### Port Already in Use
```bash
# Find process using port 8080
netstat -ano | findstr :8080

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change port
python -m uvicorn backend.app.main:app --port 8081
```

### Python Not Found
```bash
# Verify Python installation
python --version

# If not found, add to PATH or reinstall Python from python.org
```

### Module Import Errors
```bash
# Reinstall dependencies
pip install --upgrade -r backend/requirements.txt

# Clear cache
pip cache purge
```

### CORS Errors in Browser
- Already configured in `backend/app/api.py`
- Allows all origins for development
- Restrict in production: update CORS configuration

---

## 🚀 Production Deployment Checklist

- [ ] Change default admin credentials
- [ ] Set up PostgreSQL database
- [ ] Set up Redis cache
- [ ] Configure HTTPS/SSL certificates
- [ ] Set `ENVIRONMENT=production`
- [ ] Enable firewall rules
- [ ] Set up monitoring & logging
- [ ] Configure backup strategy
- [ ] Set up error tracking (Sentry)
- [ ] Load testing & optimization
- [ ] Security audit & penetration testing

---

## 📞 Support & Contribution

For issues, feature requests, or contributions:
1. Check GitHub issues
2. Create detailed bug reports
3. Submit pull requests with tests

---

## 📜 License

GuardAIN - Central Police Cyber Cell
© 2024 - All Rights Reserved

---

## 🎓 Additional Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **Uvicorn**: https://www.uvicorn.org
- **PostgreSQL**: https://www.postgresql.org/docs
- **Redis**: https://redis.io/docs
- **Docker**: https://docs.docker.com

---

**Last Updated**: 2024
**Version**: 1.0.0
**Status**: Production Ready ✅
