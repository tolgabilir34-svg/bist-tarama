import os
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- Parametreler ---
HACIM_CARPAN = float(os.environ.get("HACIM_CARPAN", "3"))       # Ortalama hacmin kaç katı
BREAKOUT_GUN = int(os.environ.get("BREAKOUT_GUN", "60"))        # Kaç günlük direnç kırılımı
MA_UZUN = int(os.environ.get("MA_UZUN", "200"))                 # Uzun vade MA
RSI_ALT = float(os.environ.get("RSI_ALT", "50"))
RSI_UST = float(os.environ.get("RSI_UST", "75"))
HACIM_PERIYOT = int(os.environ.get("HACIM_PERIYOT", "20"))      # Hacim ortalaması periyodu


def bist_semboller():
    """BIST hisselerini çeker."""
    url = "https://raw.githubusercontent.com/nicholasgasior/bist-symbols/main/symbols.txt"
    try:
        r = requests.get(url, timeout=10)
        semboller = [s.strip() + ".IS" for s in r.text.splitlines() if s.strip()]
        log.info(f"{len(semboller)} sembol yüklendi (GitHub)")
        return semboller
    except Exception:
        log.warning("GitHub listesi alınamadı, yedek liste kullanılıyor")
        yedek = [
            "AKBNK","GARAN","ISCTR","VAKBN","HALKB","YKBNK",
            "THYAO","PGSUS","BIMAS","MGROS","MIGROS","SASA",
            "KCHOL","SAHOL","EREGL","ARCLK","TUPRS","TOASO",
            "FROTO","DOAS","EKGYO","ENKAI","PETKM","TCELL",
            "TTKOM","ASELS","KOZAL","KRDMD","CCOLA","AEFES",
        ]
        return [s + ".IS" for s in yedek]


def rsi_hesapla(seri, periyot=14):
    delta = seri.diff()
    kazan = delta.clip(lower=0)
    kayip = -delta.clip(upper=0)
    ort_kazan = kazan.ewm(com=periyot - 1, adjust=False).mean()
    ort_kayip = kayip.ewm(com=periyot - 1, adjust=False).mean()
    rs = ort_kazan / ort_kayip
    return 100 - (100 / (1 + rs))


def hisse_analiz(sembol):
    """Tek hisseyi analiz eder, koşullar sağlanıyorsa dict döner, yoksa None."""
    try:
        df = yf.download(
            sembol,
            period="400d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if df is None or len(df) < MA_UZUN + 10:
            return None

        df = df.copy()
        kapanis = df["Close"].squeeze()
        yuksek = df["High"].squeeze()
        hacim = df["Volume"].squeeze()

        # Koşul 1 — Hacim patlaması
        hacim_ort = hacim.rolling(HACIM_PERIYOT).mean()
        bugun_hacim_oran = (hacim.iloc[-1] / hacim_ort.iloc[-2])
        if bugun_hacim_oran < HACIM_CARPAN:
            return None

        # Koşul 2 — Breakout (dünkü N günlük zirveyi kırdı mı)
        onceki_zirve = yuksek.iloc[-(BREAKOUT_GUN + 1):-1].max()
        if kapanis.iloc[-1] <= onceki_zirve:
            return None

        # Koşul 3 — 200 günlük ortalama üstü
        ma200 = kapanis.rolling(MA_UZUN).mean()
        if kapanis.iloc[-1] <= ma200.iloc[-1]:
            return None

        # Koşul 4 — RSI filtresi
        rsi = rsi_hesapla(kapanis)
        bugun_rsi = rsi.iloc[-1]
        if not (RSI_ALT <= bugun_rsi <= RSI_UST):
            return None

        # Günlük değişim
        degisim = ((kapanis.iloc[-1] - kapanis.iloc[-2]) / kapanis.iloc[-2]) * 100

        return {
            "sembol": sembol.replace(".IS", ""),
            "fiyat": round(float(kapanis.iloc[-1]), 2),
            "degisim": round(float(degisim), 2),
            "hacim_oran": round(float(bugun_hacim_oran), 1),
            "rsi": round(float(bugun_rsi), 1),
        }

    except Exception as e:
        log.debug(f"{sembol} atlandı: {e}")
        return None


def telegram_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "HTML",
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


def tarama_yap():
    log.info("Tarama başladı")
    semboller = bist_semboller()
    sonuclar = []

    for i, sembol in enumerate(semboller):
        if i % 50 == 0:
            log.info(f"{i}/{len(semboller)} işlendi")
        sonuc = hisse_analiz(sembol)
        if sonuc:
            sonuclar.append(sonuc)
        time.sleep(0.15)  # yfinance rate limit

    log.info(f"Tarama bitti — {len(sonuclar)} hisse koşulları sağladı")

    tarih = datetime.now().strftime("%d.%m.%Y")

    if not sonuclar:
        mesaj = (
            f"📊 <b>BIST Breakout Tarama — {tarih}</b>\n\n"
            f"Bugün koşulları sağlayan hisse bulunamadı.\n\n"
            f"<i>Kriterler: Hacim ≥{HACIM_CARPAN}x | {BREAKOUT_GUN}G direnç kırılımı | MA{MA_UZUN} üstü | RSI {RSI_ALT}–{RSI_UST}</i>"
        )
    else:
        # Hacim oranına göre sırala
        sonuclar.sort(key=lambda x: x["hacim_oran"], reverse=True)

        satirlar = []
        for s in sonuclar:
            degisim_ok = "🟢" if s["degisim"] >= 0 else "🔴"
            satirlar.append(
                f"{degisim_ok} <b>{s['sembol']}</b>  "
                f"{s['fiyat']} TL  "
                f"({'+' if s['degisim'] >= 0 else ''}{s['degisim']}%)  "
                f"| Hacim: {s['hacim_oran']}x  RSI: {s['rsi']}"
            )

        mesaj = (
            f"📊 <b>BIST Breakout Tarama — {tarih}</b>\n"
            f"<i>{len(sonuclar)} hisse koşulları sağladı</i>\n\n"
            + "\n".join(satirlar)
            + f"\n\n<i>Kriterler: Hacim ≥{HACIM_CARPAN}x | {BREAKOUT_GUN}G direnç kırılımı | MA{MA_UZUN} üstü | RSI {RSI_ALT}–{RSI_UST}</i>"
            + "\n<i>⚠️ Yatırım tavsiyesi değildir.</i>"
        )

    telegram_gonder(mesaj)
    log.info("Telegram mesajı gönderildi")


if __name__ == "__main__":
    tarama_yap()
