import schedule
import time
import logging
from tarama import tarama_yap

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# BIST kapanış sonrası 18:15 UTC+3 = 15:15 UTC
schedule.every().monday.at("15:15").do(tarama_yap)
schedule.every().tuesday.at("15:15").do(tarama_yap)
schedule.every().wednesday.at("15:15").do(tarama_yap)
schedule.every().thursday.at("15:15").do(tarama_yap)
schedule.every().friday.at("15:15").do(tarama_yap)

log.info("Zamanlayıcı başladı — her iş günü 18:15 (TR) tarama yapılacak")

while True:
    schedule.run_pending()
    time.sleep(30)
