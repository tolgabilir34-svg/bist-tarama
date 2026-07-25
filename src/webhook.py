import os
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID  = os.environ["TELEGRAM_CHAT_ID"]
WEBHOOK_SECRET    = os.environ.get("WEBHOOK_SECRET", "")  # İsteğe bağlı güvenlik


def telegram_gonder(mesaj):
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


class WebhookHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        log.info(f"HTTP {args[0]} {args[1]}")

    def do_GET(self):
        # Sağlık kontrolü
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"BIST Tarama Botu - Aktif")

    def do_POST(self):
        try:
            uzunluk  = int(self.headers.get("Content-Length", 0))
            ham_veri = self.rfile.read(uzunluk).decode("utf-8")
            log.info(f"Webhook alındı: {ham_veri[:200]}")

            # Güvenlik kontrolü
            if WEBHOOK_SECRET:
                gelen_secret = self.headers.get("X-Secret", "")
                if gelen_secret != WEBHOOK_SECRET:
                    self.send_response(403)
                    self.end_headers()
                    return

            # TradingView JSON veya düz metin gönderebilir
            try:
                veri = json.loads(ham_veri)
                sembol   = veri.get("ticker", "?")
                fiyat    = veri.get("close", "?")
                mesaj_tv = veri.get("message", "")
                zaman    = veri.get("time", "")
            except Exception:
                # Düz metin geldi
                sembol   = "?"
                fiyat    = "?"
                mesaj_tv = ham_veri
                zaman    = ""

            simdi = datetime.now().strftime("%d.%m.%Y %H:%M")

            mesaj = (
                f"🔔 <b>TradingView Sinyali — {simdi}</b>\n\n"
                f"📌 <b>Hisse:</b> {sembol}\n"
                f"💰 <b>Fiyat:</b> {fiyat} TL\n"
            )
            if mesaj_tv:
                mesaj += f"📝 <b>Mesaj:</b> {mesaj_tv}\n"
            if zaman:
                mesaj += f"🕐 <b>Bar zamanı:</b> {zaman}\n"

            mesaj += "\n<i>⚠️ Yatırım tavsiyesi değildir.</i>"

            telegram_gonder(mesaj)
            log.info(f"Sinyal Telegram'a gönderildi: {sembol}")

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        except Exception as e:
            log.error(f"Webhook hatası: {e}")
            self.send_response(500)
            self.end_headers()


def webhook_baslat():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    log.info(f"Webhook sunucusu port {port}'de başladı")
    server.serve_forever()


if __name__ == "__main__":
    webhook_baslat()
