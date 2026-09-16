"""
Test script to verify GuardAIN setup
Run: python test_setup.py
"""
import subprocess
import sys
import time
import requests
import os
from pathlib import Path

def test_python_version():
    """Check Python version"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"✅ Python {version.major}.{version.minor} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} - Need 3.10+")
        return False


def test_dependencies():
    """Check if required packages are installed"""
    print("\n🔍 Checking dependencies...")
    required = ['fastapi', 'uvicorn', 'pydantic']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg} - installed")
        except ImportError:
            print(f"❌ {pkg} - missing")
            missing.append(pkg)
    
    return len(missing) == 0


def test_project_structure():
    """Verify project structure"""
    print("\n🔍 Verifying project structure...")
    required_paths = [
        'admin_portal/index.html',
        'backend/app/main.py',
        'backend/app/api.py',
        'backend/requirements.txt',
        'docker-compose.yml',
    ]
    
    all_exist = True
    for path in required_paths:
        full_path = Path(path)
        if full_path.exists():
            print(f"✅ {path}")
        else:
            print(f"❌ {path} - NOT FOUND")
            all_exist = False
    
    return all_exist


def test_api_endpoint():
    """Test API health endpoint"""
    print("\n🔍 Testing API endpoint...")
    try:
        response = requests.get('http://localhost:8080/health', timeout=3)
        if response.status_code == 200:
            print(f"✅ API is responding")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ API responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to API (is it running?)")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_admin_portal():
    """Test admin portal is served"""
    print("\n🔍 Testing admin portal...")
    try:
        response = requests.get('http://localhost:8080/', timeout=3)
        if response.status_code == 200 and 'GuardAIN' in response.text:
            print(f"✅ Admin portal is accessible")
            return True
        else:
            print(f"❌ Admin portal not responding correctly")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_scan_api():
    """Test URL scanning endpoint"""
    print("\n🔍 Testing URL scanning API...")
    try:
        payload = {"url": "https://google.com"}
        response = requests.post('http://localhost:8080/api/scan', json=payload, timeout=3)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Scanning API works")
            print(f"   URL: {result['url']}")
            print(f"   Status: {result['status']}")
            print(f"   Threat Score: {result['threat_score']}/10")
            return True
        else:
            print(f"❌ API responded with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("  GuardAIN - Setup Verification")
    print("="*50)
    
    results = {
        "Python Version": test_python_version(),
        "Dependencies": test_dependencies(),
        "Project Structure": test_project_structure(),
    }
    
    print("\n" + "="*50)
    print("  Offline Tests Summary")
    print("="*50)
    
    all_offline_ok = all(results.values())
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test}: {status}")
    
    if not all_offline_ok:
        print("\n❌ Setup incomplete. Please follow SETUP_GUIDE.md")
        return 1
    
    # Online tests
    print("\n" + "="*50)
    print("  Online Tests (requires API running)")
    print("="*50)
    print("\n⏳ Make sure API is running: python -m uvicorn backend.app.main:app --port 8080")
    print("   Press Enter once API is running...")
    input()
    
    online_results = {
        "API Health": test_api_endpoint(),
        "Admin Portal": test_admin_portal(),
        "URL Scanning": test_scan_api(),
    }
    
    print("\n" + "="*50)
    print("  Online Tests Summary")
    print("="*50)
    
    for test, result in online_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test}: {status}")
    
    all_ok = all(online_results.values())
    
    print("\n" + "="*50)
    if all_ok:
        print("✅ ALL TESTS PASSED - GuardAIN is ready!")
        print("\n🌐 Access portal at: http://localhost:8080")
        print("🔐 Login with: admin / admin@26")
    else:
        print("❌ Some tests failed. Check errors above.")
    print("="*50 + "\n")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
