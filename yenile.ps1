# Ayın 1'inde HuzurSiteAylik görevi çalıştırır: sayfaları yeniden üretir (ay
# tablosu yeni aya geçsin) ve GitHub Pages'e gönderir. Vakit verisinin bitmesine
# 60 günden az kaldıysa Telegram'a bir kez haber verir; veri uygulama deposundaki
# tool/export_web_times.dart ile yenilenir (README).
Set-Location $PSScriptRoot
$log = Join-Path $PSScriptRoot 'yenile.log'
function Log($m) { Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) -Encoding utf8 }
$python = 'C:\Users\lutfu\AppData\Local\Programs\Python\Python312\python.exe'
$env:PYTHONIOENCODING = 'utf-8'

$out = & $python build.py 2>&1
Log ($out -join ' ')
if ($LASTEXITCODE -ne 0) { Log 'HATA: build.py başarısız'; exit 1 }

$to = (Get-Content data\times.json -Raw -Encoding utf8 | & $python -c "import json,sys; print(json.load(sys.stdin)['to'])").Trim()
$left = ([datetime]::ParseExact($to, 'yyyy-MM-dd', $null) - (Get-Date)).Days
if ($left -lt 60) {
  Log "UYARI: vakit verisi $to tarihinde bitiyor ($left gün)"
  & $python -c "import sys; sys.path.insert(0, r'C:\dev\apps\huzur_vakti\araclar'); from station import telegram; telegram.send('🌐 Huzur Vakti sitesi: şehir sayfalarının vakit verisi $to tarihinde bitiyor ($left gün kaldı). Uygulama deposunda export_web_times.dart yeniden çalıştırılmalı (site\\README.md).', dedupe_key='site-veri-bitiyor', dedupe_seconds=86400*25)"
}

git add -A docs 2>&1 | Out-Null
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Log 'değişiklik yok'; exit 0 }
git commit -q -m ("Aylık yeniden üretim {0:yyyy-MM-dd}" -f (Get-Date)) 2>&1 | Out-Null
$push = git push -q origin main 2>&1
if ($LASTEXITCODE -ne 0) { Log ("HATA: push başarısız: " + ($push -join ' ')); exit 1 }
Log 'gönderildi'
