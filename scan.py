#!/usr/bin/env python3
"""Inside CPR Scanner — proper logic using previous trading day for CPR."""
import os, sys, datetime, requests
import yfinance as yf
import pandas as pd

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

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
SAIL OIL AUROPHARMA INDIANB UBL CANBK COFORGE TORNTPOWER MRF CROMPTON
ACC GUJGASLTD LTTS NHPC NLCINDIA IDEA APLAPOLLO ESCORTS RAMCOCEM SUNDARMFIN
MOTHERSON HUDCO YESBANK PAYTM IRB LAURUSLABS AARTIIND MANAPPURAM
ASTRAL PIIND NAM-INDIA SUPREMEIND CUB DELHIVERY DIXON PRESTIGE MAZDOCK
NYKAA TATAELXSI FEDERALBNK ENDURANCE EXIDEIND CANFIN LINDEINDIA RVNL
KPITTECH POLYMED IPCALAB SUNTV GLENMARK CAMS MAHABANK VOLTAS BSE GLAND
JBCHEPHARM CDSL JSL HONAUT APOLLOTYRE EMAMILTD UNIONBANK
TATAINVEST POONAWALLA CESC RBLBANK BANDHANBNK GODREJPROP NATIONALUM
HINDCOPPER SBFC HFCL KPRMILL FIVESTAR THERMAX KAJARIACER MEDPLUS
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
    return {"pp": pp, "bc": bc, "tc": tc, "upper": max(tc, bc), "lower": min(tc, bc)}


def fmt_vol(v):
    if v >= 1e7: return f"{v/1e7:.2f}Cr"
    if v >= 1e5: return f"{v/1e5:.2f}L"
    return f"{int(v)}"


def main():
    print("Starting yfinance scan...")
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    scanned_at = ist.strftime("%a, %d %b %Y  %I:%M %p IST")
    print(f"Time: {scanned_at}")
    print(f"Universe: {len(STOCKS)} stocks")

    tickers = [f"{s}.NS" for s in STOCKS]
    print("Downloading 10 days of data from Yahoo Finance...")

    try:
        df = yf.download(tickers, period="10d", group_by='ticker',
                         auto_adjust=False, progress=False, threads=True, timeout=90)
    except Exception as e:
        err = f"yfinance error\n{scanned_at}\n\n{str(e)[:500]}"
        print(err); send_tg(err); sys.exit(1)

    if df is None or df.empty:
        send_tg(f"Scanner Error: yfinance returned empty data\n{scanned_at}")
        sys.exit(1)

    print(f"Data shape: {df.shape}")
    print("Processing...")

    inside = []
    no_data = 0
    not_inside = 0
    cpr_day = None

    for sym in STOCKS:
        ts = f"{sym}.NS"
        try:
            if ts not in df.columns.get_level_values(0):
                no_data += 1; continue
            stock_df = df[ts].dropna(how='any')
            if len(stock_df) < 2:
                no_data += 1; continue

            # Most recent trading day's data
            today = stock_df.iloc[-1]
            yday  = stock_df.iloc[-2]

            if cpr_day is None:
                cpr_day = stock_df.index[-1].strftime("%a %d %b %Y")
                print(f"Latest trading day in data: {cpr_day}")
                print(f"Previous day: {stock_df.index[-2].strftime('%a %d %b %Y')}")

            # CPR calculated from PREVIOUS day's OHLC, applies to TODAY
            h_y, l_y, c_y = float(yday['High']), float(yday['Low']), float(yday['Close'])
            c_today = float(today['Close'])
            v_today = float(today['Volume'])

            pv = calc_cpr(h_y, l_y, c_y)

            if pv['lower'] <= c_today <= pv['upper']:
                w_pct = ((pv['upper'] - pv['lower']) / c_today) * 100
                inside.append({
                    'sym': sym, 'c': c_today, 'v': v_today, 'w_pct': w_pct,
                    'upper': pv['upper'], 'lower': pv['lower'],
                })
            else:
                not_inside += 1
        except Exception as e:
            no_data += 1
            continue

    inside.sort(key=lambda x: x['w_pct'])  # narrowest CPR first
    print(f"Inside CPR: {len(inside)}, Not inside: {not_inside}, No data: {no_data}")

    if not inside:
        send_tg(f"<b>Inside CPR Scanner</b>\n<i>{scanned_at}</i>\nData: {cpr_day or 'unknown'}\n\nNo inside CPR stocks today.")
        return

    head = (f"<b>📊 Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n"
            f"Data: <b>{cpr_day}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Inside CPR: <b>{len(inside)}</b> stocks\n"
            f"Sorted by narrowest CPR first\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<code> S.No  Symbol         Volume</code>\n")
    lines = [f"<code>{i:>4}. {s['sym']:<14} {fmt_vol(s['v']):>10}</code>" for i, s in enumerate(inside, 1)]
    msg = head + "\n".join(lines)

    if send_tg(msg):
        print("✅ Sent successfully")


if __name__ == "__main__":
    main()
