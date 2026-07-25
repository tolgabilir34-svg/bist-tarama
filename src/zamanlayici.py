import threading
import logging
from webhook import webhook_baslat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

log.info("BIST Tarama Botu başladı")
log.info("Mod: TradingView Webhook")
log.info("TradingView sinyalleri beklenyor...")

# Webhook sunucusunu başlat (ana thread)
webhook_baslat()
