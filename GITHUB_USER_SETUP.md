# 👤 GitHub User Configuration Guide

## 🎯 **Current Configuration**

Your current git user settings:
- **Username**: `2dqy`
- **Email**: `info@2dqy.com`

## 🔧 **Option 1: Project-Specific User (Recommended)**

Set a different user **only for this project** without affecting your global git settings:

### **Step 1: Set Project User**
```bash
# Navigate to your project directory (you're already here)
cd /Users/vincentmac-mini/Desktop/Mac\ Mini/coding/i2/translate2.0

# Set username for this project only
git config user.name "YourGitHubUsername"

# Set email for this project only
git config user.email "your-github-email@example.com"
```

### **Step 2: Verify Changes**
```bash
# Check project-specific settings
git config user.name
git config user.email

# See all project settings
git config --list --local | grep user
```

### **Example**
```bash
# Example with a different GitHub account
git config user.name "vincentmac"
git config user.email "vincent@example.com"
```

## 🌍 **Option 2: Change Global User**

If you want to change your git user **for all projects**:

```bash
# Set global username
git config --global user.name "YourGitHubUsername"

# Set global email
git config --global user.email "your-github-email@example.com"
```

## 🔍 **Option 3: Check All Configurations**

See what's configured at different levels:

```bash
# Global settings (affects all projects)
git config --global --list | grep user

# Local settings (this project only)
git config --local --list | grep user

# System settings (all users on this machine)
git config --system --list | grep user
```

## 🚀 **Quick Setup Commands**

### **For Personal GitHub Account**
```bash
git config user.name "YourPersonalUsername"
git config user.email "personal@gmail.com"
```

### **For Work GitHub Account**
```bash
git config user.name "YourWorkUsername"
git config user.email "work@company.com"
```

### **For Organization Account**
```bash
git config user.name "YourOrgUsername"
git config user.email "username@organization.com"
```

## 📋 **Verification Steps**

After setting your user, verify everything is correct:

```bash
# 1. Check user settings
git config user.name
git config user.email

# 2. Make a test commit
git add .
git commit -m "test: verify git user configuration"

# 3. Check commit author
git log --oneline -1 --pretty=format:"%an <%ae>"
```

## 🔄 **Multiple GitHub Accounts Setup**

If you work with multiple GitHub accounts, here's a more advanced setup:

### **1. SSH Keys for Different Accounts**
```bash
# Generate SSH key for this project
ssh-keygen -t ed25519 -C "your-email@example.com" -f ~/.ssh/id_ed25519_project

# Add to SSH agent
ssh-add ~/.ssh/id_ed25519_project
```

### **2. SSH Config**
Create/edit `~/.ssh/config`:
```
# Personal GitHub
Host github.com-personal
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_personal

# Work GitHub
Host github.com-work
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_work

# This project
Host github.com-project
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_project
```

### **3. Set Remote URL**
```bash
# Use specific SSH config
git remote add origin git@github.com-project:username/po-translation-tool.git
```

## ⚠️ **Important Notes**

### **Priority Order**
Git uses this priority for user settings:
1. **Local** (project-specific) - `git config user.name`
2. **Global** (user-specific) - `git config --global user.name`
3. **System** (machine-specific) - `git config --system user.name`

### **Email Matching**
Make sure your email matches:
- Your GitHub account email
- The email you want to appear in commits
- Your SSH key email (if using SSH)

### **Commit History**
- Changing user settings only affects **new commits**
- Existing commits keep their original author
- To change existing commits, you'd need to rewrite history (advanced)

## 🎯 **Recommended Workflow**

For this PO Translation Tool project:

1. **Set project-specific user** (keeps your global settings intact)
2. **Use your preferred GitHub account** for this project
3. **Verify with a test commit**
4. **Push to your GitHub repository**

```bash
# Complete setup example
git config user.name "YourPreferredUsername"
git config user.email "your-preferred-email@example.com"
git add .
git commit -m "feat: initial commit with correct user"
git remote add origin https://github.com/YourUsername/po-translation-tool.git
git push -u origin main
```

## 🔧 **Troubleshooting**

### **If commits show wrong author:**
```bash
# Check what git thinks your user is
git config user.name
git config user.email

# Check the last commit author
git log -1 --pretty=format:"%an <%ae>"
```

### **If you need to change the last commit author:**
```bash
git commit --amend --author="New Name <new-email@example.com>"
```

---

**Choose the option that best fits your needs and run the appropriate commands!** 