"""Monthly rebuild, run by the HuzurSiteAylik scheduled task on the 1st.

Rebuilds docs/ so the printed month table moves to the new month, commits and
pushes it to GitHub Pages. When the timetable data is within 60 days of its
end it says so on Telegram (once every 25 days); the data is refreshed with
tool/export_web_times.dart in the app repo (see README.md).

Run with pythonw so the task opens no window.
"""
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / 'yenile.log'


def log(msg):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(f'{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n')


def run(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def main():
    build = run(sys.executable.replace('pythonw.exe', 'python.exe'), 'build.py')
    log((build.stdout + build.stderr).strip())
    if build.returncode != 0:
        log('HATA: build.py başarısız')
        return 1

    to = date.fromisoformat(json.loads((ROOT / 'data' / 'times.json').read_text(encoding='utf-8'))['to'])
    left = (to - date.today()).days
    if left < 60:
        log(f'UYARI: vakit verisi {to} tarihinde bitiyor ({left} gün)')
        sys.path.insert(0, r'C:\dev\apps\huzur_vakti\araclar')
        from station import telegram
        telegram.send(f'🌐 Huzur Vakti sitesi: şehir sayfalarının vakit verisi {to} tarihinde bitiyor ({left} gün kaldı). '
                      'Uygulama deposunda tool/export_web_times.dart yeniden çalıştırılmalı (site/README.md).',
                      dedupe_key='site-veri-bitiyor', dedupe_seconds=86400 * 25)

    run('git', 'add', '-A', 'docs')
    if run('git', 'diff', '--cached', '--quiet').returncode == 0:
        log('değişiklik yok')
        return 0
    run('git', 'commit', '-q', '-m', f'Aylık yeniden üretim {date.today():%Y-%m-%d}')
    push = run('git', 'push', '-q', 'origin', 'main')
    if push.returncode != 0:
        log(f'HATA: push başarısız: {push.stderr.strip()}')
        return 1
    log('gönderildi')
    return 0


if __name__ == '__main__':
    sys.exit(main())
