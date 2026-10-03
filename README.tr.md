# Marketing Campaign Intelligence (Pazarlama Kampanya Analitiği)

[English](README.md) · **Türkçe**

Hangi pazarlama kampanyaları sadece tıklama ve ciro değil, *kârlı ve tekrar alışveriş yapan* müşteri getiriyor? Bu proje 5 kanal ve 13 kampanya için CAC, ROAS, kâr ve LTV hesaplar, sonuçları Streamlit dashboard'u ve Power BI modeliyle gösterir.

**Teknolojiler:** Python (pandas) · SQL (SQLite) · Streamlit · Plotly · Power BI

> **Veri sentetiktir.** Kanal bazında harcama ve müşteri bazında gelir içeren herkese açık veri olmadığı için veri, seed'li bir simülatörle üretilir ([`src/generate_data.py`](src/generate_data.py)). Kanal davranışları kodda yazılmış varsayımlardır. Bu reponun değeri tam sayılar değil, **yöntem ve pipeline**'dır.

## Dashboard

![Genel bakış](docs/screenshots/overview.png)

| Kanallar | Kampanyalar | Segmentler |
|---|---|---|
| ![Kanallar](docs/screenshots/channels.png) | ![Kampanyalar](docs/screenshots/campaigns.png) | ![Segmentler](docs/screenshots/segments.png) |

## Temel bulgular (2025, TRY)

Portföy: **1,82M harcama → 11,64M gelir → 3,76M kâr**, ücretli ROAS 4,57x, ücretli CAC 224 TL.

1. **Ciro ≠ kâr.** Google *Search – Generic* ciroda 6. ama kârda sonuncu (−38K TL).
2. **Dönüşüm tuzağı.** TikTok *Spark Ads* %5,2 dönüşüm sağlar (ortalama %4,7), ama müşterileri 90 günde 432 TL ortalama yerine sadece 181 TL değer üretir (%19 tekrar oranı, %19 iade). TikTok genel olarak 2,3x ROAS'a rağmen zarar eder.
3. **Segmentler.** 35–44 yaş Moda alıcıları Email, Google ve Meta'da en iyi segmenttir. 18–24 Kozmetik Meta'da zarar ettirir.
4. **Bütçe kaydırma.** Harcamanın %30'unu düşük LTV:CAC kampanyalardan taşımak, ek harcama tarihsel verimliliğin yaklaşık %59'u ve üzerinde dönerse kârlıdır. Ölçeklemeden önce test edilmelidir.

![Ciro vs kâr](reports/figures/02_campaign_revenue_vs_profit.png)
![Dönüşüm vs LTV](reports/figures/04_conversion_vs_ltv.png)

Tam rapor: [`reports/findings.md`](reports/findings.md) (İngilizce)

## Nasıl çalışır

- **Veri:** `campaigns_daily` (gün × kampanya), `customers`, `orders` (last-click atıf).
- **Metrikler:** CTR, CPC, CPL, CPA, dönüşüm oranı, CAC, ROAS, kâr, LTV (90/180 gün), LTV:CAC.
- **Temel kararlar:** CPA tüm atfedilen siparişlere, CAC sadece yeni müşteriye bölünür · LTV yalnızca tam pencere boyunca gözlemlenen müşterilerle hesaplanır (sahte sıfır yok) · ana ROAS/CAC sadece ücretli kanallar içindir, organiğin medya maliyeti yoktur.
- **SQL:** `sql/` altında 4 sorgu (CTE, window function) · **Power BI:** `powerbi/data/` altında yıldız şema, DAX ölçüleri [`docs/powerbi_guide.md`](docs/powerbi_guide.md) içinde.

## Çalıştırma

```bash
pip install -r requirements.txt
make all          # veri → analiz → grafikler
make dashboard    # Streamlit uygulamasını aç
make test         # 8 test
```
`make` yoksa: `python -m src.generate_data && python -m src.marts && python -m src.analysis`

