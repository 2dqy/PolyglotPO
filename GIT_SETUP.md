# 📁 Git Setup & .gitignore Guide

## 🎯 **Overview**

This document explains the git configuration for the PO Translation Tool project, including what files are tracked and ignored.

## 📋 **What's Included in Git**

### ✅ **Source Code**
- `src/` - All Python application code
- `requirements.txt` - Python dependencies
- Configuration files (`config.py`)

### ✅ **Docker Configuration**
- `Dockerfile` - Container build instructions
- `docker-compose.yml` - Service orchestration
- `docker-start.sh` - Management script
- `.dockerignore` - Docker build exclusions

### ✅ **Documentation**
- `README.md` files
- `DOCKER_README.md` - Docker setup guide
- `DOCKER_QUICK_START.md` - Quick reference
- `DEEPSEEK_V3_UPGRADE.md` - Upgrade documentation

### ✅ **Configuration Templates**
- `.env.example` - Environment variable template
- Essential test files

## 🚫 **What's Ignored by Git**

### 🔒 **Security & Secrets**
- `.env` - Environment variables with API keys
- `*.key`, `*.pem` - Certificate files
- `api_keys.txt`, `secrets.json` - Credential files

### 🐍 **Python Generated Files**
- `__pycache__/` - Compiled Python bytecode
- `*.pyc`, `*.pyo` - Python cache files
- `venv/`, `.venv/` - Virtual environments
- `*.egg-info/` - Package metadata

### 📁 **Application Data**
- `data/storage/` - Uploaded and processed files
- `data/logs/` - Application logs
- `*.log` - Log files
- `uploads/`, `downloads/` - File storage directories

### 🔧 **Development Files**
- `.vscode/`, `.idea/` - IDE configurations
- `*.swp`, `*.tmp` - Temporary files
- `.DS_Store` - macOS system files
- `Thumbs.db` - Windows system files

### 📦 **Build & Distribution**
- `build/`, `dist/` - Build artifacts
- `*.tar.gz`, `*.zip` - Archive files
- `node_modules/` - Node.js dependencies (if any)

## 🚀 **Quick Setup**

### 1. **Initialize Repository**
```bash
git init
git add .
git commit -m "Initial commit: PO Translation Tool with DeepSeek V3"
```

### 2. **Set Up Environment**
```bash
# Copy environment template
cp .env.example .env

# Edit with your API key
nano .env  # or your preferred editor
```

### 3. **Verify .gitignore**
```bash
# Check what files are tracked
git status

# Should NOT see:
# - .env file
# - __pycache__ directories
# - data/storage/ contents
# - venv/ directory
```

## 🔍 **File Structure Overview**

```
translate2.0/
├── .gitignore              # Git ignore rules
├── .env.example           # Environment template
├── docker-compose.yml     # Docker services
├── Dockerfile            # Container build
├── requirements.txt      # Python deps
├── src/                  # Source code (tracked)
│   └── app/
├── data/                 # Data directories
│   ├── storage/         # Ignored (uploads/downloads)
│   └── logs/           # Ignored (log files)
├── venv/               # Ignored (virtual env)
└── docs/              # Documentation (tracked)
```

## ⚠️ **Important Notes**

### **Never Commit These**
- `.env` files with real API keys
- `data/storage/` with user uploads
- `__pycache__/` directories
- Virtual environment folders

### **Always Commit These**
- Source code changes
- Configuration updates
- Documentation updates
- Docker configuration changes

### **Before Committing**
```bash
# Check what you're about to commit
git status
git diff --cached

# Make sure no secrets are included
grep -r "sk-" . --exclude-dir=.git --exclude-dir=venv
```

## 🔄 **Common Git Workflows**

### **Adding New Features**
```bash
git add src/
git commit -m "feat: add new translation feature"
```

### **Updating Documentation**
```bash
git add *.md
git commit -m "docs: update setup instructions"
```

### **Configuration Changes**
```bash
git add docker-compose.yml Dockerfile requirements.txt
git commit -m "config: update Docker setup"
```

### **Emergency: Remove Accidentally Committed Secrets**
```bash
# Remove from staging
git reset HEAD .env

# Remove from history (if already committed)
git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch .env' \
--prune-empty --tag-name-filter cat -- --all
```

## 📊 **Git Status Examples**

### ✅ **Good Status (Clean)**
```
On branch main
nothing to commit, working tree clean
```

### ✅ **Good Status (New Changes)**
```
Changes to be committed:
  modified:   src/app/core/deepseek_client.py
  modified:   requirements.txt
```

### ❌ **Bad Status (Secrets Exposed)**
```
Changes to be committed:
  new file:   .env                    # ❌ Contains API keys!
  new file:   data/storage/secret.po  # ❌ User data!
```

---

**Remember**: The `.gitignore` protects you from accidentally committing sensitive data, but always double-check before pushing to remote repositories! 