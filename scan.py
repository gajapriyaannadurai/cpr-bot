#!/usr/bin/env python3
"""
Inside CPR Scanner
- Fetches Nifty 500 stock list automatically
- Gets previous day OHLC from Yahoo Finance
- Calculates CPR, R1, S1, PDH, PDL
- Filters Inside CPR stocks
- Exports cpr-watchlist.js for Fyers bot
- Sends Telegram alert
"""

import os, json, datetime, time
import requests

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID",   "").strip()

# ── NIFTY 500 STOCK LIST ──────────────────────────────────────────────────────
NIFTY500 = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","SBIN","HINDUNILVR",
    "ITC","LT","BAJFINANCE","HCLTECH","MARUTI","SUNPHARMA","ADANIENT","KOTAKBANK",
    "TITAN","ONGC","NTPC","POWERGRID","ULTRACEMCO","AXISBANK","WIPRO","ADANIPORTS",
    "BAJAJFINSV","JSWSTEEL","TATAMOTORS","TATASTEEL","COALINDIA","NESTLEIND",
    "TECHM","GRASIM","HINDALCO","INDUSINDBK","DRREDDY","DIVISLAB","CIPLA","BPCL",
    "BRITANNIA","EICHERMOT","HEROMOTOCO","APOLLOHOSP","TATACONSUM","BAJAJ-AUTO",
    "SBILIFE","HDFCLIFE","ICICIPRULI","DABUR","PIDILITIND","BERGEPAINT",
    "HAVELLS","MUTHOOTFIN","LUPIN","TORNTPHARM","BIOCON","AUROPHARMA","GLENMARK",
    "CHOLAFIN","MFSL","LICI","DMART","NAUKRI","ZOMATO","PAYTM","POLICYBZR",
    "IRCTC","INDIGO","SPICEJET","TATAPOWER","ADANIGREEN","ADANITRANS","ADANIWILMAR",
    "SIEMENS","ABB","BHEL","BEL","HAL","CONCOR","RAILVIKAS","RVNL","IRFC",
    "PFC","RECLTD","NHPC","SJVN","CANBK","BANKBARODA","PNB","UNIONBANK","INDIANB",
    "FEDERALBNK","IDFCFIRSTB","BANDHANBNK","RBLBANK","YESBANK","KARURVYSYA",
    "SOUTHBANK","DCBBANK","CUB","LAKSHVILAS","UJJIVAN","EQUITAS",
    "MOTHERSON","BOSCHLTD","BHARATFORG","ENDURANCE","SUNDRMFAST","EXIDEIND",
    "AMARARAJA","MINDA","CRAFTSMAN","SUPRAJIT","GABRIEL","JAMNA","WABCO",
    "MRF","APOLLOTYRE","CEATLTD","BALKRISIND","TIINDIA",
    "ASIANPAINT","INDIGO","SUPREMEIND","ASTRAL","FINOLEX","PRINCEPIPE",
    "RELAXO","BATA","METRO","CAMPUS","KANSAINER","AKZOINDIA",
    "PAGEIND","MANYAVAR","ABFRL","TRENT","SHOPERSTOP","VSTIND",
    "MARICO","GODREJCP","EMAMILTD","COLPAL","JYOTHYLAB","GILLETTE",
    "PGHH","VENKEYS","HATSUN","HERITAGE","PARAS","RADICO",
    "EIHOTEL","LEMONTREE","CHALET","INDHOTEL","MAHINDCIE",
    "VOLTAS","BLUESTARCO","WHIRLPOOL","SYMPHONY","CROMPTON","HAVELLS",
    "POLYCAB","FINOLEX","KEI","KPITTECH","LTTS","MPHASIS","COFORGE",
    "PERSISTENT","HEXAWARE","NIITTECH","RAMSYSCORP","ZENSAR","SONACOMS",
    "TATAELXSI","CYIENT","MASTEK","ROUTE","TANLA","INTELLECT","OFSS",
    "FSL","GRAPHITE","GSPL","GUJGASLTD","IGL","MGL","ATGL",
    "CASTROLIND","AEGISLOG","HINDPETRO","IOC","MRPL","GAIL",
    "DEEPAKNTR","GNFC","COROMANDEL","PIIND","BAYER","RALLIS","ASTERDM",
    "FORTIS","MAXHEALTH","NARAYANA","METROPOLIS","THYROCARE","LALPATHLAB",
    "AARTIIND","VINATIORGA","FINEORG","NAVINFLUOR","SUDARSCHEM","NOCIL",
    "ALKYLAMINE","AMARAJABAT","CROMPTON","ORIENTELEC","BATAINDIA",
    "VGUARD","BAJAJELEC","ORIENTCEM","JKCEMENT","RAMCOCEM","HEIDELBERG",
    "DALBHARAT","BIRLACORPN","PRISMJOHNS","AMBUJACEM","ACC","SHREECEM",
    "SAIL","NMDC","MOIL","HINDZINC","VEDL","NATIONALUM","WELCORP",
    "RATNAMANI","APL","JINDALSAW","MAHSEAMLES","ISMT","GHCL",
    "TRIDENT","VARDHMAN","NIITLTD","SYNGENE","SUVEN","SEQUENT",
    "GRANULES","SOLARA","IPCA","ALKEM","NATCOPHARM","AJANTPHARM",
    "IPCALAB","LAURUSLABS","STRIDES","GLAND","ERIS","JUBLPHARMA",
]

