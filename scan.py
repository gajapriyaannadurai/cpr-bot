#!/usr/bin/env python3
"""Inside CPR Scanner."""
import os, re, sys, datetime, time, requests

try:
    import cloudscraper
    HAS_CS = True
except ImportError:
    HAS_CS = False

SCREENER_URL = "https://chartink.com/screener/inside-cpr-2062"
SCAN_URL = "https://chartink.com/screener/scan_results"
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Hardcoded clause since Chartink loads scan_clause via JS for user-saved screeners
SCAN_CLAUSE = "( {cash} ( latest close > [latest cpr bottom] and latest close < [latest cpr top] ) )"


def send_tg(text):
    if not (TG_TOKEN and TG_CHAT):
        print("[tg] missing creds")
        return False
    for chunk in [text[i:i+3800] for i in range(0, len(text), 3800)]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT, "text": chunk, "parse_mode": "HTML",
                      "disable_web_page_preview": "true"}, timeout=15)
            if not r.ok:
                print(f"[tg] error {r.status_code}: {r.text[:200]}")
                return False
        except Exception as e:
            print(f"[tg] exception: {e}")
            return False
    print("[tg] sent ok")
    return True


def make_session():
    if HAS_CS:
        print("[scan] using cloudscraper")
        s = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "darwin", "desktop": True})
    else:
        print("[scan] using plain requests")
        s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    return s


def chartink_scan():
    s = make_session()
    try:
        r0 = s.get("https://chartink.com/", timeout=20)
        print(f"[scan] homepage status: {r0.status_code}")
    except Exception as e:
        print(f"[scan] homepage error: {e}")
    time.sleep(1)
    r = s.get(SCREENER_URL, timeout=30)
    print(f"[scan] screener status: {r.status_code}")
    if r.status_code != 200:
        raise RuntimeError(f"Screener returned {r.status_code}")
    html = r.text

    csrf = ""
    for pat in [r'<meta name="csrf-token" content="([^"]+)"',
                r'"csrf-token"\s+content="([^"]+)"']:
        m = re.search(pat, html)
        if m:
            csrf = m.group(1)
            print(f"[scan] csrf found, len={len(csrf)}")
            break
    if not csrf:
        raise RuntimeError("Could not get CSRF token")

    print(f"[scan] using clause: {SCAN_CLAUSE}")
    r = s.post(SCAN_URL, data={"scan_clause": SCAN_CLAUSE},
               headers={"X-Requested-With": "XMLHttpRequest",
                        "X-CSRF-Token": csrf,
                        "Referer": SCREENER_URL,
                        "Origin": "https://chartink.com",
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
               timeout=30)
    print(f"[scan] scan_results status: {r.status_code}")
    if not r.ok:
        print(f"[scan] response body: {r.text[:500]}")
    r.raise_for_status()
    return r.json()


def calc_cpr(h, l, c):
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {"pp": pp, "bc": bc, "tc": tc, "r1": 2*pp-l, "r2": pp+(h-l), "s1": 2*pp-h, "s2": pp-(h-l)}


def wc(v, p):
    x = (v / p) * 100
    return "Narrow" if x < 0.3 else ("Medium" if x < 0.8 else "Wide")


def dc(v, p):
    x = (v / p) * 100
    return "Narrow" if x < 1.0 else ("Medium" if x < 2.0 else "Wide")


def enrich(rows):
    out = []
    for r in rows:
        sym = r.get("nsecode") or r.get("symbol") or ""
        name = r.get("company_name") or r.get("name") or sym
        try:
            c = float(r.get("close", 0))
            h = float(r.get("high", 0))
            l = float(r.get("low", 0))
            chg = float(r.get("per_chg") or r.get("change_pct") or 0)
        except Exception:
            continue
        if not (c and h and l):
            continue
        pv = calc_cpr(h, l, c)
        w_abs = pv["tc"] - pv["bc"]
        d_r1 = pv["r1"] - pv["tc"]
        d_s1 = pv["bc"] - pv["s1"]
        w_cls = wc(w_abs, c)
        r1_cls = dc(d_r1, c)
        s1_cls = dc(d_s1, c)
        inside = pv["bc"] <= c <= pv["tc"]
        pct_in = round((c - pv["bc"]) / w_abs * 100, 1) if (inside and w_abs > 0) else None
        if w_cls == "Narrow" and r1_cls != "Wide" and s1_cls != "Wide":
            quality = "Good"
        elif w_cls == "Wide":
            quality = "Skip"
        else:
            quality = "Fair"
        out.append({"sym": sym, "name": name, "c": c, "h": h, "l": l, "chg": chg, "pv": pv,
                    "w_abs": w_abs, "d_r1": d_r1, "d_s1": d_s1, "w_cls": w_cls,
                    "r1_cls": r1_cls, "s1_cls": s1_cls, "inside": inside, "pct_in": pct_in,
                    "quality": quality, "w_pct": round((w_abs/c)*100, 3)})
    out.sort(key=lambda x: (not x["inside"], x["w_pct"]))
    return out


def format_msg(enriched, scanned_at, total):
    inside = [d for d in enriched if d["inside"]]
    good = [d for d in inside if d["quality"] == "Good"]
    fair = [d for d in inside if d["quality"] == "Fair"]
    head = (f"<b>Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n"
            f"-------------------------\n"
            f"Scanned: {total}\nInside CPR: {len(inside)}\n"
            f"Good: {len(good)}  Fair: {len(fair)}\n"
            f"-------------------------\n")

    def block(label, items):
        if not items:
            return ""
        lines = [f"\n<b>{label}</b>"]
        for d in items[:25]:
            lines.append(f"\n<b>{d['sym']}</b> Rs {d['c']:.2f} ({d['chg']:+.2f}%)\n"
                         f"  CPR: {d['w_cls']} ({d['w_pct']:.3f}%)\n"
                         f"  TC {d['pv']['tc']:.2f} BC {d['pv']['bc']:.2f}\n"
                         f"  R1 {d['pv']['r1']:.2f} S1 {d['pv']['s1']:.2f}\n"
                         f"  In CPR: <b>{d['pct_in']}%</b>")
        if len(items) > 25:
            lines.append(f"\n<i>... {len(items)-25} more</i>")
        return "\n".join(lines) + "\n"

    if not inside:
        return head + "\n<i>No inside CPR stocks today.</i>"
    return head + block("GOOD SETUPS", good) + block("FAIR SETUPS", fair)


def main():
    print("Starting...")
    print(f"Telegram: token={'yes' if TG_TOKEN else 'NO'} chat={'yes' if TG_CHAT else 'NO'}")
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    scanned_at = ist.strftime("%a, %d %b %Y  %I:%M %p IST")
    print(f"Time: {scanned_at}")
    try:
        raw = chartink_scan()
    except Exception as e:
        err = f"Scanner Error\n{scanned_at}\n\n{str(e)[:1000]}"
        send_tg(err)
        print(err)
        sys.exit(1)
    rows = raw.get("data") or raw.get("stocks") or raw.get("result") or []
    print(f"Got {len(rows)} rows")
    if not rows:
        send_tg(f"Scanner ran. 0 stocks today.\n{scanned_at}")
        return
    enriched = enrich(rows)
    msg = format_msg(enriched, scanned_at, len(rows))
    if send_tg(msg):
        print("done")


if __name__ == "__main__":
    main()
