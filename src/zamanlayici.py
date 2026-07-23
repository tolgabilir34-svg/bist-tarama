import schedule
import time
import logging
from tarama import tarama_yap
from tarama_saatlik import tarama_yap_1h

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Günlük tarama — BIST kapanışı sonrası 18:15 TR (15:15 UTC) ──
for gun in ["monday","tuesday","wednesday","thursday","friday"]:
    getattr(schedule.every(), gun).at("15:15").do(tarama_yap)

# ── 1 Saatlik tarama — BIST açık saatlerinde her saat başı ──
# 10:00 – 18:00 TR = 07:00 – 15:00 UTC
for saat in ["07:05","08:05","09:05","10:05","11:05","12:05","13:05","14:05","15:05"]:
    for gun in ["monday","tuesday","wednesday","thursday","friday"]:
        getattr(schedule.every(), gun).at(saat).do(tarama_yap_1h)

log.info("Zamanlayıcı başladı")
log.info("  Günlük tarama : her iş günü 18:15 TR")
log.info("  1H tarama     : her iş günü 10:00–18:00 TR arası her saat başı")

while True:
    schedule.run_pending()
    time.sleep(30)