# Remove duplicates
NIFTY500 = list(dict.fromkeys(NIFTY500))

# ── YAHOO FINANCE FETCH ───────────────────────────────────────────────────────
def fetch_ohlc(symbols, max_retries=3):
    """Fetch previous day OHLC from Yahoo Finance for all symbols."""
    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    for sym in symbols:
        yahoo_sym = f"{sym}.NS"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}?interval=1d&range=5d"

        for attempt in range(max_retries):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code != 200:
                    time.sleep(0.5)
                    continue

                data = r.json()
                chart = data.get("chart", {})
                result = chart.get("result", [])
                if not result:
                    break

                quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
                timestamps = result[0].get("timestamp", [])

                if not timestamps or len(timestamps) < 2:
                    break

                # Get previous day (second last candle)
                idx = -2
                h = quotes.get("high",  [])[idx]
                l = quotes.get("low",   [])[idx]
                c = quotes.get("close", [])[idx]
                o = quotes.get("open",  [])[idx]

                if h and l and c and o:
                    results[sym] = {"h": round(h,2), "l": round(l,2),
                                    "c": round(c,2), "o": round(o,2)}
                break

            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"[yahoo] ❌ {sym}: {e}")
                time.sleep(0.5)

        time.sleep(0.15)  # rate limit

    return results


# ── CPR CALCULATION ───────────────────────────────────────────────────────────
def calc_cpr(h, l, c):
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {
        "pp": pp, "bc": bc, "tc": tc,
        "r1": 2 * pp - l,
        "r2": pp + (h - l),
        "s1": 2 * pp - h,
        "s2": pp - (h - l),
    }

def width_pct(tc, bc, price):
    return ((tc - bc) / price) * 100

def classify(enriched):
    results = []
    for sym, d in enriched.items():
        h, l, c = d["h"], d["l"], d["c"]
        pv = calc_cpr(h, l, c)
        w_abs = pv["tc"] - pv["bc"]
        w_pct = width_pct(pv["tc"], pv["bc"], c)

        # Inside CPR: close is between BC and TC
        inside = pv["bc"] <= c <= pv["tc"]
        pct_in = round((c - pv["bc"]) / w_abs * 100, 1) if (inside and w_abs > 0) else None

        # Quality classification
        if w_pct < 0.3:
            quality = "Good"
        elif w_pct < 0.8:
            quality = "Fair"
        else:
            quality = "Skip"

        if inside and quality != "Skip":
            results.append({
                "sym":     sym,
                "c":       c,
                "h":       h,
                "l":       l,
                "pv":      pv,
                "w_pct":   round(w_pct, 3),
                "quality": quality,
                "pct_in":  pct_in,
            })

    results.sort(key=lambda x: (x["quality"] != "Good", x["w_pct"]))
    return results


# ── EXPORT WATCHLIST ──────────────────────────────────────────────────────────
def export_watchlist(stocks, scan_date):
    if not stocks:
        print("[export] No stocks to export")
        return 0

    lines = [
        "/**",
        f" * cpr-watchlist.js — Auto-generated by Inside CPR Scanner",
        f" * Scan date: {scan_date}",
        f" * Total stocks: {len(stocks)}",
        " */",
        "",
        "const stocks = [",
    ]

    for d in stocks:
        sym = d["sym"]
        pv  = d["pv"]
        lines += [
            f"  {{",
            f"    sym:       'NSE:{sym}-EQ',",
            f"    prevClose: {d['c']},",
            f"    openPrice: null,",
            f"    tcp:       {round(pv['tc'],2)},",
            f"    bcp:       {round(pv['bc'],2)},",
            f"    r1:        {round(pv['r1'],2)},",
            f"    s1:        {round(pv['s1'],2)},",
            f"    pdh:       {d['h']},",
            f"    pdl:       {d['l']},",
            f"    gapType:   null,",
            f"  }},",
        ]

    lines += [
        "];",
        "",
        "const GAP_THRESHOLD = require('./config').GAP_THRESHOLD_PCT || 0.5;",
        "stocks.forEach(s => {",
        "  if (s.gapType === null && s.prevClose && s.openPrice) {",
        "    const pct = ((s.openPrice - s.prevClose) / s.prevClose) * 100;",
        "    if (pct >= GAP_THRESHOLD)       s.gapType = 'up';",
        "    else if (pct <= -GAP_THRESHOLD) s.gapType = 'down';",
        "  }",
        "});",
        "",
        "module.exports = { stocks };",
    ]

    os.makedirs("exports", exist_ok=True)
    with open("exports/cpr-watchlist.js", "w") as f:
        f.write("\n".join(lines))

    print(f"[export] ✅ Exported {len(stocks)} stocks to exports/cpr-watchlist.js")
    return len(stocks)


