import os, re, json, time, pathlib, requests
from playwright.sync_api import sync_playwright

URL = os.getenv("TOKO_URL")
BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
STATE_FILE = pathlib.Path("last_status.txt")

def send_tele(msg: str):
    if not (BOT and CHAT): 
        print("Skip Telegram: token/chat_id kosong")
        return
    requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                  data={"chat_id": CHAT, "text": msg, "disable_web_page_preview": True, "parse_mode": "HTML"})

def read_last():
    return STATE_FILE.read_text().strip() if STATE_FILE.exists() else ""

def write_last(s: str):
    STATE_FILE.write_text(s)

def check_stock(page) -> str:
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    html = page.content().lower()

    def contains(patterns):
        return any(p in html for p in patterns)

    if contains(["ingatkan saya", "stok habis", ">habis<"]):
        return "SOLD_OUT"

    # Cek tombol beli/keranjang
    buy_keywords = ["beli langsung", "+ Keranjang", "tambah ke keranjang", "beli", "masukkan keranjang", "add to cart", "add to bag"]
    if contains(buy_keywords):
        return "IN_STOCK"

    # Coba sniff angka stok dari json
    m = re.search(r'"stock"\s*:\s*(\d+)', html)
    if m and int(m.group(1)) > 0:
        return "IN_STOCK"

    # Terakhir: cek disabled state tombol
    if contains(['aria-disabled="true"', "disabled"]):
        return "SOLD_OUT"

    # default konservatif
    return "UNKNOWN"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
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
