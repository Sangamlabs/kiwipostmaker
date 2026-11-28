# Kiwi Post Maker (Postbot) 🥝

Production-grade Telegram Post Maker & Automated Scheduling Bot built with Python 3.11+, `python-telegram-bot` (v22+), MongoDB (`motor`), and APScheduler.

Supports **Telegram Bot API 10.1–10.5 Rich Messages**, native tables, slideshow carousels, expandable blockquotes, and independent inline & in-body row buttons.

---

## ✨ Features

- **Article Studio (Bot API 10.5)**:
  - Native Rich Messages (`sendRichMessage`) with custom block layouts.
  - Native tables (`InputRichBlockTable`) with borders, zebra striping, and text alignment.
  - Native multi-image slideshow carousels (`InputRichBlockSlideshow`) with navigation arrows (`←`/`→`) and pagination dots (`● ● ●`).
  - Native blockquotes and expandable blockquotes (`InputRichBlockExpandableBlockQuotation`) with optional citations/credit and nested media/tables.
  - Position media anywhere (`top`, `middle`, `bottom`, or inline via `{media}` and `{table}` tags).
- **Dual Buttons Architecture**:
  - Independent **Inline URL Buttons** (`reply_markup`).
  - Independent **In-Body Row Buttons** (`InputRichBlockButtons`) with styles (`primary`, `success`, `danger`).
  - Combine **both** button types on the same post.
- **Automated Queue & Scheduler**:
  - Reliable cron-like scheduling with `APScheduler`.
  - MongoDB atomic lock (`find_one_and_update` state transitions) ensuring zero duplicate deliveries across restarts.
- **Channel Access Verification**:
  - Validates bot administrator privileges and posting permissions before publishing.

---

## 🚀 Deployment

### 1. Deploy on Render (Free Web Service + UptimeRobot 24/7)

Bot mein built-in `aiohttp` keep-alive server (`src/bot/keep_alive.py`) hai jo `0.0.0.0:$PORT` par `/` (`Bot is running`) aur `/health` (`{"status": "ok"}`) serve karta hai.

1. **GitHub par code push karein** (already configured on `Sangamlabs/kiwipostmaker`).
2. **[Render Dashboard](https://dashboard.render.com)** par jayein → **New +** → **Web Service** select karein.
3. Apna GitHub repo (`kiwipostmaker`) connect karein:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python -m src.bot.main`
   - **Instance Type:** `Free`
4. **Environment Variables** add karein:
   - `BOT_TOKEN` = `@BotFather` se mila token
   - `MONGO_URI` = MongoDB Atlas connection URI
   - `DATABASE_NAME` = `postbot`
   - `OWNER_IDS` = Aapki Telegram user ID
   - `LOG_LEVEL` = `INFO`
5. **Create Web Service** par click karein. Deploy hone ke baad aapko URL milega (e.g. `https://kiwi-post-maker.onrender.com`).
6. **UptimeRobot (24/7 Jagaa Rakhne Ke Liye):**
   - [UptimeRobot](https://uptimerobot.com) par free account banayein → **Add New Monitor**.
   - **Monitor Type:** `HTTP(s)`
   - **URL:** `https://<aapka-render-url>.onrender.com/health`
   - **Monitoring Interval:** `5 minutes`
   - Save kar dein! Render free instance ab 15 min inactivity ke baad sleep nahi hoga.

> **Free Tier Limitations & Solutions:**
> - **750 free hours/month:** 1 service 24/7 chalane ke liye ~720–744 hours chahiye hote hain, jo free tier mein cover ho jaata hai (bas multiple services mat chalayein).
> - **Sleep after 15 min:** UptimeRobot ka 5-minute HTTP ping isko jagaa kar rakhta hai.
> - **Data reset on restart:** Render ki disk ephemeral hoti hai, lekin hamara bot **MongoDB Atlas** use karta hai isliye drafts/channels/schedules kabhi delete nahi hote.

---

### 2. Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com)

1. Fork or clone this repository.
2. In Railway, click **New Project** -> **Deploy from GitHub repo**.
3. Select this repository.
4. Add the following **Environment Variables** in Railway Dashboard:
   - `BOT_TOKEN`: Your Telegram Bot API token from [@BotFather](https://t.me/BotFather)
   - `MONGO_URI`: Your MongoDB Atlas connection URI (`mongodb+srv://...`)
   - `DATABASE_NAME`: `postbot`
   - `OWNER_IDS`: Your Telegram user ID (e.g. `8055084559`)
   - `LOG_LEVEL`: `INFO`
5. Railway will automatically detect `railway.json` / `nixpacks.toml` and start the bot worker process.

---

### 2. Deploy on Heroku

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/Sangamlabs/kiwipostmaker)

1. Create a new Heroku app or click the **Deploy to Heroku** button.
2. Configure your Environment Variables (Config Vars):
   - `BOT_TOKEN`
   - `MONGO_URI`
   - `DATABASE_NAME`
   - `OWNER_IDS`
3. Ensure the **`worker`** dyno is turned ON in the Heroku Resources tab:
   ```bash
   heroku ps:scale worker=1
   ```

---

### 3. Deploy with Docker

```bash
# Build and run with docker-compose
docker-compose up -d --build
```

---

### 4. Local Development

```bash
# Clone the repository
git clone https://github.com/Sangamlabs/kiwipostmaker.git
cd kiwipostmaker

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your BOT_TOKEN and MONGO_URI

# Run the bot
python -m src.bot.main
```

---

## 🧪 Testing

Run automated unit and integration tests:

```bash
pytest tests/ -v
```

---

## 📄 License

MIT License. Designed with ❤️ by Sangam Labs.
