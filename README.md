# BIST Breakout Tarama Botu

Her iş günü 18:15'te BIST hisselerini tarar, koşulları sağlayanları Telegram'a gönderir.

## Kriterler
- Hacim ≥ 3x (20 günlük ortalama)
- 60 günlük direnç kırılımı
- 200 günlük ortalama üstü
- RSI 50–75 arası

---

## Kurulum (Railway)

### 1. Telegram Bot oluştur
1. Telegram'da **@BotFather**'a yaz
2. `/newbot` komutu ver, bot adı belirle
3. Sana verilen **TOKEN'ı** kopyala
4. Bota bir mesaj gönder (herhangi bir şey)
5. Şu adresi aç (TOKEN'ı yerine koy):
   `https://api.telegram.org/botTOKEN/getUpdates`
6. Çıkan JSON'da `"chat":{"id":...}` kısmındaki **CHAT_ID**'yi al

### 2. GitHub'a yükle
1. github.com → **New repository** → "bist-tarama"
2. Bu klasördeki tüm dosyaları yükle

### 3. Railway'e deploy et
1. railway.app → **New Project** → **Deploy from GitHub repo**
2. Az önce oluşturduğun repoyu seç
3. **Variables** sekmesine gir, şu değişkenleri ekle:

| Değişken | Değer |
|---|---|
| `TELEGRAM_TOKEN` | BotFather'dan aldığın token |
| `TELEGRAM_CHAT_ID` | getUpdates'ten aldığın ID |

### 4. İsteğe bağlı parametreler
Bunları da Variables'a ekleyebilirsin (eklemezsen varsayılan değerler kullanılır):

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `HACIM_CARPAN` | 3 | Hacim patlaması eşiği |
| `BREAKOUT_GUN` | 60 | Direnç kırılımı periyodu |
| `MA_UZUN` | 200 | Uzun vade hareketli ortalama |
| `RSI_ALT` | 50 | RSI alt sınırı |
| `RSI_UST` | 75 | RSI üst sınırı |

### 5. Deploy'u başlat
- Railway otomatik deploy eder
- **Logs** sekmesinden çalıştığını kontrol et
- "Zamanlayıcı başladı" mesajını görürsen hazır

---

## Test etmek için
Railway Variables'a şunu ekle:
`TEST_MODE = 1`

Sonra Logs'ta hata yoksa bot çalışıyor demektir.
Gerçek tarama her iş günü 18:15'te otomatik çalışır.
