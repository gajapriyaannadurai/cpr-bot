#!/usr/bin/env python3
"""
Inside CPR Scanner — runs in GitHub Actions at 4 PM IST every weekday.
Fetches the Chartink screener, computes CPR levels, filters strict
inside-CPR stocks, classifies setup quality, and sends to Telegram.
"""

import os
import re
import sys
import json
import datetime
import requests

# Optional: cloudscraper bypasses Cloudflare bot protection. Install via:
#   pip install cloudscraper
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# ── CONFIG ────────────────────────────────────────────────────────────────────
SCREENER_URL = "https://chartink.com/screener/inside-cpr-2062"
SCAN_URL     = "https://chartink.com/screener/scan_results"

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# ── CHARTINK SCAN ─────────────────────────────────────────────────────────────
def chartink_scan():
    # Use cloudscraper if available to bypass Cloudflare bot protection
    if HAS_CLOUDSCRAPER:
        print("[scan] Using cloudscraper to bypass Cloudflare")
        s = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True}
        )
    else:
        print("[scan] cloudscraper not available, using plain requests")
        s = requests.Session()

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    })

    # 1. Warm up — visit homepage first to look like a real browser
    try:
        s.get("https://chartink.com/", timeout=30)
    except Exception:
        pass

    # 2. Fetch the screener page
    r = s.get(SCREENER_URL, timeout=30)
    r.raise_for_status()
    html = r.text

    csrf = ""
    for pat in [
        r'<meta name="csrf-token" content="([^"]+)"',
        r'"csrf-token"\s+content="([^"]+)"',
    ]:
        m = re.search(pat, html)
        if m:
            csrf = m.group(1)
            break

    clause = ""
    for pat in [
        r'"scan_clause"\s*:\s*"([^"]+)"',
        r"'scan_clause'\s*:\s*'([^']+)'",
        r'id=["\']scan_clause["\'][^>]*value=["\']([^"\']+)["\']',
        r'name=["\']scan_clause["\'][^>]*value=["\']([^"\']+)["\']',
    ]:
        m = re.search(pat, html)
        if m:
            clause = m.group(1)
            break

    if not csrf:
        raise RuntimeError("Could not get CSRF token from Chartink")
    if not clause:
        raise RuntimeError("Could not get scan_clause from Chartink")

    # 2. POST to scan endpoint
    r = s.post(
        SCAN_URL,
        data={"scan_clause": clause},
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRF-Token": csrf,
            "Referer": SCREENER_URL,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://chartink.com",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── CPR MATH ──────────────────────────────────────────────────────────────────
def calc_cpr(h, l, c):
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {
        "pp": pp, "bc": bc, "tc": tc,
        "r1": 2 * pp - l, "r2": pp + (h - l),
        "s1": 2 * pp - h, "s2": pp - (h - l),
    }

def width_class(v, price):
    p = (v / price) * 100
    return "Narrow" if p < 0.3 else ("Medium" if p < 0.8 else "Wide")

def dist_class(v, price):
    p = (v / price) * 100
    return "Narrow" if p < 1.0 else ("Medium" if p < 2.0 else "Wide")


def enrich(rows):
    out = []
    for r in rows:
        sym  = r.get("nsecode") or r.get("symbol") or ""
        name = r.get("company_name") or r.get("name") or sym
        try:
            c   = float(r.get("close", 0))
            h   = float(r.get("high",  0))
            l   = float(r.get("low",   0))
            chg = float(r.get("per_chg") or r.get("change_pct") or 0)
        except (ValueError, TypeError):
            continue
        if not (c and h and l):
            continue

        pv    = calc_cpr(h, l, c)
        w_abs = pv["tc"] - pv["bc"]
        d_r1  = pv["r1"] - pv["tc"]
        d_s1  = pv["bc"] - pv["s1"]

        w_cls  = width_class(w_abs, c)
        r1_cls = dist_class(d_r1, c)
        s1_cls = dist_class(d_s1, c)

        inside = pv["bc"] <= c <= pv["tc"]
        pct_in = round((c - pv["bc"]) / w_abs * 100, 1) if (inside and w_abs > 0) else None

        if w_cls == "Narrow" and r1_cls != "Wide" and s1_cls != "Wide":
            quality = "Good"
        elif w_cls == "Wide":
            quality = "Skip"
        else:
            quality = "Fair"

        out.append({
            "sym": sym, "name": name, "c": c, "h": h, "l": l, "chg": chg,
            "pv": pv, "w_abs": w_abs, "d_r1": d_r1, "d_s1": d_s1,
            "w_cls": w_cls, "r1_cls": r1_cls, "s1_cls": s1_cls,
            "inside": inside, "pct_in": pct_in, "quality": quality,
            "w_pct": round((w_abs / c) * 100, 3),
        })

    out.sort(key=lambda x: (not x["inside"], x["w_pct"]))
    return out


# ── TELEGRAM ──────────────────────────────────────────────────────────────────
def send_telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        print("[telegram] credentials missing — skipping send")
        return False
    # Telegram message limit: 4096 chars per message
    chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={
                "chat_id":    TG_CHAT,
                "text":       chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            },
            timeout=15,
        )
        if not r.ok:
            print(f"[telegram] error: {r.status_code} {r.text}")
            return False
    return True


