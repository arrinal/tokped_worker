import os, re, time, pathlib, requests, json, hashlib
from playwright.sync_api import sync_playwright

URL = os.getenv("TOKO_URL")
BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
STATE_DIR = pathlib.Path("last_status")

def send_tele(msg: str):
    if not (BOT and CHAT):
        print("Skip Telegram: token/chat_id kosong")
        return
    requests.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        data={"chat_id": CHAT, "text": msg, "disable_web_page_preview": True, "parse_mode": "HTML"},
        timeout=15
    )

def _state_file_for(url: str) -> pathlib.Path:
    STATE_DIR.mkdir(exist_ok=True)
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return STATE_DIR / f"{url_hash}.txt"

def read_last(url: str):
    f = _state_file_for(url)
    return f.read_text().strip() if f.exists() else ""

def write_last(url: str, s: str):
    _state_file_for(url).write_text(s)

def parse_urls(raw: str):
    if not raw:
        return []
    raw = raw.strip()
    # JSON array input
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            return [u.strip() for u in arr if isinstance(u, str) and u.strip()]
        except Exception:
            pass
    # Fallback: split by newline or comma
    parts = []
    if "\n" in raw:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    elif "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        parts = [raw]
    return parts

def check_stock(page, url: str) -> str:
    use_page = page
    temp_page = None
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            use_page.goto(url, wait_until="domcontentloaded", timeout=60000)
            break
        except Exception as e:
            if attempt == max_attempts - 1:
                print(f"Navigation failed for {url}: {e}")
                if temp_page:
                    try:
                        temp_page.close()
                    except Exception:
                        pass
                return "UNKNOWN"
            time.sleep(min(10, 2 * (attempt + 1)))
            try:
                if temp_page:
                    temp_page.close()
                temp_page = page.context.new_page()
                use_page = temp_page
            except Exception:
                use_page = page

    use_page.wait_for_timeout(2500)
    html = use_page.content().lower()

    def contains(patterns): return any(p in html for p in patterns)

    status = "UNKNOWN"
    if contains(["ingatkan saya", "stok habis", ">habis<"]):
        status = "SOLD_OUT"
    else:
        buy_keywords = [
            "beli langsung",
            "masukkan keranjang",
            "add to cart",
            "add to bag"
        ]
        if contains(buy_keywords):
            status = "IN_STOCK"
        else:
            m = re.search(r'"stock"\s*:\s*(\d+)', html)
            if m and int(m.group(1)) > 0:
                status = "IN_STOCK"
            else:
                if contains(['aria-disabled="true"', "disabled"]):
                    status = "SOLD_OUT"

    if temp_page:
        try:
            temp_page.close()
        except Exception:
            pass
    return status

def main():
    if not URL:
        raise SystemExit("ENV TOKO_URL kosong")

    urls = parse_urls(URL)
    if not urls:
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
        for url in urls:
            try:
                status = check_stock(page, url)
            except Exception as e:
                print(f"Error while processing URL: {url} -> {e}")
                continue
            last = read_last(url)
            if status != last:
                write_last(url, status)
                if status == "IN_STOCK":
                    send_tele(f"🔥 <b>STOK TERSEDIA!</b>\n{url}")
                elif status == "SOLD_OUT" and last:
                    send_tele(f"Stok habis lagi.\n{url}")
            print(f"Status: {status}, Last: {last}, Url: {url}")
        browser.close()

if __name__ == "__main__":
    main()
