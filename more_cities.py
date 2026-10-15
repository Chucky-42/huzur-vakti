"""Adds the cities the app does not list to the site, from GeoNames.

The app ships 600 cities; people search for prayer times in thousands. A page
for "jadwal sholat bekasi" or "namaz time gujranwala" cannot exist while the
site only knows the app's list, so this reads GeoNames' cities15000 (CC BY 4.0)
and writes the largest towns of each country into data/cities.json as
coordinate entries. tool/export_web_times.dart computes them with the same
engine and the same country profile the app uses for a city in that country.

Names come from GeoNames' alternate names: the city's own script for the page
language (Lahore is لاہور on an Urdu page), and its English form for the slug.

    python more_cities.py            # rewrites data/cities.json
Data: C:\\dev\\apps\\huzur_vakti\\kaynaklar\\geonames (downloaded on first run).
"""
import io
import time
import unicodedata
import urllib.parse
import json
import math
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent
APP = ROOT.parent / 'kod'
GEO = ROOT.parent / 'kaynaklar' / 'geonames'
BASE = 'https://download.geonames.org/export/dump/'

# country -> (how many to add, the page language(s)). The page language is the
# one a searcher in that country types in; Germany, Azerbaijan, Uzbekistan and
# Bosnia get their own language now that the app speaks it.
QUOTA = {
    'TR': (220, ['tr']), 'ID': (180, ['id']), 'PK': (110, ['ur']), 'BD': (60, ['bn']),
    'EG': (60, ['ar']), 'NG': (50, ['en']), 'IR': (60, ['fa']), 'DZ': (45, ['ar']),
    'MA': (45, ['ar']), 'IQ': (40, ['ar']), 'SA': (40, ['ar']), 'MY': (45, ['ms']),
    'UZ': (30, ['uz']), 'AZ': (15, ['az']), 'DE': (70, ['de', 'tr']), 'FR': (40, ['fr']),
    'GB': (40, ['en']), 'NL': (15, ['tr']), 'BE': (10, ['fr']), 'AT': (10, ['de', 'tr']),
    'CH': (8, ['de']), 'BA': (15, ['bs']), 'KZ': (20, ['ru']), 'AF': (25, ['fa']),
    'SY': (20, ['ar']), 'YE': (15, ['ar']), 'SD': (20, ['ar']), 'TN': (15, ['ar']),
    'JO': (10, ['ar']), 'SN': (10, ['fr']), 'ML': (10, ['fr']), 'NE': (10, ['fr']),
    'TZ': (15, ['sw']), 'KE': (10, ['sw']), 'IN': (60, ['en']), 'US': (25, ['en']),
    'CA': (10, ['en']), 'AU': (6, ['en']), 'KW': (5, ['ar']), 'AE': (6, ['ar']),
    'OM': (6, ['ar']), 'LY': (10, ['ar']), 'SO': (8, ['ar']), 'TJ': (6, ['ru']),
    'KG': (6, ['ru']), 'TM': (5, ['ru']), 'XK': (6, ['tr']), 'MK': (6, ['tr']),
    'AL': (6, ['en']), 'SE': (6, ['en']), 'NO': (4, ['en']), 'DK': (4, ['en']),
}
# Countries whose existing app cities already have a page in another language
# that should be added in the new one too.
NEW_LANG_FOR_APP_CITIES = {'DE': 'de', 'AT': 'de', 'CH': 'de', 'AZ': 'az', 'UZ': 'uz', 'BA': 'bs'}
LANGS = ['tr', 'en', 'ar', 'fa', 'ur', 'bn', 'fr', 'id', 'ms', 'ru', 'sw', 'de', 'az', 'uz', 'bs']
# A town this close to one the app already lists is that city's suburb.
NEAR_KM = 12
SCRIPT = {'ar', 'fa', 'ur', 'bn', 'ru'}
BLOCK = {'Altstadt', 'Queens', 'The Bronx', 'Brooklyn', 'Manhattan', 'Staten Island', 'Eisenzicken'}
SCRIPT_RANGE = {'ar': (0x600, 0x6FF), 'fa': (0x600, 0x6FF), 'ur': (0x600, 0x6FF),
                'bn': (0x980, 0x9FF), 'ru': (0x400, 0x4FF)}


