import os, re, time, pathlib, requests
from playwright.sync_api import sync_playwright

URL = os.getenv("TOKO_URL")
BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = pathlib.Path("last_status.txt")

def send_tele(msg: str):
    if not (BOT and CHAT):
        print("Skip Telegram: token/chat_id kosong")
        return
    requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id": CHAT, "text": msg, "disable_web_page_preview": True, "parse_mode": "HTML"},
        timeout=15
    )

def read_last():
    return STATE_FILE.read_text().strip() if STATE_FILE.exists() else ""

def write_last(s: str):
    STATE_FILE.write_text(s)

def check_stock(page) -> str:
    for attempt in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            break
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2)

    page.wait_for_timeout(2500)
    html = page.content().lower()

    def contains(patterns): return any(p in html for p in patterns)

    if contains(["ingatkan saya", "stok habis", ">habis<"]):
        return "SOLD_OUT"

    buy_keywords = [
        "beli langsung",
        "masukkan keranjang",
        "add to cart",
        "add to bag"
    ]
    if contains(buy_keywords):
        return "IN_STOCK"

    # Coba sniff angka stok di JSON inline
    m = re.search(r'"stock"\s*:\s*(\d+)', html)
    if m and int(m.group(1)) > 0:
        return "IN_STOCK"

    # Tombol disabled → kemungkinan habis
    if contains(['aria-disabled="true"', "disabled"]):
        return "SOLD_OUT"

    return "UNKNOWN"

def main():
    if not URL:
        raise SystemExit("ENV TOKO_URL kosong")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
            locale="id-ID",
            extra_http_headers={
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Upgrade-Insecure-Requests": "1",
            },
        )
        page = ctx.new_page()
        status = check_stock(page)
        browser.close()

    last = read_last()
    if status != last:
        write_last(status)
        if status == "IN_STOCK":
            send_tele(f"🔥 <b>STOK TERSEDIA!</b>\n{URL}")
        elif status == "SOLD_OUT" and last:
            send_tele(f"Stok habis lagi.\n{URL}")
    print(f"Status: {status}, Last: {last}")

if __name__ == "__main__":
    main()
