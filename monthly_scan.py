#!/usr/bin/env python3
"""Monthly Inside CPR Scanner — runs daily near month-end via cron, but only
actually scans on the LAST TRADING DAY of the month (self-detected below).
Uses monthly OHLC to find stocks where NEXT month's CPR is completely
inside THIS month's CPR (monthly version of the daily scan.py).
Writes docs/monthly_cpr_list.json.
"""
import os, sys, io, json, datetime, smtplib
import yfinance as yf
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
REPORT_RECIPIENT   = os.environ.get("REPORT_RECIPIENT", "").strip()
FORCE_RUN          = os.environ.get("FORCE_RUN", "").strip() == "1"  # manual override for workflow_dispatch

BRAND_NAME    = "STARK SCHOOL OF FINANCE"
BRAND_TAGLINE = "Happy Price Action Trading"
BRAND_FOOTER  = "www.tradingwithgp.com"
LOGO_FILE     = "logo (Logo).png"

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
TATACONSUME BPCL HEROMOTOCO LTIM CHOLAFIN ICICIPRULI ICICIGI HAVELLS UPL JIOFIN
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

NSE_HOLIDAYS = {
    datetime.date(2025, 1, 26), datetime.date(2025, 2, 19),
    datetime.date(2025, 3, 14), datetime.date(2025, 3, 31),
    datetime.date(2025, 4, 10), datetime.date(2025, 4, 14),
    datetime.date(2025, 4, 18), datetime.date(2025, 5, 1),
    datetime.date(2025, 6, 7),  datetime.date(2025, 6, 26),
    datetime.date(2025, 6, 27), datetime.date(2025, 8, 15),
    datetime.date(2025, 8, 27), datetime.date(2025, 10, 2),
    datetime.date(2025, 10, 21),datetime.date(2025, 10, 22),
    datetime.date(2025, 11, 5), datetime.date(2025, 12, 25),
    datetime.date(2026, 1, 26), datetime.date(2026, 3, 20),
    datetime.date(2026, 4, 2),  datetime.date(2026, 4, 6),
    datetime.date(2026, 4, 14), datetime.date(2026, 5, 1),
    datetime.date(2026, 8, 15), datetime.date(2026, 10, 2),
    datetime.date(2026, 11, 4), datetime.date(2026, 11, 5),
    datetime.date(2026, 12, 25),
}


def is_trading_day(d):
    return d.weekday() < 5 and d not in NSE_HOLIDAYS


def next_trading_day(d):
    nd = d + datetime.timedelta(days=1)
    while not is_trading_day(nd):
        nd += datetime.timedelta(days=1)
    return nd


def is_last_trading_day_of_month(d):
    """True if d is a trading day and the next trading day falls in a new month."""
    if not is_trading_day(d):
        return False
    return next_trading_day(d).month != d.month


def _recipients():
    return [r.strip() for r in REPORT_RECIPIENT.split(",") if r.strip()]


def send_email_text(subject, body):
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and REPORT_RECIPIENT):
        print("[email] missing credentials")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = ", ".join(_recipients())
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, _recipients(), msg.as_string())
        print("[email] text sent ok")
        return True
    except Exception as e:
        print(f"[email] error: {e}")
        return False


def send_email_photo(image_bytes, subject, body, filename="monthly_inside_cpr.png"):
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and REPORT_RECIPIENT):
        print("[email] missing credentials")
        return False
    try:
        image_data = image_bytes.read()
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = ", ".join(_recipients())
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))
        img_attachment = MIMEImage(image_data, name=filename)
        img_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(img_attachment)
        img_inline = MIMEImage(image_data)
        img_inline.add_header("Content-ID", "<poster>")
        img_inline.add_header("Content-Disposition", "inline", filename=filename)
        msg.attach(img_inline)
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, _recipients(), msg.as_string())
        print(f"[email] photo sent to {_recipients()}")
        return True
    except Exception as e:
        print(f"[email] photo error: {e}")
        return False


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