def fetch(name):
    GEO.mkdir(parents=True, exist_ok=True)
    path = GEO / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print('indiriliyor', name)
        path.write_bytes(urllib.request.urlopen(BASE + name, timeout=120).read())
    return path


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def app_cities():
    src = (APP / 'lib' / 'core' / 'city_data.dart').read_text(encoding='utf-8')
    out = []
    for m in re.finditer(r"City\('((?:[^'\\]|\\.)*)', (-?[\d.]+), (-?[\d.]+)(.*?)\)", src):
        rest = m.group(4)
        cc = re.search(r"country: '([A-Z]{2})'", rest)
        out.append((m.group(1).replace("\\'", "'"), float(m.group(2)), float(m.group(3)),
                    cc.group(1) if cc else 'TR'))
    return out


def clean(label):
    """One plain place name out of a label: "Barda, Azerbaijan", "Ümraniye
    (Türkiye'deki şehir)", "Kreisfreie Stadt Münster" and Arabic presentation
    forms all occur."""
    label = unicodedata.normalize('NFKC', label)
    label = re.sub(r'\s*\(.*?\)', '', label)
    label = re.sub(r',.*$', '', label)
    label = re.sub(r'^(Kreisfreie Stadt|Stadt|Kota|Kabupaten|Ville de|City of) ', '', label)
    label = re.sub(r' (Upazila|উপজেলা|জেলা|ইউনিয়ন|District|district|capital)$', '', label)
    return label.strip()


def wikidata_labels(ids):
    """geonameid -> {lang: label}, from Wikidata items that carry the GeoNames id.

    GeoNames' own alternate names are a pile: Mohammedia had "الهراويين" (a
    neighbourhood) among its Arabic names and Barda was "Bǝrdǝ" with the wrong
    letter. Wikidata's label is the one name per language that editors in that
    language settled on, so it comes first and GeoNames only fills gaps.
    """
    cache_path = GEO / 'wikidata_labels.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    todo = [i for i in ids if str(i) not in cache]
    langs = ' '.join(f'"{l}"' for l in LANGS)
    for start in range(0, len(todo), 150):
        chunk = todo[start:start + 150]
        values = ' '.join(f'"{i}"' for i in chunk)
        query = (f'SELECT ?gid ?label WHERE {{ VALUES ?gid {{ {values} }} ?item wdt:P1566 ?gid . '
                 f'?item rdfs:label ?label . FILTER(LANG(?label) IN ({langs.replace(" ", ", ")})) }}')
        url = 'https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={'User-Agent': 'HuzurVaktiSite/1.0 (huzurvaktiti.571@gmail.com)'})
        for attempt in range(4):
            try:
                rows = json.load(urllib.request.urlopen(req, timeout=90))['results']['bindings']
                break
            except Exception as e:  # rate limit or timeout: wait and retry
                print('wikidata yeniden', attempt, e)
                time.sleep(10 * (attempt + 1))
        else:
            raise SystemExit('wikidata yanıt vermiyor')
        for i in chunk:
            cache.setdefault(str(i), {})
        for r in rows:
            # Several items can carry one GeoNames id (Hamadan and the ancient
            # Hegmataneh under it); keep every label and choose later.
            labels = cache[r['gid']['value']].setdefault(r['label']['xml:lang'], [])
            if r['label']['value'] not in labels:
                labels.append(r['label']['value'])
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
        time.sleep(1)
    return {int(k): v for k, v in cache.items() if int(k) in ids}


def alternate_names(cc, ids):
    """geonameid -> {lang: name}: Wikidata's label, else GeoNames' preferred name."""
    wiki = wikidata_labels(ids)
    out = {}
    z = zipfile.ZipFile(fetch(f'alternatenames/{cc}.zip'))
    geo = {}
    out = geo
    with z.open(f'{cc}.txt') as f:
        for line in io.TextIOWrapper(f, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) < 4:
                continue
            gid = int(p[1])
            if gid not in ids:
                continue
            lang, name = p[2], p[3]
            if lang not in LANGS or not name:
                continue
            # GeoNames tags some transliterations with the script language
            # ("Ural'sk" as Russian); a name must be written in the script.
            block = SCRIPT_RANGE.get(lang)
            if block and not any(block[0] <= ord(ch) <= block[1] for ch in name):
                continue
            historic = len(p) > 7 and p[7] == '1'
            colloquial = len(p) > 6 and p[6] == '1'
            if historic or colloquial:
                continue
            preferred = len(p) > 4 and p[4] == '1'
            slot = out.setdefault(gid, {})
            if lang not in slot or preferred:
                slot[lang] = clean(name)
    merged = {}
    for gid in ids:
        # GeoNames only for the scripts; its Latin-letter names are too often
        # a neighbouring district's or a bad transliteration.
        names = {l: v for l, v in geo.get(gid, {}).items() if l in SCRIPT}
        for lang, labels in wiki.get(gid, {}).items():
            block = SCRIPT_RANGE.get(lang)
            labels = [clean(l) for l in labels
                      if not block or any(block[0] <= ord(ch) <= block[1] for ch in l)]
            if not labels:
                continue
            # Where items disagree, the one GeoNames also gives wins.
            names[lang] = names[lang] if lang in names and names[lang] in labels else labels[0]
        names['_wiki'] = gid in wiki and bool(wiki[gid])
        merged[gid] = names
    return merged


