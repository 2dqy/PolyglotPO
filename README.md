# 🚀 PO Translation Tool

![PO Translation Tool Interface](images/po-translator-interface.png)

*Professional AI-powered translation tool for CMS and CRM localization workflows*

## ✨ Features

- 🤖 **AI-Powered Translation Engine** - Powered by DeepSeek V3 for high-quality translations
- 🌍 **20+ Languages** - Support for major world languages
- 🎯 **CMS/CRM Optimized** - Specialized for content management systems
- ⚡ **Batch Processing** - Handle multiple files efficiently
- 🔄 **Smart Retry Logic** - Automatic retry for failed translations
- 📊 **Real-time Progress** - Track translation progress live
- 💾 **Easy Download** - Get your translated files instantly

## Prerequisites
- Docker and Docker Compose installed
- Git installed

## 📋 Setup Steps (5 minutes)

### 1. Clone the Repository
```bash
git clone https://github.com/2dqy/po-translator.git
cd po-translator
```

### 2. Create Environment File
```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file and add your DeepSeek API key
nano .env  # or use any text editor
```

**Required in .env file:**
```
DEEPSEEK_API_KEY=your_actual_api_key_here
```

### 3. Start the Application
```bash
# Make the start script executable
chmod +x docker-start.sh

# Start the application
./docker-start.sh
```

### 4. Access the Application
- Open your browser and go to: **http://localhost:8501**
- The PO translation tool should be running!

## 🎯 That's It!

The `docker-start.sh` script will:
- Build the Docker image
- Start the container
- Set up all necessary dependencies
- Launch the web interface

## 📁 What You Need to Know

### File Structure
```
po-translator/
├── docker-start.sh          ← Main script to run
├── .env                     ← Your API keys (create this)
├── .env.example            ← Template for .env
├── docker-compose.yml      ← Docker configuration
├── src/                    ← Application source code
├── input/                  ← Place your .po files here
└── data/                   ← Translation results saved here
```

### Usage
1. **Upload PO files**: Place your `.po` files in the `input/` folder
2. **Access web interface**: Go to http://localhost:8501
3. **Start translation**: Use the web interface to select files and start translation
4. **Download results**: Translated files will be available for download

## 🔧 Troubleshooting

### If Docker fails to start:
```bash
# Stop any running containers
docker-compose down

# Rebuild and restart
docker-compose up --build
```

### If you need to check logs:
```bash
docker-compose logs -f
```

### If you need to stop the application:
```bash
# Stop the containers
docker-compose down
```

## 🆘 Need Help?

- Check the troubleshooting section above
- Review the file structure and usage instructions
- Ensure your DeepSeek API key is correctly set in the .env file

## 🔑 Getting DeepSeek API Key

1. Go to https://platform.deepseek.com/
2. Sign up/Login
3. Go to API Keys section
4. Create a new API key
5. Copy the key to your `.env` file

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

**That's all you need! The entire setup should take less than 5 minutes.** 🎉 