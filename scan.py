#!/usr/bin/env python3
"""Inside CPR Scanner — branded poster image to Telegram."""
import os, sys, io, datetime, requests
import yfinance as yf
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# Brand customisation
BRAND_NAME    = "STARK SCHOOL OF FINANCE"
BRAND_FOOTER  = "www.tradingwithgp.com"   # set to "" to hide
LOGO_FILE     = "logo (Logo).png"

# Brand colors (from logo)
NAVY      = (26, 40, 71)
GREEN     = (45, 138, 78)
GREEN_LT  = (140, 205, 165)
CREAM     = (248, 249, 252)
GREY_LN   = (210, 215, 225)
GREY_TXT  = (107, 114, 128)
DARK      = (26, 26, 26)
WHITE     = (255, 255, 255)

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


def _chat_ids():
    return [c.strip() for c in TG_CHAT.split(",") if c.strip()]


def send_tg_text(text):
    for chat_id in _chat_ids():
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print(f"[tg] text error for {chat_id}: {e}")


def send_tg_photo(image_bytes, caption):
    image_bytes_data = image_bytes.read()
    sent_to = 0
    for chat_id in _chat_ids():
        try:
            r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": ("inside_cpr.png", image_bytes_data, "image/png")},
                timeout=30)
            if r.ok:
                sent_to += 1
                print(f"[tg] photo sent to {chat_id}")
            else:
                print(f"[tg] error for {chat_id}: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"[tg] photo error for {chat_id}: {e}")
    return sent_to > 0


def calc_cpr(h, l, c):
    pp = (h + l + c) / 3
    bc = (h + l) / 2
    tc = 2 * pp - bc
    return {"upper": max(tc, bc), "lower": min(tc, bc), "width": abs(tc - bc)}


def font(size, bold=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def center_text(d, text, font_obj, x_center, y, fill):
    bbox = d.textbbox((0, 0), text, font=font_obj)
    w = bbox[2] - bbox[0]
    d.text((x_center - w / 2, y), text, fill=fill, font=font_obj)


def make_poster(stocks, target_date):
    n = len(stocks)
    use_two_col = n > 5
    rows = (n + 1) // 2 if use_two_col else n

    W = 1080
    pad = 60
    row_h = 88

    # Layout sections
    y_logo_top = 50
    logo_area_h = 240
    y_title_top = y_logo_top + logo_area_h
    title_bar_h = 200
    y_table_top = y_title_top + title_bar_h + 50
    table_h = (rows + 1) * row_h
    y_footer = y_table_top + table_h + 60
    footer_h = 100
    H = y_footer + footer_h + 30

    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # ── Logo ──
    try:
        logo = Image.open(LOGO_FILE).convert("RGBA")
        logo.thumbnail((420, logo_area_h - 20), Image.LANCZOS)
        img.paste(logo, ((W - logo.width) // 2, y_logo_top + (logo_area_h - logo.height) // 2), logo)
    except Exception as e:
        print(f"[poster] logo load failed: {e}")
        center_text(d, BRAND_NAME, font(56), W / 2, y_logo_top + 90, NAVY)

    # ── Title Bar (navy bg) ──
    d.rectangle([0, y_title_top, W, y_title_top + title_bar_h], fill=NAVY)
    # Green accent line on left
    d.rectangle([0, y_title_top, 12, y_title_top + title_bar_h], fill=GREEN)
    # Title
    center_text(d, "INSIDE CPR STOCKS", font(64), W / 2, y_title_top + 35, WHITE)
    # Date subtitle
    center_text(d, target_date, font(52), W / 2, y_title_top + 115, GREEN_LT)

    # ── Table ──
    if use_two_col:
        col_w = [130, (W - 2 * pad - 130) / 2, (W - 2 * pad - 130) / 2]
        x_col = [pad, pad + col_w[0], pad + col_w[0] + col_w[1]]
        headers = ["S.NO", "STOCKS", "STOCKS"]
    else:
        col_w = [180, W - 2 * pad - 180]
        x_col = [pad, pad + col_w[0]]
        headers = ["S.NO", "STOCKS"]

    f_head = font(34)
    f_cell = font(38)
    f_no   = font(34)

    y = y_table_top

    # Header row (navy bg)
    for i, h in enumerate(headers):
        x = x_col[i]; cw = col_w[i]
        d.rectangle([x, y, x + cw, y + row_h], fill=NAVY, outline=NAVY)
        bbox = d.textbbox((0, 0), h, font=f_head)
        tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
        d.text((x + (cw - tw) / 2, y + (row_h - th) / 2 - 4), h, fill=WHITE, font=f_head)
    y += row_h

    # Data rows
    if use_two_col:
        left = stocks[:rows]; right = stocks[rows:]
        for i in range(rows):
            row_bg = CREAM if i % 2 == 0 else WHITE
            # S.No cell
            d.rectangle([x_col[0], y, x_col[0] + col_w[0], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            sno = f"{i+1}."
            bbox = d.textbbox((0, 0), sno, font=f_no); tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_col[0] + (col_w[0] - tw) / 2, y + (row_h - th) / 2 - 4), sno, fill=NAVY, font=f_no)
            # Left
            d.rectangle([x_col[1], y, x_col[1] + col_w[1], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            if i < len(left):
                d.text((x_col[1] + 40, y + (row_h - 42) / 2 - 2), left[i], fill=DARK, font=f_cell)
            # Right
            d.rectangle([x_col[2], y, x_col[2] + col_w[2], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            if i < len(right):
                d.text((x_col[2] + 40, y + (row_h - 42) / 2 - 2), right[i], fill=DARK, font=f_cell)
            y += row_h
    else:
        for i, sym in enumerate(stocks):
            row_bg = CREAM if i % 2 == 0 else WHITE
            d.rectangle([x_col[0], y, x_col[0] + col_w[0], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            sno = f"{i+1}."
            bbox = d.textbbox((0, 0), sno, font=f_no); tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_col[0] + (col_w[0] - tw) / 2, y + (row_h - th) / 2 - 4), sno, fill=NAVY, font=f_no)
            d.rectangle([x_col[1], y, x_col[1] + col_w[1], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            d.text((x_col[1] + 40, y + (row_h - 42) / 2 - 2), sym, fill=DARK, font=f_cell)
            y += row_h

    # ── Footer ──
    if BRAND_FOOTER:
        # Thin green divider
        d.rectangle([pad, y_footer, W - pad, y_footer + 3], fill=GREEN)
        center_text(d, BRAND_FOOTER, font(34), W / 2, y_footer + 35, GREY_TXT)

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
        send_tg_text(f"yfinance error: {e}"); sys.exit(1)
    if df is None or df.empty:
        send_tg_text("yfinance returned empty data"); sys.exit(1)

    print("Processing...")
    inside = []
    tomorrow_label = None

    for sym in STOCKS:
        ts = f"{sym}.NS"
        try:
            if ts not in df.columns.get_level_values(0): continue
            stock_df = df[ts].dropna(how='any')
            if len(stock_df) < 2: continue

            day_today = stock_df.iloc[-1]
            day_yday  = stock_df.iloc[-2]

            if tomorrow_label is None:
                d_today = stock_df.index[-1]
                d_tomorrow = d_today + pd.tseries.offsets.BDay(1)
                tomorrow_label = d_tomorrow.strftime("%d-%m-%Y")
                print(f"Target: {tomorrow_label}")

            today_cpr    = calc_cpr(float(day_yday['High']),  float(day_yday['Low']),  float(day_yday['Close']))
            tomorrow_cpr = calc_cpr(float(day_today['High']), float(day_today['Low']), float(day_today['Close']))

            if (tomorrow_cpr['upper'] <= today_cpr['upper'] and
                tomorrow_cpr['lower'] >= today_cpr['lower']):
                w_pct = (tomorrow_cpr['width'] / float(day_today['Close'])) * 100
                inside.append({'sym': sym, 'w_pct': w_pct})
        except Exception:
            continue

    inside.sort(key=lambda x: x['w_pct'])
    print(f"Found {len(inside)} inside CPR stocks")

    if not inside:
        send_tg_text(f"<b>Inside CPR Stock List</b>\nFor: {tomorrow_label}\n\nNo inside CPR stocks today.")
        return

    syms = [s['sym'] for s in inside]
    print(f"Stocks: {syms}")

    img_buf = make_poster(syms, tomorrow_label)
    caption = f"<b>Inside CPR Stock List</b>\nFor next trading session: <b>{tomorrow_label}</b>"
    send_tg_photo(img_buf, caption)


if __name__ == "__main__":
    main()
