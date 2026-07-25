import os
import time
import math
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BB_PERIYOT    = int(os.environ.get("BB_PERIYOT", "20"))
BB_CARPAN     = float(os.environ.get("BB_CARPAN", "2.0"))
SQUEEZE_PCT   = int(os.environ.get("SQUEEZE_PCT", "20"))
SQUEEZE_BARS  = int(os.environ.get("SQUEEZE_BARS", "50"))
HACIM_CARPAN  = float(os.environ.get("HACIM_CARPAN", "2.0"))
HACIM_PERIYOT = int(os.environ.get("HACIM_PERIYOT", "20"))
BREAKOUT_BARS = int(os.environ.get("BREAKOUT_BARS", "30"))
BATCH_SIZE    = int(os.environ.get("BATCH_SIZE", "50"))  # Kaçar kaçar indirilsin

BIST_SYMBOLS_URL = "https://raw.githubusercontent.com/ahmeterenodaci/Istanbul-Stock-Exchange--BIST--including-symbols-and-logos/main/bist.min.json"


def bist_semboller():
    try:
        r = requests.get(BIST_SYMBOLS_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        semboller = [item["symbol"] + ".IS" for item in data if "symbol" in item]
        log.info(f"{len(semboller)} BIST sembolü yüklendi")
    except Exception as e:
        log.warning(f"Sembol listesi alınamadı ({e}), yedek liste kullanılıyor")
        yedek = [
            "AKBNK","GARAN","ISCTR","VAKBN","HALKB","YKBNK",
            "THYAO","PGSUS","BIMAS","MGROS","SASA","KCHOL",
            "SAHOL","EREGL","ARCLK","TUPRS","TOASO","FROTO",
            "DOAS","EKGYO","ENKAI","PETKM","TCELL","TTKOM",
            "ASELS","KOZAL","KRDMD","CCOLA","AEFES","BIGEN",
        ]
        semboller = [s + ".IS" for s in yedek]

    ekstra = os.environ.get("EKSTRA_SEMBOLLER", "")
    if ekstra:
        ekstra_list = [s.strip().upper() + ".IS" for s in ekstra.split(",") if s.strip()]
        onceki = len(semboller)
        semboller = list(dict.fromkeys(semboller + ekstra_list))
        yeni = len(semboller) - onceki
        if yeni > 0:
            log.info(f"{yeni} ekstra sembol eklendi: {ekstra_list}")

    return semboller


def toplu_indir(semboller, period="300d", interval="1d"):
    """Hisseleri batch halinde toplu indirir — rate limit riskini azaltır."""
    tum_veri = {}
    for i in range(0, len(semboller), BATCH_SIZE):
        batch = semboller[i:i + BATCH_SIZE]
        log.info(f"Batch indiriliyor: {i+1}–{min(i+BATCH_SIZE, len(semboller))} / {len(semboller)}")
        try:
            df = yf.download(
                batch,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                group_by="ticker",
            )
            for sembol in batch:
                try:
                    if len(batch) == 1:
                        tum_veri[sembol] = df
                    else:
                        tum_veri[sembol] = df[sembol]
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"Batch hatası ({batch[0]}...): {e}")
        time.sleep(2)  # Batch arası bekleme
    return tum_veri


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


def hisse_analiz(sembol, df):
    try:
        if df is None or len(df) < SQUEEZE_BARS + BB_PERIYOT + 5:
            return None

        kapanis = df["Close"].dropna()
        hacim   = df["Volume"].dropna()

        if len(kapanis) < SQUEEZE_BARS + BB_PERIYOT + 5:
            return None

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

        fiyat_bugun = float(kapanis.iloc[-1])
        fiyat_dun   = float(kapanis.iloc[-2])

        if math.isnan(fiyat_bugun) or math.isnan(fiyat_dun) or fiyat_dun == 0:
            return None

        degisim = ((fiyat_bugun - fiyat_dun) / fiyat_dun) * 100

        return {
            "sembol":      sembol.replace(".IS", ""),
            "fiyat":       round(fiyat_bugun, 2),
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

    # Toplu indirme
    tum_veri = toplu_indir(semboller, period="300d", interval="1d")
    log.info(f"{len(tum_veri)} hisse verisi indirildi")

    sonuclar = []
    for sembol, df in tum_veri.items():
        sonuc = hisse_analiz(sembol, df)
        if sonuc:
            sonuclar.append(sonuc)

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
