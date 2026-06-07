# 📊 Inside CPR Scanner Bot

Automated daily Telegram alerts for inside CPR stocks from your Chartink screener.
Runs every weekday at 4:00 PM IST in GitHub's cloud — no PC needed.

---

## ⚙️ What it does
1. At 4 PM IST Mon–Fri, fetches your Chartink screener
2. Computes CPR (TC/PP/BC), R1, R2, S1, S2 for every stock
3. Strictly filters for inside CPR (BC ≤ close ≤ TC)
4. Classifies CPR width and distance to R1/S1 (Narrow/Medium/Wide)
5. Rates setup quality (Good/Fair/Skip)
6. Sends the full list to your Telegram

---

## 🚀 Setup (one-time, ~5 minutes)

### 1️⃣ Create Telegram Bot
- Open Telegram → search **@BotFather** → send `/newbot`
- Pick a name and username (must end in `bot`)
- **Save the bot token** (looks like `7245678901:AAH...xyz`)
- Search **@userinfobot** → **save your Chat ID** (a number like `123456789`)
- Open your new bot → tap **Start** (important!)

### 2️⃣ Create GitHub Account & Repo
- Go to **github.com** → Sign up (free)
- Click **+** (top right) → **New repository**
- Name: `cpr-bot` → set as **Private** → Create
- On the empty repo page, click "uploading an existing file"
- Drag and drop ALL files from this folder (keep the folder structure):
  ```
  .github/workflows/scan.yml
  scripts/scan.py
  README.md
  ```

### 3️⃣ Add Telegram Secrets
In your repo: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add **two** secrets:

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | your bot token from BotFather |
| `TELEGRAM_CHAT_ID`   | your chat ID from @userinfobot |

### 4️⃣ Enable & Test
- Click the **Actions** tab in your repo
- If prompted, click "I understand my workflows, enable them"
- Click **"Inside CPR Scanner"** in the left sidebar
- Click **Run workflow** → **Run workflow** (green button)
- Wait ~30 seconds → check your Telegram

✅ If you got a message, you're done! From tomorrow it runs automatically at 4 PM IST every weekday.

---

## 🩹 Troubleshooting

### "403 Forbidden" error in Actions log
Chartink uses Cloudflare which sometimes blocks datacenter IPs. The script uses cloudscraper to bypass this, but if you still get 403, message me and I'll add proxy support or switch to a different scraping approach.

### No Telegram message
- Check both secrets are exactly named `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Make sure you tapped **Start** in your bot's chat
- Open Actions tab → click latest run → expand "Run scanner" step → check error

### "0 stocks returned"
Your screener may genuinely have 0 inside CPR stocks today. Check chartink.com manually.

### Workflow didn't run at 4 PM
GitHub free-tier cron can be delayed 5–15 min during peak times — this is normal.

---

## 🛠 Customising

### Change the time
Edit `.github/workflows/scan.yml`:
```yaml
- cron: '30 10 * * 1-5'   # 10:30 UTC = 4:00 PM IST
```

### Change the screener
Edit `scripts/scan.py`:
```python
SCREENER_URL = "https://chartink.com/screener/your-screener-name"
```

---

## 📁 Files
```
cpr-bot/
├── .github/workflows/scan.yml
├── scripts/scan.py
├── history/        (auto-created)
└── README.md
```

## ℹ️ Notes
- GitHub Actions free tier: 2,000 min/month; this uses ~10 min/month
- Repo can be private — no one else sees your screener
