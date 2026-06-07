#!/usr/bin/env python3
"""Inside CPR Scanner — Tomorrow's CPR is inside Today's CPR."""
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
    """Returns CPR with handling for inverted case."""
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {
        "pp": pp,
        "tc_raw": tc, "bc_raw": bc,
        "upper": max(tc, bc),   # CPR top
        "lower": min(tc, bc),   # CPR bottom
        "width": abs(tc - bc),
    }


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
    print("Downloading 10 days of data...")

    try:
        df = yf.download(tickers, period="10d", group_by='ticker',
                         auto_adjust=False, progress=False, threads=True, timeout=90)
    except Exception as e:
        err = f"yfinance error\n{scanned_at}\n\n{str(e)[:500]}"
        print(err); send_tg(err); sys.exit(1)

    if df is None or df.empty:
        send_tg(f"Scanner Error: empty yfinance data\n{scanned_at}")
        sys.exit(1)

    print(f"Data shape: {df.shape}")
    print("Processing...")

    inside = []
    no_data = 0
    not_inside = 0
    today_label = None
    tomorrow_label = None

    for sym in STOCKS:
        ts = f"{sym}.NS"
        try:
            if ts not in df.columns.get_level_values(0):
                no_data += 1; continue
            stock_df = df[ts].dropna(how='any')
            if len(stock_df) < 2:
                no_data += 1; continue

            # day_today = most recent trading day (the day just closed at 4 PM)
            # day_yday  = the day before that
            day_today = stock_df.iloc[-1]
            day_yday  = stock_df.iloc[-2]

            if today_label is None:
                d_today = stock_df.index[-1]
                today_label = d_today.strftime("%a %d %b %Y")
                # Next trading day = today + 1 business day (skip weekends)
                d_tomorrow = d_today + pd.tseries.offsets.BDay(1)
                tomorrow_label = d_tomorrow.strftime("%a %d %b %Y")
                print(f"Today (data day): {today_label}")
                print(f"Tomorrow (target): {tomorrow_label}")

            # Today's CPR = calculated from YESTERDAY's H/L/C (was active during today)
            today_cpr = calc_cpr(
                float(day_yday['High']),
                float(day_yday['Low']),
                float(day_yday['Close']))

            # Tomorrow's CPR = calculated from TODAY's H/L/C (will be active tomorrow)
            tomorrow_cpr = calc_cpr(
                float(day_today['High']),
                float(day_today['Low']),
                float(day_today['Close']))

            # Inside CPR: tomorrow's CPR is fully inside today's CPR
            is_inside = (tomorrow_cpr['upper'] <= today_cpr['upper'] and
                         tomorrow_cpr['lower'] >= today_cpr['lower'])

            if is_inside:
                w_pct = (tomorrow_cpr['width'] / float(day_today['Close'])) * 100
                inside.append({
                    'sym': sym,
                    'c': float(day_today['Close']),
                    'v': float(day_today['Volume']),
                    'tom_upper': tomorrow_cpr['upper'],
                    'tom_lower': tomorrow_cpr['lower'],
                    'tod_upper': today_cpr['upper'],
                    'tod_lower': today_cpr['lower'],
                    'w_pct': w_pct,
                })
            else:
                not_inside += 1
        except Exception:
            no_data += 1
            continue

    inside.sort(key=lambda x: x['w_pct'])  # narrowest tomorrow CPR first
    print(f"Inside CPR: {len(inside)}, Not inside: {not_inside}, No data: {no_data}")

    if not inside:
        send_tg(f"<b>Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n\nNo inside CPR stocks for {tomorrow_label}.")
        return

    head = (f"<b>📊 Inside CPR Scanner</b>\n<i>{scanned_at}</i>\n"
            f"For trading on: <b>{tomorrow_label}</b>\n"
            f"Based on close of: {today_label}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Tomorrow's CPR inside Today's CPR: <b>{len(inside)}</b> stocks\n"
            f"Sorted by narrowest CPR first\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<code> S.No  Symbol         Volume</code>\n")
    lines = [f"<code>{i:>4}. {s['sym']:<14} {fmt_vol(s['v']):>10}</code>" for i, s in enumerate(inside, 1)]
    msg = head + "\n".join(lines)

    if send_tg(msg):
        print("✅ Sent successfully")


if __name__ == "__main__":
    main()
