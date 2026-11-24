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

### 1. Deploy on Railway

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
