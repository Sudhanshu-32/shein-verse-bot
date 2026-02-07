# Shein Verse Bot for Railway

A complete bot to track Shein Verse Men's section stock with anti-detection measures, deployed on Railway.

## Features
- ✅ **Men's Only** - Tracks only Men's section products
- ✅ **Anti-Detection** - Advanced techniques to avoid blocking
- ✅ **Telegram Alerts** - Instant notifications with images
- ✅ **Size & Quantity** - Shows available sizes and stock
- ✅ **App Links** - Direct links to open in SHEIN app
- ✅ **Railway Ready** - Deploys easily on Railway.app
- ✅ **24/7 Monitoring** - Runs continuously
- ✅ **SQLite Database** - Tracks product history

## Quick Deployment

### 1. Create Telegram Bot
1. Message **@BotFather** on Telegram
2. Send `/newbot` and follow instructions
3. Copy the **bot token**
4. Message **@userinfobot** to get your **chat ID**

### 2. Deploy on Railway
```bash
# Create new repository
git init
git add .
git commit -m "Initial commit"

# Push to GitHub
git remote add origin https://github.com/yourusername/shein-bot.git
git push -u origin main

# Deploy on Railway
# 1. Go to railway.app
# 2. Create New Project
# 3. Deploy from GitHub repo
# 4. Add environment variables
