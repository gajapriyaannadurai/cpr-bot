#!/usr/bin/env python3
"""Inside CPR Scanner — sends a poster image to Telegram."""
import os, sys, io, datetime, requests
import yfinance as yf
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

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


def send_tg_text(text):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data={"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"}, timeout=15)


def send_tg_photo(image_bytes, caption):
    r = requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
        data={"chat_id": TG_CHAT, "caption": caption, "parse_mode": "HTML"},
        files={"photo": ("inside_cpr.png", image_bytes, "image/png")},
        timeout=30)
    if r.ok:
        print("[tg] photo sent ok")
        return True
    print(f"[tg] photo error {r.status_code}: {r.text[:200]}")
    return False


def calc_cpr(h, l, c):
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {"upper": max(tc, bc), "lower": min(tc, bc), "width": abs(tc - bc)}


def get_font(size):
    """Try to load a clean bold font, fall back to default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_poster(stocks, target_date):
    """Render a poster image like the user's reference."""
    n = len(stocks)
    # 2 columns layout when more than 6 stocks
    use_two_col = n > 6
    rows = (n + 1) // 2 if use_two_col else n

    W = 1080
    pad = 60
    title_h = 220
    table_top = title_h + 60
    row_h = 90
    table_h = (rows + 1) * row_h
    footer_h = 100
    H = table_top + table_h + footer_h + pad

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # ── Title ──
    f_title = get_font(58)
    f_subtitle = get_font(48)
    title_line1 = target_date
    title_line2 = "INSIDE CPR STOCKS"

    bbox = d.textbbox((0, 0), title_line1, font=f_title)
    w1 = bbox[2] - bbox[0]
    d.text(((W - w1) / 2, 80), title_line1, fill="black", font=f_title)

    bbox = d.textbbox((0, 0), title_line2, font=f_subtitle)
    w2 = bbox[2] - bbox[0]
    d.text(((W - w2) / 2, 160), title_line2, fill="black", font=f_subtitle)

    # ── Table ──
    f_head = get_font(36)
    f_cell = get_font(36)

    if use_two_col:
        col_widths = [120, (W - 2 * pad - 120) / 2, (W - 2 * pad - 120) / 2]
        x_cols = [pad, pad + col_widths[0], pad + col_widths[0] + col_widths[1]]
        headers = ["S.NO", "STOCKS", ""]
    else:
        col_widths = [200, W - 2 * pad - 200]
        x_cols = [pad, pad + col_widths[0]]
        headers = ["S.NO", "STOCKS"]

    y = table_top
    # header row
    for i, h_text in enumerate(headers):
        x = x_cols[i]
        cw = col_widths[i] if i < len(col_widths) else col_widths[-1]
        d.rectangle([x, y, x + cw, y + row_h], outline="black", width=3)
        if h_text:
            bbox = d.textbbox((0, 0), h_text, font=f_head)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            d.text((x + (cw - tw) / 2, y + (row_h - th) / 2 - 5), h_text, fill="black", font=f_head)

    y += row_h

    # data rows
    if use_two_col:
        left = stocks[:rows]
        right = stocks[rows:]
        for i in range(rows):
            # S.No cell
            d.rectangle([x_cols[0], y, x_cols[0] + col_widths[0], y + row_h], outline="black", width=3)
            sno_text = f"{i+1}."
            bbox = d.textbbox((0, 0), sno_text, font=f_cell)
            tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_cols[0] + (col_widths[0] - tw) / 2, y + (row_h - th) / 2 - 5), sno_text, fill="black", font=f_cell)
            # Left column
            d.rectangle([x_cols[1], y, x_cols[1] + col_widths[1], y + row_h], outline="black", width=3)
            sym_l = left[i] if i < len(left) else ""
            if sym_l:
                d.text((x_cols[1] + 30, y + (row_h - 40) / 2), sym_l, fill="black", font=f_cell)
            # Right column
            d.rectangle([x_cols[2], y, x_cols[2] + col_widths[2], y + row_h], outline="black", width=3)
            sym_r = right[i] if i < len(right) else ""
            if sym_r:
                d.text((x_cols[2] + 30, y + (row_h - 40) / 2), sym_r, fill="black", font=f_cell)
            y += row_h
    else:
        for i, sym in enumerate(stocks):
            d.rectangle([x_cols[0], y, x_cols[0] + col_widths[0], y + row_h], outline="black", width=3)
            sno_text = f"{i+1}."
            bbox = d.textbbox((0, 0), sno_text, font=f_cell)
            tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_cols[0] + (col_widths[0] - tw) / 2, y + (row_h - th) / 2 - 5), sno_text, fill="black", font=f_cell)
            d.rectangle([x_cols[1], y, x_cols[1] + col_widths[1], y + row_h], outline="black", width=3)
            d.text((x_cols[1] + 30, y + (row_h - 40) / 2), sym, fill="black", font=f_cell)
            y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def main():
    print("Starting scan...")
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    print(f"Time: {ist.strftime('%a %d %b %Y %I:%M %p IST')}")

    tickers = [f"{s}.NS" for s in STOCKS]
    print(f"Downloading {len(tickers)} tickers...")
    try:
        df = yf.download(tickers, period="10d", group_by='ticker',
                         auto_adjust=False, progress=False, threads=True, timeout=90)
    except Exception as e:
        send_tg_text(f"yfinance error: {e}")
        sys.exit(1)

    if df is None or df.empty:
        send_tg_text("yfinance returned empty data")
        sys.exit(1)

    print("Processing...")
    inside = []
    tomorrow_label = None

    for sym in STOCKS:
        ts = f"{sym}.NS"
        try:
            if ts not in df.columns.get_level_values(0):
                continue
            stock_df = df[ts].dropna(how='any')
            if len(stock_df) < 2:
                continue

            day_today = stock_df.iloc[-1]
            day_yday  = stock_df.iloc[-2]

            if tomorrow_label is None:
                d_today = stock_df.index[-1]
                d_tomorrow = d_today + pd.tseries.offsets.BDay(1)
                tomorrow_label = d_tomorrow.strftime("%d-%m-%Y").upper()
                print(f"Target: {tomorrow_label}")

            today_cpr = calc_cpr(float(day_yday['High']), float(day_yday['Low']), float(day_yday['Close']))
            tomorrow_cpr = calc_cpr(float(day_today['High']), float(day_today['Low']), float(day_today['Close']))

            # Tomorrow's CPR is fully inside Today's CPR
            if (tomorrow_cpr['upper'] <= today_cpr['upper'] and
                tomorrow_cpr['lower'] >= today_cpr['lower']):
                w_pct = (tomorrow_cpr['width'] / float(day_today['Close'])) * 100
                inside.append({'sym': sym, 'w_pct': w_pct})
        except Exception:
            continue

    inside.sort(key=lambda x: x['w_pct'])  # narrowest first
    print(f"Found {len(inside)} inside CPR stocks")

    if not inside:
        send_tg_text(f"<b>Inside CPR Stock List</b>\nFor: {tomorrow_label}\n\nNo inside CPR stocks today.")
        return

    syms = [s['sym'] for s in inside]
    print(f"Stocks: {syms}")

    img_buf = make_poster(syms, tomorrow_label)
    caption = f"<b>Inside CPR Stock List</b>\nFor next trading session: <b>{tomorrow_label}</b>\nTotal: {len(syms)} stocks"
    send_tg_photo(img_buf, caption)


if __name__ == "__main__":
    main()
