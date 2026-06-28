#!/usr/bin/env python3
"""Inside CPR Scanner — sends branded poster via Gmail."""
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

# Brand customisation
BRAND_NAME    = "STARK SCHOOL OF FINANCE"
BRAND_TAGLINE = "Happy Price Action Trading"
BRAND_FOOTER  = "www.tradingwithgp.com"
LOGO_FILE     = "logo (Logo).png"

# Brand colors
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


def send_email_photo(image_bytes, subject, body):
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

        img_attachment = MIMEImage(image_data, name="inside_cpr.png")
        img_attachment.add_header("Content-Disposition", "attachment", filename="inside_cpr.png")
        msg.attach(img_attachment)

        # Also embed inline for email clients that show images
        img_inline = MIMEImage(image_data)
        img_inline.add_header("Content-ID", "<poster>")
        img_inline.add_header("Content-Disposition", "inline", filename="inside_cpr.png")
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


def make_poster(stocks, target_date):
    n = len(stocks)
    use_two_col = n > 5
    rows = (n + 1) // 2 if use_two_col else n

    W = 1080
    pad = 60
    row_h = 88

    y_logo_top = 50
    logo_area_h = 240
    y_title_top = y_logo_top + logo_area_h
    title_bar_h = 200
    y_table_top = y_title_top + title_bar_h + 50
    table_h = (rows + 1) * row_h
    y_footer = y_table_top + table_h + 60
    footer_h = 140
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
    center_text(d, "INSIDE CPR STOCKS", font(64), W / 2, y_title_top + 35, WHITE)
    center_text(d, target_date, font(52), W / 2, y_title_top + 115, GREEN_LT)

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
            d.text((x_col[0] + (col_w[0] - tw) / 2, y + (row_h - th) / 2 - 4), sno, fill=NAVY, font=f_no)
            d.rectangle([x_col[1], y, x_col[1] + col_w[1], y + row_h], fill=row_bg, outline=GREY_LN, width=1)
            if i < len(left):
                d.text((x_col[1] + 40, y + (row_h - 42) / 2 - 2), left[i], fill=DARK, font=f_cell)
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

    if BRAND_TAGLINE or BRAND_FOOTER:
        d.rectangle([pad, y_footer, W - pad, y_footer + 3], fill=GREEN)
        if BRAND_TAGLINE:
            center_text(d, BRAND_TAGLINE, font(38), W / 2, y_footer + 30, NAVY)
        if BRAND_FOOTER:
            center_text(d, BRAND_FOOTER, font(28), W / 2, y_footer + 85, GREY_TXT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def export_watchlist_js(stocks_data, target_date):
    """Save the structured watchlist for downstream tools (Fyers bot etc)."""
    os.makedirs("exports", exist_ok=True)
    lines = [
        "/**",
        " * cpr-watchlist.js — Auto-generated by Inside CPR Scanner",
        f" * Scan date: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        f" * Total stocks: {len(stocks_data)}",
        " * Auto-loaded by Fyers CPR Bot every morning at 9:00 AM.",
        " */",
        "",
        "const stocks = [",
    ]
    for s in stocks_data:
        lines.append("  {")
        lines.append(f"    sym:       'NSE:{s['sym']}-EQ',")
        lines.append(f"    prevClose: {s['c']:.2f},")
        lines.append(f"    openPrice: null,")
        lines.append(f"    tcp:       {s['pv']['upper']:.2f},")
        lines.append(f"    bcp:       {s['pv']['lower']:.2f},")
        lines.append(f"    r1:        {s['pv']['r1']:.2f},")
        lines.append(f"    s1:        {s['pv']['s1']:.2f},")
        lines.append(f"    pdh:       {s['pdh']:.2f},")
        lines.append(f"    pdl:       {s['pdl']:.2f},")
        lines.append(f"    gapType:   null,")
        lines.append("  },")
    lines.append("];")
    lines.append("")
    lines.append("module.exports = stocks;")

    with open("exports/cpr-watchlist.js", "w") as f:
        f.write("\n".join(lines))
    print(f"[export] ✅ Exported {len(stocks_data)} stocks to exports/cpr-watchlist.js")


def main():
    print("Starting scan...")
    ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
    print(f"Time: {ist.strftime('%a %d %b %Y %I:%M %p IST')}")
    print(f"Email configured: gmail={'yes' if GMAIL_ADDRESS else 'NO'} pass={'yes' if GMAIL_APP_PASSWORD else 'NO'} to={'yes' if REPORT_RECIPIENT else 'NO'}")

    tickers = [f"{s}.NS" for s in STOCKS]
    print(f"Downloading {len(tickers)} tickers...")
    try:
        df = yf.download(tickers, period="10d", group_by='ticker',
                         auto_adjust=False, progress=False, threads=True, timeout=90)
    except Exception as e:
        send_email_text("CPR Scanner Error", f"yfinance error: {e}")
        sys.exit(1)
    if df is None or df.empty:
        send_email_text("CPR Scanner Error", "yfinance returned empty data")
        sys.exit(1)

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
                NSE_HOLIDAYS = {
                    datetime.date(2025, 1, 26),   # Republic Day
                    datetime.date(2025, 2, 19),   # Chhatrapati Shivaji Maharaj Jayanti
                    datetime.date(2025, 3, 14),   # Holi
                    datetime.date(2025, 3, 31),   # Id-Ul-Fitr (Ramzan Eid)
                    datetime.date(2025, 4, 10),   # Shri Ram Navami
                    datetime.date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
                    datetime.date(2025, 4, 18),   # Good Friday
                    datetime.date(2025, 5, 1),    # Maharashtra Day
                    datetime.date(2025, 6, 7),    # Shri Guru Granth Sahib Ji birthday
                    datetime.date(2025, 6, 26),   # Eid al-Adha (Bakri Eid)
                    datetime.date(2025, 8, 15),   # Independence Day
                    datetime.date(2025, 8, 27),   # Ganesh Chaturthi
                    datetime.date(2025, 10, 2),   # Gandhi Jayanti
                    datetime.date(2025, 10, 21),  # Diwali (Laxmi Pujan)
                    datetime.date(2025, 10, 22),  # Diwali (Balipratipada)
                    datetime.date(2025, 11, 5),   # Prakash Gurpurb Sri Guru Nanak Dev Ji
                    datetime.date(2025, 12, 25),  # Christmas
                }
                d_today = stock_df.index[-1]
                d_tomorrow = d_today + pd.tseries.offsets.BDay(1)
                while d_tomorrow.date() in NSE_HOLIDAYS:
                    d_tomorrow += pd.tseries.offsets.BDay(1)
                tomorrow_label = d_tomorrow.strftime("%d-%m-%Y")
                print(f"Target: {tomorrow_label}")

            today_cpr    = calc_cpr(float(day_yday['High']),  float(day_yday['Low']),  float(day_yday['Close']))
            tomorrow_cpr = calc_cpr(float(day_today['High']), float(day_today['Low']), float(day_today['Close']))

            if (tomorrow_cpr['upper'] <= today_cpr['upper'] and
                tomorrow_cpr['lower'] >= today_cpr['lower']):
                w_pct = (tomorrow_cpr['width'] / float(day_today['Close'])) * 100
                pp = (float(day_today['High']) + float(day_today['Low']) + float(day_today['Close'])) / 3
                r1 = 2 * pp - float(day_today['Low'])
                s1 = 2 * pp - float(day_today['High'])
                tomorrow_cpr['r1'] = r1
                tomorrow_cpr['s1'] = s1
                inside.append({
                    'sym': sym,
                    'w_pct': w_pct,
                    'c': float(day_today['Close']),
                    'pv': tomorrow_cpr,
                    'pdh': float(day_today['High']),
                    'pdl': float(day_today['Low']),
                })
        except Exception:
            continue

    inside.sort(key=lambda x: x['w_pct'])
    print(f"Found {len(inside)} inside CPR stocks")

    if not inside:
        send_email_text(
            f"Inside CPR Stock List — {tomorrow_label}",
            f"<b>Inside CPR Stock List</b><br>For: {tomorrow_label}<br><br>No inside CPR stocks today."
        )
        return

    syms = [s['sym'] for s in inside]
    print(f"Stocks: {syms}")

    # Export JS watchlist for downstream tools (signal bot etc)
    export_watchlist_js(inside, tomorrow_label)

    # Generate and send poster image via email
    img_buf = make_poster(syms, tomorrow_label)
    subject = f"📊 Inside CPR Stock List — {tomorrow_label}"
    body = (
        f"<h2>Inside CPR Stock List</h2>"
        f"<p>For next trading session: <b>{tomorrow_label}</b></p>"
        f"<p>Total stocks: <b>{len(syms)}</b></p>"
        f"<p>See attached poster image.</p>"
        f"<p><i>Happy Price Action Trading 📈</i></p>"
    )
    send_email_photo(img_buf, subject, body)


if __name__ == "__main__":
    main()
