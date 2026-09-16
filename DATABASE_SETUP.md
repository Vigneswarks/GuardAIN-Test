# GuardAIN - Database & Redis Integration Guide

## Overview

This guide shows you how to integrate PostgreSQL (database) and Redis (caching) with GuardAIN for production deployments.

---

## 📦 PostgreSQL Setup

### Windows

#### 1. Install PostgreSQL

```bash
# Download from: https://www.postgresql.org/download/windows/
# Run installer and note your password
```

#### 2. Create Database

```bash
# Open Command Prompt as Administrator
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE guardain_db;
CREATE USER guardain_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE guardain_db TO guardain_user;
\q
```

#### 3. Configure Connection

```bash
# Set environment variable (Windows CMD)
set DATABASE_URL=postgresql://guardain_user:your_secure_password@localhost:5432/guardain_db

# Or set in .env file
# DATABASE_URL=postgresql://guardain_user:your_secure_password@localhost:5432/guardain_db
```

#### 4. Enable in Code

In `backend/app/api.py`:
```python
# Uncomment PostgreSQL integration
# from sqlalchemy import create_engine
# engine = create_engine(DATABASE_URL)
```

### macOS

```bash
# Install with Homebrew
brew install postgresql

# Start service
brew services start postgresql

# Create database
psql postgres
CREATE DATABASE guardain_db;
CREATE USER guardain_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE guardain_db TO guardain_user;
\q

# Set environment
export DATABASE_URL=postgresql://guardain_user:your_secure_password@localhost:5432/guardain_db
```

### Linux (Ubuntu/Debian)

```bash
# Install
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE guardain_db;
CREATE USER guardain_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE guardain_db TO guardain_user;
\q

# Set environment
export DATABASE_URL=postgresql://guardain_user:your_secure_password@localhost:5432/guardain_db
```

---

## 🔴 Redis Setup

### Windows

#### 1. Install Redis

```bash
# Download from: https://github.com/microsoftarchive/redis/releases
# Or use Windows Subsystem for Linux (WSL)

# Using Chocolatey (if installed)
choco install redis-64
```

#### 2. Start Redis

```bash
# Command Prompt
redis-server

# Or install as Windows service
redis-server --service-install
redis-server --service-start
```

#### 3. Configure Connection

```bash
# Set environment variable
set REDIS_URL=redis://localhost:6379/0

# With password (optional)
set REDIS_URL=redis://:password@localhost:6379/0
```

### macOS

```bash
# Install with Homebrew
brew install redis

# Start service
brew services start redis

# Or run directly
redis-server

# Configure connection
export REDIS_URL=redis://localhost:6379/0
```

### Linux (Ubuntu/Debian)

```bash
# Install
sudo apt update
sudo apt install redis-server

# Start service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Configure connection
export REDIS_URL=redis://localhost:6379/0
```

---

## 🔐 Redis with Authentication

### Setup Password Protection

#### Windows/macOS/Linux

1. Edit Redis config file:
   - Windows: `C:\Program Files\Redis\redis.conf`
   - macOS: `/usr/local/etc/redis.conf`
   - Linux: `/etc/redis/redis.conf`

2. Find and uncomment:
```
requirepass your_redis_password
```

3. Restart Redis service

4. Update connection:
```bash
export REDIS_URL=redis://:your_redis_password@localhost:6379/0
```

---

## 🐳 Docker Compose (Complete Stack)

### Setup Everything with Docker

1. Create `.env` file:

```env
# Database
DATABASE_URL=postgresql://guardain_user:guardain_password@postgres:5432/guardain_db

# Redis
REDIS_URL=redis://redis:6379/0

# Security
GUARDAIN_ADMIN_PASSWORD=admin@26
JWT_SECRET_KEY=your_super_secret_key_here

# Environment
ENVIRONMENT=production
PORT=8080
```

2. Start services:

```bash
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f api
docker-compose logs -f postgres
docker-compose logs -f redis

# Stop services
docker-compose down
```

### Access Services

- **API**: http://localhost:8080
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

---

## 🔄 Complete Integration Example

### Update backend/app/api.py

