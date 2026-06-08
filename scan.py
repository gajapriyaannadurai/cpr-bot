#!/usr/bin/env python3
"""
Inside CPR Scanner — runs in GitHub Actions at 4 PM IST every weekday.
Fetches Chartink screener, computes CPR levels, filters inside-CPR stocks,
classifies setup quality, sends to Telegram, and exports cpr-watchlist.js
for the Fyers bot to auto-load next morning.
"""

import os, re, sys, json, datetime, requests

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

# ── CONFIG ────────────────────────────────────────────────────────────────────
SCREENER_URL = "https://chartink.com/screener/inside-cpr-2062"
SCAN_URL     = "https://chartink.com/screener/scan_results"

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID",   "").strip()

# ── CHARTINK SCAN ─────────────────────────────────────────────────────────────
def chartink_scan():
    if HAS_CLOUDSCRAPER:
        print("[scan] Using cloudscraper to bypass Cloudflare")
        s = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True}
        )
    else:
        print("[scan] Using plain requests")
        s = requests.Session()

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        s.get("https://chartink.com/", timeout=30)
    except Exception:
        pass

    r = s.get(SCREENER_URL, timeout=30)
    r.raise_for_status()
    html = r.text

    csrf = ""
    for pat in [r'<meta name="csrf-token" content="([^"]+)"', r'"csrf-token"\s+content="([^"]+)"']:
        m = re.search(pat, html)
        if m:
            csrf = m.group(1)
            break

    clause = ""
    for pat in [r'"scan_clause"\s*:\s*"([^"]+)"', r"'scan_clause'\s*:\s*'([^']+)'",
                r'id=["\'](scan_clause)["\'][^>]*value=["\']([^"\']+)["\']']:
        m = re.search(pat, html)
        if m:
            clause = m.group(1) if len(m.groups()) == 1 else m.group(2)
            break

    if not csrf:
        raise RuntimeError("Could not get CSRF token from Chartink")
    if not clause:
        raise RuntimeError("Could not get scan_clause from Chartink")

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
        "r1": 2 * pp - l,
        "r2": pp + (h - l),
        "s1": 2 * pp - h,
        "s2": pp - (h - l),
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


# ── EXPORT cpr-watchlist.js ───────────────────────────────────────────────────
def export_watchlist(enriched, scan_date):
    """
    Generates cpr-watchlist.js — Fyers bot auto-downloads this every morning.
    Only exports Good + Fair inside CPR stocks.
    """
    inside = [d for d in enriched if d["inside"] and d["quality"] != "Skip"]

    if not inside:
        print("[export] No inside CPR stocks to export")
        return None

    lines = [
        "/**",
        f" * cpr-watchlist.js — Auto-generated by Inside CPR Scanner",
        f" * Scan date: {scan_date}",
        f" * Total stocks: {len(inside)}",
        " * This file is auto-loaded by the Fyers CPR Bot every morning.",
        " */",
        "",
        "const stocks = [",
    ]

    for d in inside:
        sym    = d["sym"]
        pv     = d["pv"]
        c      = d["c"]
        h      = d["h"]
        l      = d["l"]
        tcp    = round(pv["tc"], 2)
        bcp    = round(pv["bc"], 2)
        r1     = round(pv["r1"], 2)
        s1     = round(pv["s1"], 2)
        pdh    = round(h, 2)
        pdl    = round(l, 2)
        prev_c = round(c, 2)

        lines.append(f"  {{")
        lines.append(f"    sym:       'NSE:{sym}-EQ',")
        lines.append(f"    prevClose: {prev_c},")
        lines.append(f"    openPrice: null,   // filled automatically at 9:15 AM")
        lines.append(f"    tcp:       {tcp},")
        lines.append(f"    bcp:       {bcp},")
        lines.append(f"    r1:        {r1},")
        lines.append(f"    s1:        {s1},")
        lines.append(f"    pdh:       {pdh},")
        lines.append(f"    pdl:       {pdl},")
        lines.append(f"    gapType:   null,   // auto-detected at open")
        lines.append(f"  }},")

    lines.append("];")
    lines.append("")
    lines.append("// Auto-detect gap type from prevClose vs openPrice")
    lines.append("const GAP_THRESHOLD = require('./config').GAP_THRESHOLD_PCT || 0.5;")
    lines.append("stocks.forEach(s => {")
    lines.append("  if (s.gapType === null && s.prevClose && s.openPrice) {")
    lines.append("    const pct = ((s.openPrice - s.prevClose) / s.prevClose) * 100;")
    lines.append("    if (pct >= GAP_THRESHOLD)       s.gapType = 'up';")
    lines.append("    else if (pct <= -GAP_THRESHOLD) s.gapType = 'down';")
    lines.append("  }")
    lines.append("});")
    lines.append("")
    lines.append("module.exports = { stocks };")

    content = "\n".join(lines)

    # Save to repo root — GitHub Actions will commit this
    os.makedirs("exports", exist_ok=True)
    fpath = "exports/cpr-watchlist.js"
    with open(fpath, "w") as f:
        f.write(content)

    print(f"[export] ✅ Exported {len(inside)} stocks to {fpath}")
    return fpath, len(inside), inside


