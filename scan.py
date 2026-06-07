#!/usr/bin/env python3
"""Inside CPR Scanner — fetches NSE data via yfinance, sends to Telegram."""
import os, sys, datetime, requests
import yfinance as yf
import pandas as pd

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Nifty 200 — the most actively traded NSE stocks
STOCKS = """
RELIANCE TCS HDFCBANK BHARTIARTL ICICIBANK INFY SBIN HINDUNILVR ITC LT KOTAKBANK
LICI BAJFINANCE HCLTECH MARUTI SUNPHARMA AXISBANK ADANIENT ONGC NTPC TATAMOTORS
DMART ULTRACEMCO TITAN ASIANPAINT WIPRO BAJAJFINSV NESTLEIND M&M COALINDIA POWERGRID
ADANIPORTS HAL JSWSTEEL TATASTEEL BAJAJ-AUTO TRENT IOC ADANIPOWER ADANIGREEN HINDALCO
SIEMENS PIDILITIND VBL DLF GRASIM TECHM BEL HDFCLIFE BRITANNIA CIPLA APOLLOHOSP
SBILIFE IRFC INDIGO EICHERMOT DRREDDY ABB DIVISLAB INDUSINDBK SHREECEM ZOMATO
TATACONSUM BPCL HEROMOTOCO LTIM CHOLAFIN ICICIPRULI ICICIGI HAVELLS UPL JIOFIN
GAIL TATAPOWER GODREJCP DABUR PFC RECLTD AMBUJACEM ADANIENSOL VEDL TVSMOTOR
SHRIRAMFIN BAJAJHLDNG IRCTC CGPOWER NAUKRI POLYCAB PNB BANKBARODA TIINDIA SRF
INDUSTOWER LODHA TORNTPHARM BERGEPAINT MARICO SBICARD BOSCHLTD ATGL UNITDSPR
MUTHOOTFIN ABCAPITAL BHEL CONCOR LICHSGFIN TATACOMM PETRONET MFSL MPHASIS
COLPAL HINDPETRO BHARATFORG MAXHEALTH OBEROIRLTY ZYDUSLIFE INDHOTEL BIOCON
BANKINDIA LUPIN HINDZINC ALKEM AUBANK PERSISTENT NMDC PAGEIND IDFCFIRSTB
JSWENERGY ABFRL JINDALSTEL CUMMINSIND IGL OFSS ASHOKLEY BALKRISIND POLICYBZR
SAIL OIL AUROPHARMA INDIANB UBL CANBK COFORGE TORNTPOWER MRF GMRINFRA CROMPTON
ACC GUJGASLTD LTTS NHPC NLCINDIA IDEA APLAPOLLO ESCORTS RAMCOCEM SUNDARMFIN
MOTHERSON HUDCO FACT YESBANK PAYTM IRB BHARTIHEXA LAURUSLABS AARTIIND MANAPPURAM
ASTRAL PIIND NAM-INDIA SUPREMEIND CUB DELHIVERY DIXON PRESTIGE MAZDOCK
NYKAA TATAELXSI FEDERALBNK ENDURANCE EXIDEIND CANFINHOME LINDEINDIA RVNL
KPITTECH POLYMED IPCALAB SUNTV GLENMARK CAMS MAHABANK NIACL VOLTAS BSE GLAND
JBCHEPHARM CDSL JSL HONAUT SUVENPHAR DEEPAKNTR APOLLOTYRE GICRE EMAMILTD UNIONBANK
TATAINVEST POONAWALLA CESC RBLBANK BANDHANBNK GODREJPROP NATIONALUM 360ONE NSDLNGINDS
HINDCOPPER SBFC HFCL KPRMILL FIVESTAR FINPIPE THERMAX KAJARIACER MEDPLUS
""".split()


def send_tg(text):
    if not (TG_TOKEN and TG_CHAT):
        print("[tg] missing creds"); return False
    for chunk in [text[i:i+3800] for i in range(0, len(text), 3800)]:
        try:
            r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT, "text": chunk, "parse_mode": "HTML",
                      "disable_web_page_preview": "true"}, timeout=15)
            if not r.ok:
                print(f"[tg] error {r.status_code}: {r.text[:200]}"); return False
        except Exception as e:
            print(f"[tg] exception: {e}"); return False
    print("[tg] sent ok"); return True


def calc_cpr(h, l, c):
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {"pp": pp, "bc": bc, "tc": tc}


def fmt_vol(v):
    if v >= 1e7: return f"{v/1e7:.2f}Cr"
    if v >= 1e5: return f"{v/1e5:.2f}L"
    return f"{int(v)}"


def main():
    print("Starting yfinance scan...")
    print(f"Telegram: {'yes' if TG_TOKEN else 'NO'}/{'yes' if TG_CHAT else 'NO'}")
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    scanned_at = ist.strftime("%a, %d %b %Y  %I:%M %p IST")
    print(f"Time: {scanned_at}")
    print(f"Universe: {len(STOCKS)} stocks")

    tickers = [f"{s}.NS" for s in STOCKS]
    print("Downloading from Yahoo Finance...")

    try:
        df = yf.download(tickers, period="5d", group_by='ticker',
                         auto_adjust=False, progress=False, threads=True, timeout=60)
    except Exception as e:
        err = f"yfinance error\n{scanned_at}\n\n{str(e)[:500]}"
        print(err); send_tg(err); sys.exit(1)

    print("Processing...")
    inside_stocks = []
    failed = 0
    for sym in STOCKS:
        ts = f"{sym}.NS"
        try:
            if ts not in df.columns.get_level_values(0):
                failed += 1; continue
            stock_df = df[ts].dropna()
            if len(stock_df) == 0:
                failed += 1; continue
            row = stock_df.iloc[-1]
            h, l, c, v = float(row['High']), float(row['Low']), float(row['Close']), float(row['Volume'])
            if not (h and l and c):
                failed += 1; continue
            pv = calc_cpr(h, l, c)
            if pv['bc'] <= c <= pv['tc']:
                w_pct = ((pv['tc'] - pv['bc']) / c) * 100
                inside_stocks.append({'sym': sym, 'c': c, 'v': v, 'w_pct': w_pct})
        except Exception:
            failed += 1; continue

    inside_stocks.sort(key=lambda x: x['w_pct'])  # narrowest CPR first
    print(f"Inside CPR: {len(inside_stocks)}, failed: {failed}")

    if not inside_stocks:
        send_tg(f"<b>Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n\nNo inside CPR stocks today.")
        return

    head = (f"<b>📊 Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Inside CPR: <b>{len(inside_stocks)}</b> stocks\n"
            f"Sorted by narrowest CPR first\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>S.No  Symbol         Volume</b>\n")
    lines = [f"{i:>3}. <b>{s['sym']:<13}</b> {fmt_vol(s['v'])}" for i, s in enumerate(inside_stocks, 1)]
    msg = head + "\n".join(lines)

    if send_tg(msg):
        print("✅ Sent successfully")


if __name__ == "__main__":
    main()
