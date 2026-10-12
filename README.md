# Huzur Vakti — şehir sayfaları

https://chucky-42.github.io/huzur-vakti/

Her şehir için o şehrin namaz vakitleri (bugün + ay tablosu), kıble açısı ve uygulamanın mağaza bağlantıları; 11 dilde.

- **Vakitler burada hesaplanmaz.** `data/times.json` uygulama deposundaki `tool/export_web_times.dart` ile, uygulamanın kendi hesap motoruyla üretilir; site ile uygulama aynı vakti gösterir.
- `python build.py` → `docs/` (GitHub Pages `main` dalının `docs/` klasöründen yayınlar).
- Bilgisayardaki **HuzurSiteAylik** görevi her ayın 1'inde `yenile.py` ile yeniden üretip gönderir (ay tablosu güncel kalsın diye). Sayfadaki betik "bugün"ü ziyaretçinin anına göre ilerletir. (GitHub Actions ile yapmak için `gh` belirtecine `workflow` izni gerekir.)

## Veriyi yenilemek (2027 bitmeden)

Uygulama deposunda (`kod/`):

```
HUZUR_WEB_CITIES=../site/data/cities.json HUZUR_WEB_OUT=../site/data/times.json \
HUZUR_WEB_FROM=2027-11-01 HUZUR_WEB_TO=2028-12-31 flutter test tool/export_web_times.dart
```

Şehir eklemek: `data/cities.json`'a uygulamanın şehir kimliğini (`ÜLKE:Ad`, ör. `SA:Mekke`) ve sayfa dilini ekleyip dışa aktarımı yeniden çalıştır.