# ── TELEGRAM ──────────────────────────────────────────────────────────────────
def send_telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        print("[telegram] credentials missing — skipping send")
        return False
    chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
    for chunk in chunks:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": chunk, "parse_mode": "HTML",
                  "disable_web_page_preview": "true"},
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
            chg  = f"{d['chg']:+.2f}%"
            line = (
                f"\n<b>{d['sym']}</b>  ₹{d['c']:.2f}  {chg}\n"
                f"  • CPR: TC ₹{d['pv']['tc']:.2f}  BC ₹{d['pv']['bc']:.2f}  Width: {d['w_cls']} ({d['w_pct']:.3f}%)\n"
                f"  • R1: ₹{d['pv']['r1']:.2f} ({d['r1_cls']}) | S1: ₹{d['pv']['s1']:.2f} ({d['s1_cls']})\n"
                f"  • PDH: ₹{d['h']:.2f} | PDL: ₹{d['l']:.2f}\n"
                f"  • % in CPR: <b>{d['pct_in']}%</b>"
            )
            lines.append(line)
        if len(items) > 25:
            lines.append(f"\n<i>… {len(items)-25} more not shown</i>")
        return "\n".join(lines) + "\n"

    if not inside:
        return head + "\n<i>No inside CPR stocks found today.</i>"

    body  = block("Good setups", good, "🟢")
    body += block("Fair setups", fair, "🟡")
    return head + body + "\n<i>Trade safe! 📈</i>"


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("Inside CPR Scanner — starting…")
    ist_now    = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    scanned_at = ist_now.strftime("%a, %d %b %Y  %I:%M %p IST")
    scan_date  = ist_now.strftime("%Y-%m-%d")
    print(f"Time: {scanned_at}")

    try:
        raw = chartink_scan()
    except Exception as e:
        err = f"❌ <b>Scanner Error</b>\n<i>{scanned_at}</i>\n\n<code>{e}</code>"
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

    # ── Export watchlist for Fyers bot ──
    export_result = export_watchlist(enriched, scan_date)

    # ── Send Telegram message ──
    msg = format_message(enriched, scanned_at, len(rows))

    # Add export summary to Telegram message
    if export_result:
        fpath, count, inside = export_result
        syms = ", ".join(d["sym"] for d in inside[:10])
        if len(inside) > 10:
            syms += f" +{len(inside)-10} more"
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 <b>Fyers Bot Watchlist exported!</b>\n"
            f"<i>{count} stocks ready for tomorrow:</i>\n"
            f"<code>{syms}</code>\n"
            f"<i>Fyers bot will auto-load at 9:00 AM ✅</i>"
        )

    # ── Save history snapshot ──
    os.makedirs("history", exist_ok=True)
    fname = f"history/scan_{scan_date}.json"
    with open(fname, "w") as f:
        json.dump({"scanned_at": scanned_at, "total": len(rows), "data": enriched}, f, indent=2)
    print(f"Saved {fname}")

    if send_telegram(msg):
        print("✅ Sent to Telegram")
    else:
        print("⚠️ Telegram send failed")
        print(msg)


if __name__ == "__main__":
    main()
