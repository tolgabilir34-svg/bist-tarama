import os
import time
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- Parametreler (Pine Script ile aynı) ---
BB_PERIYOT    = int(os.environ.get("BB_PERIYOT", "20"))
BB_CARPAN     = float(os.environ.get("BB_CARPAN", "2.0"))
SQUEEZE_PCT   = int(os.environ.get("SQUEEZE_PCT", "20"))
SQUEEZE_BARS  = int(os.environ.get("SQUEEZE_BARS", "50"))
HACIM_CARPAN  = float(os.environ.get("HACIM_CARPAN", "2.0"))
HACIM_PERIYOT = int(os.environ.get("HACIM_PERIYOT", "20"))
BREAKOUT_BARS = int(os.environ.get("BREAKOUT_BARS", "30"))

# Sembol listesi kaynağı
BIST_SYMBOLS_URL = "https://raw.githubusercontent.com/ahmeterenodaci/Istanbul-Stock-Exchange--BIST--including-symbols-and-logos/main/bist.min.json"


def bist_semboller():
    """Tüm BIST hisselerini GitHub'dan çeker (537 hisse)."""
    try:
        r = requests.get(BIST_SYMBOLS_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        semboller = [item["symbol"] + ".IS" for item in data if "symbol" in item]
        log.info(f"{len(semboller)} BIST sembolü yüklendi")
        return semboller
    except Exception as e:
        log.warning(f"Sembol listesi alınamadı ({e}), yedek liste kullanılıyor")
        yedek = [
            "AKBNK","GARAN","ISCTR","VAKBN","HALKB","YKBNK",
            "THYAO","PGSUS","BIMAS","MGROS","SASA","KCHOL",
            "SAHOL","EREGL","ARCLK","TUPRS","TOASO","FROTO",
            "DOAS","EKGYO","ENKAI","PETKM","TCELL","TTKOM",
            "ASELS","KOZAL","KRDMD","CCOLA","AEFES","BIGEN",
        ]
        return [s + ".IS" for s in yedek]


def bb_width_hesapla(kapanis):
    basis = kapanis.rolling(BB_PERIYOT).mean()
    std   = kapanis.rolling(BB_PERIYOT).std()
    upper = basis + BB_CARPAN * std
    lower = basis - BB_CARPAN * std
    return (upper - lower) / basis


def is_squeezed(bb_width_serisi, idx):
    pencere = bb_width_serisi.iloc[max(0, idx - SQUEEZE_BARS): idx + 1]
    if len(pencere) < SQUEEZE_BARS:
        return False
    esik = pencere.quantile(SQUEEZE_PCT / 100)
    return float(bb_width_serisi.iloc[idx]) <= esik


def hisse_analiz(sembol):
    try:
        df = yf.download(
            sembol,
            period="300d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if df is None or len(df) < SQUEEZE_BARS + BB_PERIYOT + 5:
            return None

        df      = df.copy()
        kapanis = df["Close"].squeeze()
        hacim   = df["Volume"].squeeze()

        # Koşul 1 — Önceki barda BB sıkışması
        bb_w    = bb_width_hesapla(kapanis)
        dun_idx = len(kapanis) - 2
        if not is_squeezed(bb_w, dun_idx):
            return None

        # Koşul 2 — Hacim patlaması
        hacim_ort        = hacim.rolling(HACIM_PERIYOT).mean()
        bugun_hacim_oran = float(hacim.iloc[-1]) / float(hacim_ort.iloc[-2])
        if bugun_hacim_oran < HACIM_CARPAN:
            return None

        # Koşul 3 — 30 günlük fiyat kırılımı
        onceki_zirve = kapanis.iloc[-(BREAKOUT_BARS + 1):-1].max()
        if float(kapanis.iloc[-1]) <= float(onceki_zirve):
            return None

        degisim = ((float(kapanis.iloc[-1]) - float(kapanis.iloc[-2]))
                   / float(kapanis.iloc[-2])) * 100

        return {
            "sembol":      sembol.replace(".IS", ""),
            "fiyat":       round(float(kapanis.iloc[-1]), 2),
            "degisim":     round(degisim, 2),
            "hacim_oran":  round(bugun_hacim_oran, 1),
            "bb_genislik": round(float(bb_w.iloc[-2]) * 100, 2),
        }

    except Exception as e:
        log.debug(f"{sembol} atlandı: {e}")
        return None


def telegram_gonder(mesaj):
    url     = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


def tarama_yap():
    log.info("Tarama başladı")
    semboller = bist_semboller()
    sonuclar  = []

    for i, sembol in enumerate(semboller):
        if i % 50 == 0:
            log.info(f"{i}/{len(semboller)} işlendi")
        sonuc = hisse_analiz(sembol)
        if sonuc:
            sonuclar.append(sonuc)
        time.sleep(0.15)

    log.info(f"Tarama bitti — {len(sonuclar)} hisse koşulları sağladı")

    tarih = datetime.now().strftime("%d.%m.%Y")

    if not sonuclar:
        mesaj = (
            f"📊 <b>BIST Sıkışma Kırılım Tarama — {tarih}</b>\n\n"
            f"Bugün koşulları sağlayan hisse bulunamadı.\n\n"
            f"<i>Evren: Tüm BIST ({len(semboller)} hisse) | "
            f"BB sıkışması | Hacim ≥{HACIM_CARPAN}x | {BREAKOUT_BARS}G kırılım</i>"
        )
    else:
        sonuclar.sort(key=lambda x: x["hacim_oran"], reverse=True)

        satirlar = []
        for s in sonuclar:
            ok = "🟢" if s["degisim"] >= 0 else "🔴"
            satirlar.append(
                f"{ok} <b>{s['sembol']}</b>  "
                f"{s['fiyat']} TL  "
                f"({'+' if s['degisim'] >= 0 else ''}{s['degisim']}%)  "
                f"| Hacim: {s['hacim_oran']}x  BB: %{s['bb_genislik']}"
            )

        mesaj = (
            f"📊 <b>BIST Sıkışma Kırılım Tarama — {tarih}</b>\n"
            f"<i>{len(sonuclar)} hisse / {len(semboller)} tarandı</i>\n\n"
            + "\n".join(satirlar)
            + f"\n\n<i>BB sıkışması (önceki bar) | Hacim ≥{HACIM_CARPAN}x | {BREAKOUT_BARS}G kırılım</i>"
            + "\n<i>⚠️ Yatırım tavsiyesi değildir.</i>"
        )

    telegram_gonder(mesaj)
    log.info("Telegram mesajı gönderildi")


if __name__ == "__main__":
    tarama_yap()
