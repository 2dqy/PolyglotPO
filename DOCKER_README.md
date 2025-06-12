# PO Translation Tool - Docker Deployment Guide

This guide helps you deploy the PO Translation Tool using Docker for easy background operation on your local machine.

## 🚀 Quick Start

### Prerequisites

- **Docker**: Install from [docker.com](https://www.docker.com/get-started)
- **Docker Compose**: Usually included with Docker Desktop
- **DeepSeek API Key**: Get from [DeepSeek Platform](https://platform.deepseek.com/)

### 1. Clone and Setup

```bash
# Navigate to your project directory
cd /path/to/translate2.0

# Make the startup script executable
chmod +x docker-start.sh

# Start the application (will create .env template if needed)
./docker-start.sh start
```

### 2. Configure API Key

Edit the `.env` file and add your DeepSeek API key:

```bash
# Edit .env file
nano .env

# Add your API key
DEEPSEEK_API_KEY=sk-your-actual-api-key-here
```

### 3. Start the Application

```bash
# Start the application
./docker-start.sh start
```

The application will be available at: **http://localhost:8002**

## 📋 Management Commands

### Basic Operations

```bash
# Start the application
./docker-start.sh start

# Stop the application
./docker-start.sh stop

# Restart the application
./docker-start.sh restart

# Check application status
./docker-start.sh status

# View real-time logs
./docker-start.sh logs
```

### Advanced Operations

```bash
# Rebuild Docker image (after code changes)
./docker-start.sh build

# Clean up all data (destructive - removes all translations)
./docker-start.sh cleanup
```

## 🐳 Manual Docker Commands

If you prefer using Docker commands directly:

```bash
# Build and start
docker-compose up -d --build

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Rebuild image
docker-compose build --no-cache
```

## 📁 Directory Structure

```
translate2.0/
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose configuration
├── docker-start.sh           # Management script
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── .dockerignore            # Docker build exclusions
├── src/                     # Application source code
└── data/                    # Persistent data (created automatically)
    ├── storage/             # File storage
    │   ├── uploads/         # Uploaded PO files
    │   ├── processed/       # Translated files
    │   └── downloads/       # Download-ready files
    └── logs/               # Application logs
```

## ⚙️ Configuration

### Environment Variables

Edit `.env` file to customize:

```bash
# DeepSeek API Configuration
DEEPSEEK_API_KEY=your-api-key-here

# Server Configuration
HOST=0.0.0.0
PORT=8002
DEBUG=false

# Storage Configuration
STORAGE_RETENTION_DAYS=1        # Auto-cleanup after 1 day
CLEANUP_INTERVAL=3600           # Cleanup check every hour

# Logging
LOG_LEVEL=INFO
```

### Port Configuration

To change the port (e.g., to 8080):

1. Edit `docker-compose.yml`:
   ```yaml
   ports:
     - "8080:8002"  # External:Internal
   ```

2. Edit `.env`:
   ```bash
   PORT=8002  # Keep internal port as 8002
   ```

## 🔧 Troubleshooting

### Application Won't Start

1. **Check Docker is running**:
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Check logs**:
   ```bash
   ./docker-start.sh logs
   ```

3. **Verify API key**:
   ```bash
   cat .env | grep DEEPSEEK_API_KEY
   ```

### Port Already in Use

If port 8002 is busy:

1. **Find what's using the port**:
   ```bash
   lsof -i :8002
   ```

2. **Stop the conflicting service** or **change port** in `docker-compose.yml`

### Permission Issues

If you get permission errors:

```bash
# Fix ownership of data directory
sudo chown -R $USER:$USER data/

# Or run with sudo (not recommended)
sudo ./docker-start.sh start
```

### Container Health Check Failing

```bash
# Check if application is responding
curl http://localhost:8002/health

# Check container status
docker-compose ps

# Restart with fresh build
./docker-start.sh stop
./docker-start.sh build
./docker-start.sh start
```

## 🔄 Background Operation

### Running as System Service (Linux/macOS)

To run the translation tool as a system service that starts automatically:

#### Option 1: Using systemd (Linux)

Create `/etc/systemd/system/po-translation.service`:

```ini
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
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable po-translation.service
sudo systemctl start po-translation.service
```

#### Option 2: Using launchd (macOS)

Create `~/Library/LaunchAgents/com.user.po-translation.plist`:

```xml
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
```

Load and start:
```bash
launchctl load ~/Library/LaunchAgents/com.user.po-translation.plist
launchctl start com.user.po-translation
```

### Auto-restart Configuration

The Docker Compose configuration includes `restart: unless-stopped`, which means:

- ✅ Container restarts automatically if it crashes
- ✅ Container starts automatically when Docker starts
- ✅ Container won't restart if manually stopped
- ✅ Survives system reboots (if Docker starts automatically)

## 📊 Monitoring

### Health Checks

The application includes built-in health monitoring:

```bash
# Check application health
curl http://localhost:8002/health

# Expected response
{"status": "healthy", "timestamp": "2025-06-12T04:20:00.000000"}
```

### Log Monitoring

```bash
# Real-time logs
./docker-start.sh logs

# Last 100 lines
docker-compose logs --tail=100

# Logs for specific timeframe
docker-compose logs --since="2h"
```

### Resource Usage

```bash
# Container resource usage
docker stats po-translation-tool

# Disk usage
du -sh data/
```

## 🔒 Security Considerations

1. **API Key Security**: Keep your `.env` file secure and never commit it to version control
2. **Network Access**: The application only binds to localhost by default
3. **File Permissions**: The container runs as a non-root user for security
4. **Data Persistence**: Translation data is stored in `./data/` directory

## 🚀 Production Deployment

For production deployment, consider:

1. **Reverse Proxy**: Use nginx or Apache as a reverse proxy
2. **SSL/TLS**: Add HTTPS encryption
3. **Monitoring**: Implement proper logging and monitoring
4. **Backup**: Regular backup of the `data/` directory
5. **Resource Limits**: Set memory and CPU limits in docker-compose.yml

Example production docker-compose.yml additions:

```yaml
services:
  translation-tool:
    # ... existing configuration ...
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 📞 Support

If you encounter issues:

1. Check the logs: `./docker-start.sh logs`
2. Verify configuration: `./docker-start.sh status`
3. Try rebuilding: `./docker-start.sh build`
4. Check Docker installation: `docker --version`

---

**Happy Translating! 🌍✨** 