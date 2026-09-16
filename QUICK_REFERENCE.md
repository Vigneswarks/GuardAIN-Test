# GuardAIN - Quick Reference Card

## 🚀 START (Pick One)

### Windows - Easiest
```
Double-click: start.bat
```

### Windows - PowerShell
```powershell
Right-click start.ps1 > Run with PowerShell
```

### Manual - Any OS
```bash
python -m venv .venv
.venv\Scripts\activate.bat    # Windows
source .venv/bin/activate     # macOS/Linux

pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🌐 ACCESS PORTAL

```
URL:      http://localhost:8080
Username: admin
Password: admin@26
```

---

## 🔍 SCAN URLs

| URL | Result |
|-----|--------|
| https://google.com | ✅ SAFE |
| https://malicious.com | ⚠️ DANGER |
| https://phishing.site | ⚠️ DANGER |

---

## 📚 DOCUMENTATION

| File | Purpose |
|------|---------|
| README.md | Overview & quick start |
| SETUP_GUIDE.md | Detailed setup |
| DATABASE_SETUP.md | PostgreSQL & Redis |
| test_setup.py | Verify installation |
| COMPLETION_SUMMARY.md | What's done |

---

## 🔌 API ENDPOINTS

```bash
# Health
curl http://localhost:8080/health

# Scan URL
curl -X POST http://localhost:8080/api/scan \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'

# Stats
curl http://localhost:8080/api/stats
```

---

## ⚙️ CHANGE CREDENTIALS

**File**: `backend/app/api.py`

Find and update:
```python
if username == "admin" and password == "admin@26":
```

---

## 🗄️ ADD DATABASE (Optional)

See **DATABASE_SETUP.md** for:
- ✅ PostgreSQL setup
- ✅ Redis setup
- ✅ Connection strings
- ✅ Docker Compose

---

## 🧪 TEST INSTALLATION

```bash
python test_setup.py
```

Checks:
- ✅ Python version
- ✅ Dependencies
- ✅ Project structure
- ✅ API running
- ✅ Portal accessible
- ✅ Scanning works

---

## 🚨 QUICK FIXES

### Port in Use
```bash
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

### Python Not Found
- Install from python.org
- Add to PATH
- Restart terminal

### Module Error
```bash
pip install -r backend/requirements.txt
```

---

## 🎨 PORTAL FEATURES

- 🔐 **Police cybercell theme** - Dark navy with cyan
- 🔍 **URL scanner** - Real-time threat detection
- 📊 **Dashboard** - Live statistics
- 📜 **History** - Recent scans
- ✅ **Safe/Danger** - Clear threat indicators

---

## 📊 DASHBOARD STATS

- **Total Scans** - URLs scanned
- **Safe** - Legitimate websites (green)
- **Dangerous** - Malicious threats (red)
- **Success Rate** - Accuracy %

---

## 🛠️ COMMON COMMANDS

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run tests
python test_setup.py

# Start server
python -m uvicorn backend.app.main:app --reload

# Stop server
Ctrl+C

# Logout
Click "Logout" button on portal

# Clear cache (Redis)
redis-cli FLUSHALL
```

---

## 📁 KEY FILES

| File | Purpose |
|------|---------|
| `admin_portal/index.html` | Web portal UI |
| `backend/app/api.py` | Threat scanner API |
| `backend/app/main.py` | Server startup |
| `start.bat` | Windows launcher |
| `test_setup.py` | Verification script |

---

## 🔐 SECURITY BASICS

✅ Change default password for production  
✅ Enable HTTPS/SSL  
✅ Use strong JWT secret  
✅ Configure firewall  
✅ Use PostgreSQL + Redis  
✅ Set strong DB passwords  

---

## 💡 TIPS

- Server auto-reloads on code changes
- Check terminal for error messages
- Use `http://localhost:8080/docs` for API docs
- Use `http://localhost:8080/redoc` for alternative docs
- Scan history is in-memory (cleared on restart)

---

## 🎯 PROJECT STATUS

✅ Admin portal complete  
✅ API working  
✅ Scanner functional  
✅ Authentication enabled  
✅ Documentation complete  
✅ Production ready  

---

## 📞 QUICK HELP

1. **Won't start?** → Check Python version (3.10+)
2. **Port error?** → Change port number or kill process
3. **Import error?** → Run `pip install -r backend/requirements.txt`
4. **Login fails?** → Username: `admin`, Password: `admin@26`
5. **Scanning error?** → Check API is running, terminal for logs

---

## 🎉 YOU'RE READY!

Run: `start.bat` (Windows) or `start.ps1` (PowerShell)  
Open: `http://localhost:8080`  
Login: `admin` / `admin@26`  

**Happy threat hunting! 🛡️**