# ── TELEGRAM ──────────────────────────────────────────────────────────────────
def send_telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        print("[telegram] No credentials — skipping")
        return
    chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
    for chunk in chunks:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT, "text": chunk,
                      "parse_mode": "HTML", "disable_web_page_preview": "true"},
                timeout=15,
            )
        except Exception as e:
            print(f"[telegram] Error: {e}")


# ── FORMAT MESSAGE ────────────────────────────────────────────────────────────
def format_message(stocks, scanned_at, total_fetched, exported):
    good = [s for s in stocks if s["quality"] == "Good"]
    fair = [s for s in stocks if s["quality"] == "Fair"]

    head = (
        f"<b>📊 Inside CPR Scanner</b>\n"
        f"<i>{scanned_at}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>Nifty 500 scanned:</b> {total_fetched}\n"
        f"✅ <b>Inside CPR:</b>        {len(stocks)}\n"
        f"🟢 <b>Good setups:</b>      {len(good)}\n"
        f"🟡 <b>Fair setups:</b>      {len(fair)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    def block(label, items, emoji):
        if not items: return ""
        lines = [f"\n<b>{emoji} {label} ({len(items)})</b>"]
        for d in items[:20]:
            lines.append(
                f"\n<b>{d['sym']}</b>  ₹{d['c']:.2f}\n"
                f"  CPR: TC ₹{d['pv']['tc']:.2f}  BC ₹{d['pv']['bc']:.2f}  ({d['w_pct']:.3f}%)\n"
                f"  R1: ₹{d['pv']['r1']:.2f}  S1: ₹{d['pv']['s1']:.2f}\n"
                f"  PDH: ₹{d['h']:.2f}  PDL: ₹{d['l']:.2f}\n"
                f"  % in CPR: <b>{d['pct_in']}%</b>"
            )
        if len(items) > 20:
            lines.append(f"<i>+{len(items)-20} more</i>")
        return "\n".join(lines) + "\n"

    body  = block("GOOD SETUPS", good, "🟢")
    body += block("FAIR SETUPS", fair, "🟡")

    if not stocks:
        body = "\n<i>No inside CPR stocks found today.</i>"

    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📥 <b>Fyers Bot Watchlist exported!</b>\n"
        f"<i>{exported} stocks ready for tomorrow</i>\n"
        f"<i>Fyers bot auto-loads at 9:00 AM ✅</i>\n"
        f"<i>Trade safe! 📈</i>"
    )

    return head + body + footer


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("Inside CPR Scanner — starting...")
    ist_now    = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    scanned_at = ist_now.strftime("%a, %d %b %Y  %I:%M %p IST")
    scan_date  = ist_now.strftime("%Y-%m-%d")
    print(f"Time: {scanned_at}")
    print(f"Fetching OHLC for {len(NIFTY500)} Nifty 500 stocks from Yahoo Finance...")

    ohlc = fetch_ohlc(NIFTY500)
    print(f"Fetched: {len(ohlc)} stocks")

    if not ohlc:
        msg = f"❌ <b>CPR Scanner Error</b>\n<i>{scanned_at}</i>\n\nCould not fetch any data from Yahoo Finance."
        send_telegram(msg)
        return

    stocks = classify(ohlc)
    print(f"Inside CPR stocks: {len(stocks)}")

    exported = export_watchlist(stocks, scan_date)

    os.makedirs("history", exist_ok=True)
    with open(f"history/scan_{scan_date}.json", "w") as f:
        json.dump({"scanned_at": scanned_at, "total": len(ohlc), "stocks": stocks}, f, indent=2)

    msg = format_message(stocks, scanned_at, len(ohlc), exported)
    send_telegram(msg)
    print("✅ Done!")

if __name__ == "__main__":
    main()