def make_poster(stocks, target_label, header_title="MONTHLY INSIDE CPR STOCKS"):
    n = len(stocks)
    use_two_col = n > 5
    rows = (n + 1) // 2 if use_two_col else n
    W = 1080; pad = 60; row_h = 88
    y_logo_top = 50; logo_area_h = 240
    y_title_top = y_logo_top + logo_area_h; title_bar_h = 200
    y_table_top = y_title_top + title_bar_h + 50
    table_h = (rows + 1) * row_h
    y_footer = y_table_top + table_h + 60; footer_h = 140
    H = y_footer + footer_h + 30
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    try:
        logo = Image.open(LOGO_FILE).convert("RGBA")
        logo.thumbnail((420, logo_area_h - 20), Image.LANCZOS)
        img.paste(logo, ((W - logo.width) // 2, y_logo_top + (logo_area_h - logo.height) // 2), logo)
    except Exception as e:
        print(f"[poster] logo load failed: {e}")
        center_text(d, BRAND_NAME, font(56), W / 2, y_logo_top + 90, NAVY)
    d.rectangle([0, y_title_top, W, y_title_top + title_bar_h], fill=NAVY)
    d.rectangle([0, y_title_top, 12, y_title_top + title_bar_h], fill=GREEN)
    center_text(d, header_title, font(56), W / 2, y_title_top + 35, WHITE)
    center_text(d, target_label, font(46), W / 2, y_title_top + 115, GREEN_LT)
    if use_two_col:
        col_w = [130, (W - 2 * pad - 130) / 2, (W - 2 * pad - 130) / 2]
        x_col = [pad, pad + col_w[0], pad + col_w[0] + col_w[1]]
        headers = ["S.NO", "STOCKS", "STOCKS"]
    else:
        col_w = [180, W - 2 * pad - 180]
        x_col = [pad, pad + col_w[0]]
        headers = ["S.NO", "STOCKS"]
    f_head = font(34); f_cell = font(38); f_no = font(34)
    y = y_table_top
    for i, h in enumerate(headers):
        x = x_col[i]; cw = col_w[i]
        d.rectangle([x, y, x + cw, y + row_h], fill=NAVY, outline=NAVY)
        bbox = d.textbbox((0, 0), h, font=f_head)
        tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
        d.text((x + (cw - tw) / 2, y + (row_h - th) / 2 - 4), h, fill=WHITE, font=f_head)
    y += row_h
    if use_two_col:
        left = stocks[:rows]; right = stocks[rows:]
        for i in range(rows):
            row_bg = CREAM if i % 2 == 0 else WHITE
            d.rectangle([x_col[0], y, x_col[0] + col_w[0], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            sno = f"{i+1}."
            bbox = d.textbbox((0, 0), sno, font=f_no); tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_col[0] + (col_w[0] - tw) / 2, y + (row_h - th) / 2 - 4), sno, fill=DARK, font=f_no)
            for ci, col_stocks in enumerate([left, right]):
                cx = x_col[1 + ci]; cw = col_w[1 + ci]
                d.rectangle([cx, y, cx + cw, y + row_h], fill=row_bg, outline=GREY_LN, width=1)
                if i < len(col_stocks):
                    name = col_stocks[i]
                    bbox = d.textbbox((0, 0), name, font=f_cell); tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
                    d.text((cx + (cw - tw) / 2, y + (row_h - th) / 2 - 4), name, fill=DARK, font=f_cell)
            y += row_h
    else:
        for i, name in enumerate(stocks):
            row_bg = CREAM if i % 2 == 0 else WHITE
            sno = f"{i+1}."
            d.rectangle([x_col[0], y, x_col[0] + col_w[0], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            bbox = d.textbbox((0, 0), sno, font=f_no); tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_col[0] + (col_w[0] - tw) / 2, y + (row_h - th) / 2 - 4), sno, fill=DARK, font=f_no)
            d.rectangle([x_col[1], y, x_col[1] + col_w[1], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            bbox = d.textbbox((0, 0), name, font=f_cell); tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            d.text((x_col[1] + (col_w[1] - tw) / 2, y + (row_h - th) / 2 - 4), name, fill=DARK, font=f_cell)
            y += row_h
    d.rectangle([pad, y_footer, W - pad, y_footer + 3], fill=GREEN)
    if BRAND_TAGLINE:
        center_text(d, BRAND_TAGLINE, font(38), W / 2, y_footer + 30, NAVY)
    if BRAND_FOOTER:
        center_text(d, BRAND_FOOTER, font(28), W / 2, y_footer + 85, GREY_TXT)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def export_cpr_list_json(stocks_data, target_label, path="docs/monthly_cpr_list.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    payload = {
        "generated_at": ist.strftime("%Y-%m-%d %H:%M IST"),
        "for_month":    target_label,
        "total":        len(stocks_data),
        "stocks": [
            {
                "sym":        s["sym"],
                "close":      round(s["c"], 2),
                "cpr_upper":  round(s["pv"]["upper"], 2),
                "cpr_lower":  round(s["pv"]["lower"], 2),
                "w_pct":      round((s["pv"]["width"] / s["c"]) * 100, 3),
                "r1":         round(s["pv"]["r1"], 2),
                "s1":         round(s["pv"]["s1"], 2),
                "month_high": round(s["mo_high"], 2),
                "month_low":  round(s["mo_low"], 2),
            }
            for s in stocks_data
        ]
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[export] Exported {len(stocks_data)} stocks to {path}")


def next_month_label(this_month_last_date):
    y, m = this_month_last_date.year, this_month_last_date.month
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return datetime.date(ny, nm, 1).strftime("%B %Y")


def main():
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    today = ist.date()
    print(f"Time: {ist.strftime('%a %d %b %Y %I:%M %p IST')}")

    if not FORCE_RUN and not is_last_trading_day_of_month(today):
        print(f"[monthly] {today} is not the last trading day of the month — skipping. "
              f"(next trading day: {next_trading_day(today)})")
        return

    print("Starting MONTHLY scan (last trading day of month)...")
    print(f"Email configured: gmail={'yes' if GMAIL_ADDRESS else 'NO'} pass={'yes' if GMAIL_APP_PASSWORD else 'NO'} to={'yes' if REPORT_RECIPIENT else 'NO'}")

    tickers = [f"{s}.NS" for s in STOCKS]
    print(f"Downloading {len(tickers)} tickers (2y history for monthly resample)...")
    try:
        df = yf.download(tickers, period="2y", group_by='ticker',
                         auto_adjust=False, progress=False, threads=True, timeout=120)
    except Exception as e:
        send_email_text("Monthly CPR Scanner Error", f"yfinance error: {e}")
        sys.exit(1)
    if df is None or df.empty:
        send_email_text("Monthly CPR Scanner Error", "yfinance returned empty data")
        sys.exit(1)

    print("Processing monthly resample...")
    inside = []
    month_label = None

    for sym in STOCKS:
        ts = f"{sym}.NS"
        try:
            if ts not in df.columns.get_level_values(0): continue
            stock_df = df[ts].dropna(how='any')
            if len(stock_df) < 30: continue

            monthly = stock_df.resample('ME').agg(
                {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
            ).dropna(how='any')
            if len(monthly) < 2: continue

            # monthly.iloc[-1] = the month that just closed today (last trading day)
            # monthly.iloc[-2] = the month before that
            just_closed  = monthly.iloc[-1]
            prior_month  = monthly.iloc[-2]

            if month_label is None:
                last_month_date = monthly.index[-1].date()
                month_label = next_month_label(last_month_date)
                print(f"Target month: {month_label}")

            this_month_cpr = calc_cpr(float(prior_month['High']), float(prior_month['Low']), float(prior_month['Close']))
            next_month_cpr = calc_cpr(float(just_closed['High']), float(just_closed['Low']), float(just_closed['Close']))

            if (next_month_cpr['upper'] <= this_month_cpr['upper'] and
                next_month_cpr['lower'] >= this_month_cpr['lower']):
                w_pct = (next_month_cpr['width'] / float(just_closed['Close'])) * 100
                pp = (float(just_closed['High']) + float(just_closed['Low']) + float(just_closed['Close'])) / 3
                r1 = 2 * pp - float(just_closed['Low'])
                s1 = 2 * pp - float(just_closed['High'])
                next_month_cpr['r1'] = r1
                next_month_cpr['s1'] = s1
                inside.append({
                    'sym': sym, 'w_pct': w_pct,
                    'c': float(just_closed['Close']),
                    'pv': next_month_cpr,
                    'mo_high': float(just_closed['High']),
                    'mo_low': float(just_closed['Low']),
                })
        except Exception:
            continue

    inside.sort(key=lambda x: x['w_pct'])
    print(f"Found {len(inside)} monthly inside CPR stocks")

    export_cpr_list_json(inside, month_label or "")

    if not inside:
        send_email_text(
            f"Monthly Inside CPR Stock List — {month_label}",
            f"<b>Monthly Inside CPR Stock List</b><br>For: {month_label}<br><br>No monthly inside CPR stocks."
        )
        return

    syms = [s['sym'] for s in inside]
    print(f"Stocks: {syms}")

    img_buf = make_poster(syms, month_label)
    subject = f"📊 Monthly Inside CPR Stock List — {month_label}"
    body = (
        f"<h2>Monthly Inside CPR Stock List</h2>"
        f"<p>For the month: <b>{month_label}</b></p>"
        f"<p>Total stocks: <b>{len(syms)}</b></p>"
        f"<p>See attached poster image.</p>"
        f"<p><i>Happy Price Action Trading 📈</i></p>"
    )
    send_email_photo(img_buf, subject, body)


if __name__ == "__main__":
    main()