# ── FORMAT MESSAGE ────────────────────────────────────────────────────────────
def format_message(enriched, scanned_at, total):
    inside = [d for d in enriched if d["inside"]]
    good   = [d for d in inside if d["quality"] == "Good"]
    fair   = [d for d in inside if d["quality"] == "Fair"]

    head = (
        f"<b>📊 Inside CPR Scanner</b>\n"
        f"<i>{scanned_at}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>Total scanned:</b>   {total}\n"
        f"✅ <b>Inside CPR:</b>      {len(inside)}\n"
        f"🟢 <b>Good setups:</b>    {len(good)}\n"
        f"🟡 <b>Fair setups:</b>    {len(fair)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    def block(label, items, emoji):
        if not items:
            return ""
        lines = [f"\n<b>{emoji} {label.upper()} ({len(items)})</b>"]
        for d in items[:25]:
            chg = f"{d['chg']:+.2f}%"
            line = (
                f"\n<b>{d['sym']}</b>  ₹{d['c']:.2f}  {chg}\n"
                f"  • CPR width: {d['w_cls']} ({d['w_pct']:.3f}%)\n"
                f"  • TC: ₹{d['pv']['tc']:.2f}  PP: ₹{d['pv']['pp']:.2f}  BC: ₹{d['pv']['bc']:.2f}\n"
                f"  • R1: ₹{d['pv']['r1']:.2f} ({d['r1_cls']}) | S1: ₹{d['pv']['s1']:.2f} ({d['s1_cls']})\n"
                f"  • % in CPR: <b>{d['pct_in']}%</b>"
            )
            lines.append(line)
        if len(items) > 25:
            lines.append(f"\n<i>… {len(items)-25} more not shown</i>")
        return "\n".join(lines) + "\n"

    if not inside:
        return head + "\n<i>No inside CPR stocks found today.</i>"

    body = block("Good setups", good, "🟢")
    body += block("Fair setups", fair, "🟡")
    return head + body + "\n<i>Trade safe! 📈</i>"


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("Inside CPR Scanner — starting…")
    ist_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    scanned_at = ist_now.strftime("%a, %d %b %Y  %I:%M %p IST")
    print(f"Time: {scanned_at}")

    try:
        raw = chartink_scan()
    except Exception as e:
        err = f"❌ <b>Scanner Error</b>\n<i>{scanned_at}</i>\n\nCould not fetch from Chartink:\n<code>{e}</code>"
        print(err)
        send_telegram(err)
        sys.exit(1)

    rows = raw.get("data") or raw.get("stocks") or raw.get("result") or []
    print(f"Got {len(rows)} rows from Chartink")

    if not rows:
        msg = (
            f"⚠️ <b>Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n\n"
            f"Chartink returned 0 stocks.\nResponse keys: {list(raw.keys())}"
        )
        send_telegram(msg)
        print("No stocks returned.")
        return

    enriched = enrich(rows)
    msg = format_message(enriched, scanned_at, len(rows))

    # Save snapshot
    os.makedirs("history", exist_ok=True)
    fname = f"history/scan_{ist_now.strftime('%Y-%m-%d')}.json"
    with open(fname, "w") as f:
        json.dump({"scanned_at": scanned_at, "total": len(rows), "data": enriched}, f, indent=2)
    print(f"Saved {fname}")

    if send_telegram(msg):
        print("✅ Sent to Telegram")
    else:
        print("⚠️ Telegram send failed (check secrets)")
        print(msg)


if __name__ == "__main__":
    main()
