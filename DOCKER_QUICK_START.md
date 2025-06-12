# 🐳 PO Translation Tool - Docker Quick Start

## ⚡ One-Command Setup

```bash
# 1. Make script executable and start
chmod +x docker-start.sh && ./docker-start.sh start

# 2. Add your DeepSeek API key to .env file
nano .env  # Add: DEEPSEEK_API_KEY=sk-your-key-here

# 3. Restart to apply API key
./docker-start.sh restart
```

**🎉 Done! Access at: http://localhost:8002**

## 📋 Essential Commands

```bash
# Start (runs in background)
./docker-start.sh start

# Stop
./docker-start.sh stop

# Check status
./docker-start.sh status

# View logs
./docker-start.sh logs

# Restart
./docker-start.sh restart
```

## 🔧 Configuration

Edit `.env` file:
```bash
DEEPSEEK_API_KEY=sk-your-actual-api-key-here
PORT=8002
STORAGE_RETENTION_DAYS=1
```

## 📁 Data Persistence

- **Translations**: `./data/storage/`
- **Logs**: `./data/logs/`
- **Auto-cleanup**: Files deleted after 1 day

## ✅ Features

- ✅ **Background Operation**: Runs automatically in Docker
- ✅ **Auto-restart**: Container restarts if it crashes
- ✅ **Health Monitoring**: Built-in health checks
- ✅ **File Cleanup**: Automatic storage management
- ✅ **Web Interface**: Full UI at http://localhost:8002
- ✅ **API Access**: REST API for automation

## 🚨 Troubleshooting

**Container won't start?**
```bash
./docker-start.sh logs  # Check logs
docker --version        # Verify Docker is installed
```

**Port 8002 busy?**
```bash
lsof -i :8002          # Find what's using the port
```

**Need to change port?**
Edit `docker-compose.yml`:
```yaml
ports:
  - "8080:8002"  # Change 8080 to your preferred port
```

## 🔄 System Service (Optional)

**macOS - Auto-start on boot:**
```bash
# Create launch agent
cat > ~/Library/LaunchAgents/com.user.po-translation.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.po-translation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/translate2.0/docker-start.sh</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/translate2.0</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

# Load and start
launchctl load ~/Library/LaunchAgents/com.user.po-translation.plist
```

**Linux - systemd service:**
```bash
# Create service file
sudo tee /etc/systemd/system/po-translation.service << 'EOF'
[Unit]
Description=PO Translation Tool
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/translate2.0
ExecStart=/path/to/translate2.0/docker-start.sh start
ExecStop=/path/to/translate2.0/docker-start.sh stop

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable po-translation.service
sudo systemctl start po-translation.service
```

---

**🌟 Your translation tool is now running 24/7 in the background!** 