def main():
    zipfile.ZipFile(fetch('cities15000.zip')).extractall(GEO)
    rows = []
    for line in (GEO / 'cities15000.txt').read_text(encoding='utf-8').splitlines():
        p = line.split('\t')
        if p[8] not in QUOTA or p[6] != 'P':
            continue
        # Seats and populated places; skip sections of a bigger city.
        if p[7] in ('PPLX', 'PPLH', 'PPLQ', 'PPLW'):
            continue
        rows.append({'gid': int(p[0]), 'name': p[1], 'ascii': p[2], 'lat': float(p[4]),
                     'lon': float(p[5]), 'cc': p[8], 'pop': int(p[14] or 0), 'tz': p[17]})
    have = app_cities()
    cities_json = ROOT / 'data' / 'cities.json'
    current = json.loads(cities_json.read_text(encoding='utf-8'))
    # Keep the app's own cities, drop earlier GeoNames additions, rebuild those.
    kept = [c for c in current if 'lat' not in c]
    have_ids = {(c['id'], c['lang']) for c in kept}
    for name, lat, lon, cc in have:
        lang = NEW_LANG_FOR_APP_CITIES.get(cc)
        if lang and any(c['id'] == f'{cc}:{name}' for c in kept) and (f'{cc}:{name}', lang) not in have_ids:
            kept.append({'id': f'{cc}:{name}', 'lang': lang})
            have_ids.add((f'{cc}:{name}', lang))

    added = []
    for cc, (quota, langs) in QUOTA.items():
        pool = sorted((r for r in rows if r['cc'] == cc), key=lambda r: -r['pop'])
        mine = [(lat, lon) for _, lat, lon, c in have if c == cc]
        pool = [r for r in pool[:quota * 4]
                if not any(km((r['lat'], r['lon']), m) < NEAR_KM for m in mine)]
        alts = alternate_names(cc, {r['gid'] for r in pool})
        chosen = []
        ids = set()
        for r in pool:
            if len(chosen) >= quota:
                break
            if any(km((r['lat'], r['lon']), (c['lat'], c['lon'])) < NEAR_KM for c in chosen):
                continue
            a = alts.get(r['gid'], {})
            # A page in Arabic, Persian, Urdu, Bengali or Russian that names
            # its city in Latin letters looks machine-made, and is: skip the
            # town rather than print "Al Khuşūş" on an Arabic page.
            if any(l in SCRIPT and l not in a for l in langs):
                continue
            # No Wikidata item at all means a place too small or too obscure
            # to have been written up anywhere (Rasapūdipalem); skip it.
            if not a.get('_wiki'):
                continue
            english = clean(a.get('en') or r['name'])
            # Parts of a bigger city that GeoNames lists as places of their own.
            if english in BLOCK:
                continue
            if f'{cc}:{english}' in ids:
                continue  # two towns of one name; the larger one keeps it
            ids.add(f'{cc}:{english}')
            r['alts'] = a
            r['english'] = english
            chosen.append(r)
        for r in chosen:
            a, english = r['alts'], r['english']
            # Latin-script languages keep the place's own spelling (Çorlu,
            # Mingəçevir, Bugojno); a tagged alternate name in them is often a
            # neighbouring district's, so only scripts and English take one.
            local = clean(r['name'])
            names = {}
            for l in LANGS:
                names[l] = a[l] if l in a else (local if l in langs or l == 'tr' else english)
            names['en'] = clean(english)
            for lang in langs:
                added.append({'id': f'{cc}:{english}', 'lang': lang, 'lat': r['lat'], 'lon': r['lon'],
                              'tz': r['tz'], 'country': cc, 'names': names, 'pop': r['pop']})
        print(cc, len(chosen))
    cities_json.write_text(json.dumps(kept + added, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{len(kept)} uygulama şehri + {len(added)} GeoNames sayfası yazıldı')


if __name__ == '__main__':
    main()