```python
import os
import redis.asyncio as redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Redis Cache
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL)

# Use in your endpoints
@app.post("/api/scan")
async def scan_url(request: URLScanRequest):
    # Check cache first
    cached = await redis_client.get(f"scan:{request.url}")
    if cached:
        return json.loads(cached)
    
    # Perform scan
    result = threat_db.check_url(request.url)
    
    # Cache result (1 hour)
    await redis_client.setex(
        f"scan:{request.url}",
        3600,
        json.dumps(result)
    )
    
    return result
```

---

## 🧪 Test Database Connection

### Test PostgreSQL

```bash
# From Python
python
>>> import psycopg2
>>> conn = psycopg2.connect("postgresql://user:pass@localhost/guardain_db")
>>> cursor = conn.cursor()
>>> cursor.execute("SELECT version();")
>>> print(cursor.fetchone())
```

### Test Redis

```bash
# Using redis-cli
redis-cli
> ping
PONG

> set test_key "Hello"
OK

> get test_key
"Hello"

> quit
```

---

## 📊 Monitoring & Troubleshooting

### PostgreSQL

```bash
# Check if running
pg_isready -h localhost -U guardain_user

# View database size
psql -U guardain_user -d guardain_db -c "SELECT pg_size_pretty(pg_database_size('guardain_db'));"

# View tables
psql -U guardain_user -d guardain_db -c "\dt"

# View connections
psql -U guardain_user -d guardain_db -c "SELECT * FROM pg_stat_activity;"
```

### Redis

```bash
# Check if running
redis-cli ping

# View memory usage
redis-cli info memory

# View all keys
redis-cli keys "*"

# Clear cache
redis-cli FLUSHALL

# View database stats
redis-cli info stats
```

---

## 🚨 Common Issues

### PostgreSQL Connection Failed

```bash
# Check if running
psql -U postgres -c "SELECT 1"

# Verify password
psql -U guardain_user -h localhost -c "SELECT 1"

# Check pg_hba.conf for authentication method
```

### Redis Connection Failed

```bash
# Check if running
redis-cli ping

# Check port
netstat -ano | findstr :6379

# Verify password if set
redis-cli -a your_password ping
```

### Port Already in Use

```bash
# PostgreSQL default: 5432
netstat -ano | findstr :5432

# Redis default: 6379
netstat -ano | findstr :6379

# Kill process if needed
taskkill /PID <PID> /F
```

---

## 🔒 Security Best Practices

1. **Strong Passwords**
   - PostgreSQL: Use 16+ character passwords
   - Redis: Use strong `requirepass`

2. **Network Security**
   - Don't expose ports to public internet
   - Use firewall rules
   - Use VPN for remote access

3. **Backups**
   - Daily PostgreSQL backups
   - Redis persistence enabled
   - Test restore procedures

4. **Updates**
   - Keep PostgreSQL updated
   - Keep Redis updated
   - Apply security patches

5. **Monitoring**
   - Monitor disk space
   - Monitor memory usage
   - Set up alerts

---

## 📈 Production Checklist

- [ ] PostgreSQL installed and configured
- [ ] Redis installed and configured
- [ ] Strong passwords set
- [ ] Firewall rules configured
- [ ] Backups configured
- [ ] Monitoring enabled
- [ ] Environment variables set
- [ ] SSL/TLS configured
- [ ] Database initialized
- [ ] Connection tested

---

## 🆘 Quick Reference

### Connection Strings

```bash
# PostgreSQL (standard)
postgresql://user:password@localhost:5432/database

# PostgreSQL (with SSL)
postgresql://user:password@localhost:5432/database?sslmode=require

# Redis (standard)
redis://localhost:6379/0

# Redis (with password)
redis://:password@localhost:6379/0

# Redis (with SSL)
rediss://user:password@localhost:6379/0
```

### Environment Variables

```bash
# PostgreSQL
export DATABASE_URL=postgresql://user:pass@host:5432/db

# Redis
export REDIS_URL=redis://host:6379/0

# Admin
export GUARDAIN_ADMIN_PASSWORD=admin@26

# JWT
export JWT_SECRET_KEY=your_secret_key
```

---

## 📚 Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [FastAPI + Databases](https://fastapi.tiangolo.com/advanced/sql-databases/)

---

**Version**: 1.0.0
**Last Updated**: 2024
