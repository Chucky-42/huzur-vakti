#!/usr/bin/env python3
"""Builds the Huzur Vakti website into docs/ (served by GitHub Pages).

One page per city with that city's prayer times, a page per language and a
site index. The times are not calculated here: data/times.json is written by
the app repo's tool/export_web_times.dart, with the app's own engine, so a
page and the app can never disagree. This script only lays them out.

    python build.py

Rebuilt and pushed on the 1st of every month by the HuzurSiteAylik scheduled
task on the laptop (yenile.py) so the printed month table stays current; the
page's script moves "today" forward in between. data/times.json runs to its "to" date and must be re-exported before
then (it is good until the end of 2027).
"""
import html
import json
import math
import re
import shutil
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'docs'
BASE = 'https://chucky-42.github.io/huzur-vakti/'
PLAY = 'https://play.google.com/store/apps/details?id=com.lutfu.huzurvakti'
APPSTORE = 'https://apps.apple.com/app/id6818989611'
PRIVACY = 'https://chucky-42.github.io/huzur-vakti-gizlilik/'
SUPPORT = 'https://chucky-42.github.io/huzur-vakti-gizlilik/destek.html'
KAABA = (21.4225, 39.8262)

LANGS = ['tr', 'en', 'ar', 'fa', 'ur', 'bn', 'fr', 'id', 'ms', 'ru', 'sw', 'de', 'az', 'uz', 'bs']
RTL = {'ar', 'fa', 'ur'}
# Same digits as the app shows on a phone in that language (locale_digits.dart).
ZERO = {'ar': 0x660, 'fa': 0x6F0, 'bn': 0x9E6}
# Locale handed to Intl for the visitor-side date line. Persian would otherwise
# get the Solar Hijri calendar next to a Gregorian month table.
INTL = {'en': 'en-GB', 'fa': 'fa-u-ca-gregory', 'ar': 'ar-u-nu-arab'}

T = {
    'tr': {
        'name': 'Türkçe',
        'title': '{city} Namaz Vakitleri – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': '{city} Namaz Vakitleri',
        'desc': "{city} için bugünkü ve aylık namaz vakitleri: imsak, güneş, öğle, ikindi, akşam ve yatsı. Kıble açısı ve ezan bildirimi için ücretsiz, reklamsız Huzur Vakti.",
        'next': 'Sıradaki vakit', 'day': 'Gün',
        'month_title': '{month} {year} namaz vakitleri',
        'months': ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
        'facts': 'Hesaplama', 'method': 'Hesaplama yöntemi', 'asr': 'İkindi',
        'asr_shafi': 'Standart: gölge cismin boyu kadar', 'asr_hanafi': 'Hanefi: gölge cismin iki katı',
        'qibla': 'Kıble açısı', 'qibla_value': 'Gerçek kuzeyden saat yönünde {deg}°',
        'distance': "Kâbe'ye uzaklık", 'km': 'km', 'zone': 'Saat dilimi',
        'cta_title': 'Ezan vaktini kaçırmayın',
        'cta_text': "Ezan vakti bildirimi, internetsiz kıble pusulası, imsakiye ve Kur'an-ı Kerim. Reklamsız, hesap gerektirmez.",
        'free': 'Ücretsiz · Reklamsız · Hesap yok',
        'play': "Google Play'den indir", 'appstore': "App Store'dan indir",
        'more': 'Diğer şehirler',
        'note': 'Bu vakitler Huzur Vakti uygulamasının kendi hesabıdır ({method}); uygulamada gördüğünüz vakitlerle aynıdır. Resmî takvimlerle bir-iki dakika fark olabilir.',
        'index_title': 'Namaz Vakitleri – Huzur Vakti', 'index_h1': 'Namaz vakitleri',
        'index_desc': "Türkiye ve dünyadan şehirler için günlük ve aylık namaz vakitleri. Ezan bildirimi, kıble pusulası ve Kur'an için ücretsiz Huzur Vakti uygulaması.",
        'cities': 'Şehirler', 'languages': 'Diğer diller', 'privacy': 'Gizlilik politikası', 'support': 'Destek',
    },
    'en': {
        'name': 'English',
        'title': '{city} Prayer Times Today – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Prayer times in {city}',
        'desc': "Today's and this month's prayer times for {city}: Fajr, Sunrise, Dhuhr, Asr, Maghrib and Isha, with the qibla direction. Adhan alerts with the free, ad-free Huzur Vakti app.",
        'next': 'Next prayer', 'day': 'Day',
        'month_title': 'Prayer times for {month} {year}',
        'months': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
        'facts': 'How these times are calculated', 'method': 'Calculation method', 'asr': 'Asr',
        'asr_shafi': 'Standard: shadow equal to the object', 'asr_hanafi': 'Hanafi: shadow twice the object',
        'qibla': 'Qibla direction', 'qibla_value': '{deg}° clockwise from true north',
        'distance': 'Distance to the Kaaba', 'km': 'km', 'zone': 'Time zone',
        'cta_title': 'Never miss a prayer',
        'cta_text': None,
        'free': 'Free · No ads · No account',
        'play': 'Get it on Google Play', 'appstore': 'Download on the App Store',
        'more': 'More cities',
        'note': "These times come from the Huzur Vakti app's own calculation ({method}) and match what the app shows. Official timetables may differ by a minute or two.",
        'index_title': 'Prayer Times – Huzur Vakti', 'index_h1': 'Prayer times',
        'index_desc': 'Daily and monthly prayer times for cities around the world. Adhan alerts, qibla compass and Quran in the free Huzur Vakti app.',
        'cities': 'Cities', 'languages': 'Other languages', 'privacy': 'Privacy policy', 'support': 'Support',
    },
    'ar': {
        'name': 'العربية',
        'title': 'مواقيت الصلاة في {city} اليوم – {p[0]} و{p[2]} و{p[3]} و{p[4]} و{p[5]}',
        'h1': 'مواقيت الصلاة في {city}',
        'desc': 'مواقيت الصلاة اليوم وطوال الشهر في {city}: الفجر والشروق والظهر والعصر والمغرب والعشاء، مع اتجاه القبلة. تنبيهات الأذان مع تطبيق Huzur Vakti المجاني بلا إعلانات.',
        'next': 'الصلاة القادمة', 'day': 'اليوم',
        'month_title': 'مواقيت الصلاة لشهر {month} {year}',
        'months': ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'],
        'facts': 'طريقة حساب هذه المواقيت', 'method': 'طريقة الحساب', 'asr': 'العصر',
        'asr_shafi': 'الجمهور: ظل الشيء مثله', 'asr_hanafi': 'الحنفي: ظل الشيء مثلاه',
        'qibla': 'اتجاه القبلة', 'qibla_value': '{deg}° من الشمال الجغرافي باتجاه عقارب الساعة',
        'distance': 'المسافة إلى الكعبة', 'km': 'كم', 'zone': 'المنطقة الزمنية',
        'cta_title': 'لا تفوّتك الصلاة',
        'cta_text': None,
        'free': 'مجاني · بلا إعلانات · بلا حساب',
        'play': 'حمّله من Google Play', 'appstore': 'حمّله من App Store',
        'more': 'مدن أخرى',
        'note': 'هذه المواقيت من حساب تطبيق Huzur Vakti نفسه ({method})، وهي نفس ما يعرضه التطبيق. قد تختلف التقاويم الرسمية بدقيقة أو دقيقتين.',
        'index_title': 'مواقيت الصلاة – Huzur Vakti', 'index_h1': 'مواقيت الصلاة',
        'index_desc': 'مواقيت الصلاة اليومية والشهرية لمدن من أنحاء العالم. تنبيهات الأذان وبوصلة القبلة والقرآن في تطبيق Huzur Vakti المجاني.',
        'cities': 'المدن', 'languages': 'لغات أخرى', 'privacy': 'سياسة الخصوصية', 'support': 'الدعم',
    },
    'fa': {
        'name': 'فارسی',
        'title': 'اوقات شرعی {city} امروز – {p[0]}، {p[2]}، {p[3]}، {p[4]} و {p[5]}',
        'h1': 'اوقات شرعی {city}',
        'desc': 'اوقات شرعی امروز و کل ماه در {city}: فجر، طلوع آفتاب، ظهر، عصر، مغرب و عشا، به همراه جهت قبله. یادآور اذان با اپلیکیشن رایگان و بدون تبلیغ Huzur Vakti.',
        'next': 'وقت بعدی', 'day': 'روز',
        'month_title': 'اوقات شرعی {month} {year}',
        'months': ['ژانویه', 'فوریه', 'مارس', 'آوریل', 'مه', 'ژوئن', 'ژوئیه', 'اوت', 'سپتامبر', 'اکتبر', 'نوامبر', 'دسامبر'],
        'facts': 'نحوهٔ محاسبهٔ این اوقات', 'method': 'روش محاسبه', 'asr': 'عصر',
        'asr_shafi': 'استاندارد: سایه برابر شاخص', 'asr_hanafi': 'حنفی: سایه دو برابر شاخص',
        'qibla': 'جهت قبله', 'qibla_value': '{deg}° از شمال جغرافیایی در جهت عقربه‌های ساعت',
        'distance': 'فاصله تا کعبه', 'km': 'کیلومتر', 'zone': 'منطقهٔ زمانی',
        'cta_title': 'وقت نماز را از دست ندهید',
        'cta_text': None,
        'free': 'رایگان · بدون تبلیغ · بدون حساب کاربری',
        'play': 'دریافت از Google Play', 'appstore': 'دریافت از App Store',
        'more': 'شهرهای دیگر',
        'note': 'این اوقات حاصل محاسبهٔ خود اپلیکیشن Huzur Vakti است ({method}) و با آنچه اپلیکیشن نشان می‌دهد یکی است. ممکن است با تقویم‌های رسمی یکی دو دقیقه تفاوت داشته باشد.',
        'index_title': 'اوقات شرعی – Huzur Vakti', 'index_h1': 'اوقات شرعی',
        'index_desc': 'اوقات شرعی روزانه و ماهانه برای شهرهایی در سراسر جهان. یادآور اذان، قبله‌نما و قرآن در اپلیکیشن رایگان Huzur Vakti.',
        'cities': 'شهرها', 'languages': 'زبان‌های دیگر', 'privacy': 'سیاست حریم خصوصی', 'support': 'پشتیبانی',
    },
    'ur': {
        'name': 'اردو',
        'title': '{city} میں آج کے نماز کے اوقات – {p[0]}، {p[2]}، {p[3]}، {p[4]}، {p[5]}',
        'h1': '{city} میں نماز کے اوقات',
        'desc': '{city} میں آج اور پورے مہینے کے نماز کے اوقات: فجر، طلوعِ آفتاب، ظہر، عصر، مغرب اور عشاء، ساتھ قبلہ کی سمت۔ مفت اور اشتہارات کے بغیر Huzur Vakti ایپ سے اذان کی اطلاع پائیں۔',
        'next': 'اگلی نماز', 'day': 'تاریخ',
        'month_title': '{month} {year} کے نماز کے اوقات',
        'months': ['جنوری', 'فروری', 'مارچ', 'اپریل', 'مئی', 'جون', 'جولائی', 'اگست', 'ستمبر', 'اکتوبر', 'نومبر', 'دسمبر'],
        'facts': 'یہ اوقات کیسے نکالے گئے', 'method': 'حساب کا طریقہ', 'asr': 'عصر',
        'asr_shafi': 'جمہور: سایہ ایک مثل', 'asr_hanafi': 'حنفی: سایہ دو مثل',
        'qibla': 'قبلہ کی سمت', 'qibla_value': 'اصل شمال سے گھڑی کی سمت میں {deg}°',
        'distance': 'کعبہ تک فاصلہ', 'km': 'کلومیٹر', 'zone': 'ٹائم زون',
        'cta_title': 'کوئی نماز نہ چھوٹے',
        'cta_text': None,
        'free': 'مفت · اشتہارات کے بغیر · اکاؤنٹ کی ضرورت نہیں',
        'play': 'Google Play سے حاصل کریں', 'appstore': 'App Store سے ڈاؤن لوڈ کریں',
        'more': 'دوسرے شہر',
        'note': 'یہ اوقات Huzur Vakti ایپ کے اپنے حساب سے ہیں ({method}) اور وہی ہیں جو ایپ دکھاتی ہے۔ سرکاری نقشۂ اوقات سے ایک دو منٹ کا فرق ہو سکتا ہے۔',
        'index_title': 'نماز کے اوقات – Huzur Vakti', 'index_h1': 'نماز کے اوقات',
        'index_desc': 'دنیا بھر کے شہروں کے روزانہ اور ماہانہ نماز کے اوقات۔ اذان کی اطلاع، قبلہ نما اور قرآن، مفت Huzur Vakti ایپ میں۔',
        'cities': 'شہر', 'languages': 'دوسری زبانیں', 'privacy': 'رازداری کی پالیسی', 'support': 'مدد',
    },
    'bn': {
        'name': 'বাংলা',
        'title': '{city} আজকের নামাজের সময়সূচি – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': '{city} নামাজের সময়সূচি',
        'desc': '{city}-এর আজকের ও পুরো মাসের নামাজের সময়: ফজর, সূর্যোদয়, যোহর, আসর, মাগরিব ও এশা, সাথে কিবলার দিক। বিনামূল্যে ও বিজ্ঞাপনমুক্ত Huzur Vakti অ্যাপে আজানের নোটিফিকেশন পান।',
        'next': 'পরবর্তী ওয়াক্ত', 'day': 'তারিখ',
        'month_title': '{month} {year}-এর নামাজের সময়সূচি',
        'months': ['জানুয়ারি', 'ফেব্রুয়ারি', 'মার্চ', 'এপ্রিল', 'মে', 'জুন', 'জুলাই', 'আগস্ট', 'সেপ্টেম্বর', 'অক্টোবর', 'নভেম্বর', 'ডিসেম্বর'],
        'facts': 'এই সময়গুলো কীভাবে হিসাব করা হয়েছে', 'method': 'হিসাবের পদ্ধতি', 'asr': 'আসর',
        'asr_shafi': 'সাধারণ: ছায়া বস্তুর সমান', 'asr_hanafi': 'হানাফি: ছায়া বস্তুর দ্বিগুণ',
        'qibla': 'কিবলার দিক', 'qibla_value': 'প্রকৃত উত্তর থেকে ঘড়ির কাঁটার দিকে {deg}°',
        'distance': 'কাবা পর্যন্ত দূরত্ব', 'km': 'কিমি', 'zone': 'সময় অঞ্চল',
        'cta_title': 'নামাজের সময় মিস করবেন না',
        'cta_text': None,
        'free': 'বিনামূল্যে · বিজ্ঞাপন নেই · অ্যাকাউন্ট লাগে না',
        'play': 'Google Play থেকে নিন', 'appstore': 'App Store থেকে ডাউনলোড করুন',
        'more': 'অন্যান্য শহর',
        'note': 'এই সময়গুলো Huzur Vakti অ্যাপের নিজস্ব হিসাব ({method}), অ্যাপে যা দেখায় ঠিক তা-ই। সরকারি সময়সূচির সাথে এক-দুই মিনিটের পার্থক্য হতে পারে।',
        'index_title': 'নামাজের সময়সূচি – Huzur Vakti', 'index_h1': 'নামাজের সময়সূচি',
        'index_desc': 'বিশ্বের বিভিন্ন শহরের দৈনিক ও মাসিক নামাজের সময়সূচি। আজানের নোটিফিকেশন, কিবলা কম্পাস ও কুরআন — বিনামূল্যের Huzur Vakti অ্যাপে।',
        'cities': 'শহর', 'languages': 'অন্যান্য ভাষা', 'privacy': 'গোপনীয়তা নীতি', 'support': 'সহায়তা',
    },
    'fr': {
        'name': 'Français',
        'title': "Horaires de prière à {city} aujourd'hui – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}",
        'h1': 'Horaires de prière à {city}',
        'desc': "Horaires de prière du jour et du mois à {city} : Fajr, Chourouk, Dhouhr, Asr, Maghreb et Icha, avec la direction de la qibla. L'adhan à l'heure avec l'application gratuite et sans publicité Huzur Vakti.",
        'next': 'Prochaine prière', 'day': 'Jour',
        'month_title': 'Horaires de prière – {month} {year}',
        'months': ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
        'facts': 'Comment ces horaires sont calculés', 'method': 'Méthode de calcul', 'asr': 'Asr',
        'asr_shafi': "Standard : ombre égale à l'objet", 'asr_hanafi': "Hanafite : ombre double de l'objet",
        'qibla': 'Direction de la qibla', 'qibla_value': '{deg}° depuis le nord géographique, dans le sens horaire',
        'distance': "Distance jusqu'à la Kaaba", 'km': 'km', 'zone': 'Fuseau horaire',
        'cta_title': 'Ne manquez plus une prière',
        'cta_text': None,
        'free': 'Gratuit · Sans publicité · Sans compte',
        'play': 'Disponible sur Google Play', 'appstore': "Télécharger dans l'App Store",
        'more': 'Autres villes',
        'note': "Ces horaires sont calculés par l'application Huzur Vakti elle-même ({method}) : ce sont ceux qu'elle affiche. Les calendriers officiels peuvent différer d'une ou deux minutes.",
        'index_title': 'Horaires de prière – Huzur Vakti', 'index_h1': 'Horaires de prière',
        'index_desc': "Horaires de prière du jour et du mois pour des villes du monde entier. Adhan, boussole qibla et Coran dans l'application gratuite Huzur Vakti.",
        'cities': 'Villes', 'languages': 'Autres langues', 'privacy': 'Politique de confidentialité', 'support': 'Assistance',
    },
    'id': {
        'name': 'Bahasa Indonesia',
        'title': 'Jadwal Sholat {city} Hari Ini – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Jadwal Sholat {city}',
        'desc': 'Jadwal sholat hari ini dan sebulan penuh untuk {city}: Subuh, Terbit, Zuhur, Asar, Magrib, dan Isya, beserta arah kiblat. Pengingat azan dengan aplikasi Huzur Vakti yang gratis dan tanpa iklan.',
        'next': 'Sholat berikutnya', 'day': 'Tgl',
        'month_title': 'Jadwal sholat {month} {year}',
        'months': ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'],
        'facts': 'Cara jadwal ini dihitung', 'method': 'Metode perhitungan', 'asr': 'Asar',
        'asr_shafi': 'Standar: bayangan sama panjang dengan benda', 'asr_hanafi': 'Hanafi: bayangan dua kali panjang benda',
        'qibla': 'Arah kiblat', 'qibla_value': '{deg}° dari utara sejati searah jarum jam',
        'distance': "Jarak ke Ka'bah", 'km': 'km', 'zone': 'Zona waktu',
        'cta_title': 'Jangan lewatkan waktu sholat',
        'cta_text': None,
        'free': 'Gratis · Tanpa iklan · Tanpa akun',
        'play': 'Dapatkan di Google Play', 'appstore': 'Unduh di App Store',
        'more': 'Kota lainnya',
        'note': 'Jadwal ini berasal dari perhitungan aplikasi Huzur Vakti sendiri ({method}) dan sama dengan yang ditampilkan aplikasi. Jadwal resmi bisa berbeda satu-dua menit.',
        'index_title': 'Jadwal Sholat – Huzur Vakti', 'index_h1': 'Jadwal sholat',
        'index_desc': "Jadwal sholat harian dan bulanan untuk kota-kota di seluruh dunia. Pengingat azan, kompas kiblat, dan Al-Qur'an di aplikasi gratis Huzur Vakti.",
        'cities': 'Kota', 'languages': 'Bahasa lain', 'privacy': 'Kebijakan privasi', 'support': 'Bantuan',
    },
    'ms': {
        'name': 'Bahasa Melayu',
        'title': 'Waktu Solat {city} Hari Ini – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Waktu Solat {city}',
        'desc': 'Waktu solat hari ini dan sebulan penuh bagi {city}: Subuh, Syuruk, Zohor, Asar, Maghrib dan Isyak, serta arah kiblat. Peringatan azan dengan aplikasi Huzur Vakti yang percuma dan tanpa iklan.',
        'next': 'Solat seterusnya', 'day': 'Hb',
        'month_title': 'Waktu solat {month} {year}',
        'months': ['Januari', 'Februari', 'Mac', 'April', 'Mei', 'Jun', 'Julai', 'Ogos', 'September', 'Oktober', 'November', 'Disember'],
        'facts': 'Cara waktu ini dikira', 'method': 'Kaedah pengiraan', 'asr': 'Asar',
        'asr_shafi': 'Standard: bayang sama panjang dengan objek', 'asr_hanafi': 'Hanafi: bayang dua kali panjang objek',
        'qibla': 'Arah kiblat', 'qibla_value': '{deg}° dari utara benar, mengikut arah jam',
        'distance': 'Jarak ke Kaabah', 'km': 'km', 'zone': 'Zon waktu',
        'cta_title': 'Jangan terlepas waktu solat',
        'cta_text': None,
        'free': 'Percuma · Tanpa iklan · Tanpa akaun',
        'play': 'Dapatkan di Google Play', 'appstore': 'Muat turun di App Store',
        'more': 'Bandar lain',
        'note': 'Waktu ini dikira oleh aplikasi Huzur Vakti sendiri ({method}) dan sama dengan yang dipaparkan dalam aplikasi. Jadual rasmi mungkin berbeza seminit dua.',
        'index_title': 'Waktu Solat – Huzur Vakti', 'index_h1': 'Waktu solat',
        'index_desc': 'Waktu solat harian dan bulanan bagi bandar-bandar di seluruh dunia. Peringatan azan, kompas kiblat dan al-Quran dalam aplikasi percuma Huzur Vakti.',
        'cities': 'Bandar', 'languages': 'Bahasa lain', 'privacy': 'Dasar privasi', 'support': 'Sokongan',
    },
    'ru': {
        'name': 'Русский',
        'title': '{city} — время намаза сегодня: {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Время намаза — {city}',
        'desc': 'Расписание намазов на сегодня и на весь месяц, город {city}: Фаджр, Восход, Зухр, Аср, Магриб и Иша, а также направление киблы. Азан вовремя в бесплатном приложении Huzur Vakti без рекламы.',
        'next': 'Следующий намаз', 'day': 'Число',
        'month_title': 'Время намаза: {month} {year}',
        'months': ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'],
        'months_of': ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
        'facts': 'Как рассчитано это время', 'method': 'Метод расчёта', 'asr': 'Аср',
        'asr_shafi': 'Стандартный: тень равна предмету', 'asr_hanafi': 'Ханафитский: тень вдвое длиннее предмета',
        'qibla': 'Направление киблы', 'qibla_value': '{deg}° от истинного севера по часовой стрелке',
        'distance': 'Расстояние до Каабы', 'km': 'км', 'zone': 'Часовой пояс',
        'cta_title': 'Не пропускайте время намаза',
        'cta_text': None,
        'free': 'Бесплатно · Без рекламы · Без аккаунта',
        'play': 'Доступно в Google Play', 'appstore': 'Загрузите в App Store',
        'more': 'Другие города',
        'note': 'Время рассчитано самим приложением Huzur Vakti ({method}) и совпадает с тем, что показывает приложение. Официальные расписания могут отличаться на минуту-две.',
        'index_title': 'Время намаза – Huzur Vakti', 'index_h1': 'Время намаза',
        'index_desc': 'Расписание намазов на день и на месяц для городов по всему миру. Азан, компас киблы и Коран в бесплатном приложении Huzur Vakti.',
        'cities': 'Города', 'languages': 'Другие языки', 'privacy': 'Политика конфиденциальности', 'support': 'Поддержка',
    },
    'sw': {
        'name': 'Kiswahili',
        'title': 'Nyakati za Sala – {city} leo: {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Nyakati za Sala – {city}',
        'desc': 'Nyakati za sala za leo na za mwezi mzima kwa {city}: Alfajiri, Macheo, Adhuhuri, Alasiri, Magharibi na Isha, pamoja na mwelekeo wa kibla. Pata adhana kwa wakati ukitumia programu ya Huzur Vakti, bure na bila matangazo.',
        'next': 'Sala inayofuata', 'day': 'Tarehe',
        'month_title': 'Nyakati za sala – {month} {year}',
        'months': ['Januari', 'Februari', 'Machi', 'Aprili', 'Mei', 'Juni', 'Julai', 'Agosti', 'Septemba', 'Oktoba', 'Novemba', 'Desemba'],
        'facts': 'Jinsi nyakati hizi zinavyohesabiwa', 'method': 'Njia ya kuhesabu', 'asr': 'Alasiri',
        'asr_shafi': 'Kawaida: kivuli sawa na kitu', 'asr_hanafi': 'Hanafi: kivuli mara mbili ya kitu',
        'qibla': 'Mwelekeo wa kibla', 'qibla_value': '{deg}° kutoka kaskazini halisi, kwa mwelekeo wa saa',
        'distance': 'Umbali hadi Al-Kaaba', 'km': 'km', 'zone': 'Saa za eneo',
        'cta_title': 'Usikose wakati wa sala',
        'cta_text': None,
        'free': 'Bure · Bila matangazo · Bila akaunti',
        'play': 'Ipate kwenye Google Play', 'appstore': 'Pakua kwenye App Store',
        'more': 'Miji mingine',
        'note': 'Nyakati hizi zimehesabiwa na programu ya Huzur Vakti yenyewe ({method}) na ni zile zile zinazoonyeshwa kwenye programu. Kalenda rasmi zinaweza kutofautiana kwa dakika moja au mbili.',
        'index_title': 'Nyakati za Sala – Huzur Vakti', 'index_h1': 'Nyakati za sala',
        'index_desc': "Nyakati za sala za kila siku na za mwezi kwa miji ya duniani kote. Adhana, dira ya kibla na Qur'ani katika programu ya bure ya Huzur Vakti.",
        'cities': 'Miji', 'languages': 'Lugha nyingine', 'privacy': 'Sera ya faragha', 'support': 'Msaada',
    },
    'de': {
        'name': 'Deutsch',
        'title': 'Gebetszeiten {city} heute – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Gebetszeiten in {city}',
        'desc': 'Gebetszeiten für {city} heute und für den ganzen Monat: Fadschr, Schuruq, Dhuhr, Asr, Maghrib und Ischa, mit Qibla-Richtung. Adhan-Erinnerung mit der kostenlosen, werbefreien App Huzur Vakti.',
        'next': 'Nächstes Gebet',
        'day': 'Tag',
        'month_title': 'Gebetszeiten {month} {year}',
        'months': ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
        'facts': 'So werden diese Zeiten berechnet',
        'method': 'Berechnungsmethode',
        'asr': 'Asr',
        'asr_shafi': 'Standard: Schatten so lang wie der Gegenstand',
        'asr_hanafi': 'Hanafitisch: Schatten doppelt so lang',
        'qibla': 'Qibla-Richtung',
        'qibla_value': '{deg}° im Uhrzeigersinn ab geografisch Nord',
        'distance': 'Entfernung zur Kaaba',
        'km': 'km',
        'zone': 'Zeitzone',
        'cta_title': 'Kein Gebet mehr verpassen',
        'cta_text': None,
        'free': 'Kostenlos · Ohne Werbung · Ohne Konto',
        'play': 'Bei Google Play herunterladen',
        'appstore': 'Im App Store laden',
        'more': 'Weitere Städte',
        'note': 'Diese Zeiten stammen aus der eigenen Berechnung der App Huzur Vakti ({method}) und stimmen mit der App überein. Offizielle Kalender können um ein bis zwei Minuten abweichen.',
        'index_title': 'Gebetszeiten – Huzur Vakti',
        'index_h1': 'Gebetszeiten',
        'index_desc': "Tägliche und monatliche Gebetszeiten für Städte in Deutschland und weltweit. Adhan-Erinnerung, Qibla-Kompass und Qur'an in der kostenlosen App Huzur Vakti.",
        'cities': 'Städte',
        'languages': 'Andere Sprachen',
        'privacy': 'Datenschutz',
        'support': 'Hilfe',
    },
    'az': {
        'name': 'Azərbaycanca',
        'title': '{city} namaz vaxtları bu gün – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': '{city} namaz vaxtları',
        'desc': '{city} üçün bugünkü və aylıq namaz vaxtları: sübh, günəş, zöhr, əsr, məğrib və işa, qiblə istiqaməti ilə. Pulsuz və reklamsız Huzur Vakti tətbiqi ilə azan bildirişi.',
        'next': 'Növbəti namaz',
        'day': 'Gün',
        'month_title': '{month} {year} namaz vaxtları',
        'months': ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'İyun', 'İyul', 'Avqust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'],
        'facts': 'Bu vaxtlar necə hesablanır',
        'method': 'Hesablama üsulu',
        'asr': 'Əsr',
        'asr_shafi': 'Standart: kölgə əşya boyda',
        'asr_hanafi': 'Hənəfi: kölgə əşyanın iki misli',
        'qibla': 'Qiblə istiqaməti',
        'qibla_value': 'Coğrafi şimaldan saat əqrəbi istiqamətində {deg}°',
        'distance': 'Kəbəyə məsafə',
        'km': 'km',
        'zone': 'Saat qurşağı',
        'cta_title': 'Namaz vaxtını qaçırmayın',
        'cta_text': None,
        'free': 'Pulsuz · Reklamsız · Hesabsız',
        'play': 'Google Play-dən yükləyin',
        'appstore': 'App Store-dan yükləyin',
        'more': 'Digər şəhərlər',
        'note': 'Bu vaxtlar Huzur Vakti tətbiqinin öz hesablamasıdır ({method}) və tətbiqdə gördüyünüzlə eynidir. Rəsmi təqvimlərlə bir-iki dəqiqə fərq ola bilər.',
        'index_title': 'Namaz vaxtları – Huzur Vakti',
        'index_h1': 'Namaz vaxtları',
        'index_desc': 'Azərbaycan və dünya şəhərləri üçün gündəlik və aylıq namaz vaxtları. Pulsuz Huzur Vakti tətbiqində azan bildirişi, qiblə kompası və Quran.',
        'cities': 'Şəhərlər',
        'languages': 'Digər dillər',
        'privacy': 'Məxfilik siyasəti',
        'support': 'Dəstək',
    },
    'uz': {
        'name': 'Oʻzbekcha',
        'title': '{city} namoz vaqtlari bugun – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': '{city} namoz vaqtlari',
        'desc': '{city} uchun bugungi va oylik namoz vaqtlari: bomdod, quyosh, peshin, asr, shom va xufton, qibla yoʻnalishi bilan. Bepul va reklamasiz Huzur Vakti ilovasida azon eslatmasi.',
        'next': 'Keyingi namoz',
        'day': 'Kun',
        'month_title': '{year}-yil {month} namoz vaqtlari',
        'months': ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'],
        'facts': 'Bu vaqtlar qanday hisoblanadi',
        'method': 'Hisoblash usuli',
        'asr': 'Asr',
        'asr_shafi': 'Standart: soya buyum boʻyi',
        'asr_hanafi': 'Hanafiy: soya buyumdan ikki baravar',
        'qibla': 'Qibla yoʻnalishi',
        'qibla_value': 'Geografik shimoldan soat mili boʻyicha {deg}°',
        'distance': 'Kaʼbagacha masofa',
        'km': 'km',
        'zone': 'Vaqt mintaqasi',
        'cta_title': 'Namoz vaqtini oʻtkazib yubormang',
        'cta_text': None,
        'free': 'Bepul · Reklamasiz · Hisobsiz',
        'play': 'Google Playʼdan yuklab oling',
        'appstore': 'App Storeʼdan yuklab oling',
        'more': 'Boshqa shaharlar',
        'note': 'Bu vaqtlar Huzur Vakti ilovasining oʻz hisobidir ({method}) va ilovada koʻrganingiz bilan bir xil. Rasmiy taqvimlar bilan bir-ikki daqiqa farq boʻlishi mumkin.',
        'index_title': 'Namoz vaqtlari – Huzur Vakti',
        'index_h1': 'Namoz vaqtlari',
        'index_desc': 'Oʻzbekiston va dunyo shaharlari uchun kunlik va oylik namoz vaqtlari. Bepul Huzur Vakti ilovasida azon eslatmasi, qibla kompasi va Qurʼon.',
        'cities': 'Shaharlar',
        'languages': 'Boshqa tillar',
        'privacy': 'Maxfiylik siyosati',
        'support': 'Yordam',
    },
    'bs': {
        'name': 'Bosanski',
        'title': 'Vaktija {city} danas – {p[0]}, {p[2]}, {p[3]}, {p[4]}, {p[5]}',
        'h1': 'Vaktija za {city}',
        'desc': 'Današnja i mjesečna namaska vremena za {city}: zora, izlazak sunca, podne, ikindija, akšam i jacija, s pravcem kible. Ezan na vrijeme uz besplatnu aplikaciju Huzur Vakti bez reklama.',
        'next': 'Sljedeći namaz',
        'day': 'Dan',
        'month_title': 'Vaktija za {month} {year}.',
        'months': ['januar', 'februar', 'mart', 'april', 'maj', 'juni', 'juli', 'august', 'septembar', 'oktobar', 'novembar', 'decembar'],
        'facts': 'Kako se računaju ova vremena',
        'method': 'Metoda izračuna',
        'asr': 'Ikindija',
        'asr_shafi': 'Standardno: sjena jednaka predmetu',
        'asr_hanafi': 'Hanefijski: sjena dvostruka od predmeta',
        'qibla': 'Pravac kible',
        'qibla_value': '{deg}° u smjeru kazaljke od geografskog sjevera',
        'distance': 'Udaljenost do Kabe',
        'km': 'km',
        'zone': 'Vremenska zona',
        'cta_title': 'Ne propustite vakat',
        'cta_text': None,
        'free': 'Besplatno · Bez reklama · Bez računa',
        'play': 'Preuzmite na Google Playu',
        'appstore': 'Preuzmite na App Storeu',
        'more': 'Ostali gradovi',
        'note': 'Ova vremena su vlastiti izračun aplikacije Huzur Vakti ({method}) i ista su kao u aplikaciji. Zvanične vaktije mogu odstupati minutu-dvije.',
        'index_title': 'Vaktija – Huzur Vakti',
        'index_h1': 'Vaktija',
        'index_desc': "Dnevna i mjesečna namaska vremena za gradove u Bosni i Hercegovini i svijetu. Ezan, kompas za kiblu i Kur'an u besplatnoj aplikaciji Huzur Vakti.",
        'cities': 'Gradovi',
        'languages': 'Drugi jezici',
        'privacy': 'Politika privatnosti',
        'support': 'Podrška',
    },
}


# Ramadan pages: the fasting timetable of the Ramadan inside the data, per city.
R = {
    'tr': {'title': '{city} Ramazan İmsakiyesi {year} – Sahur ve İftar Saatleri', 'h1': '{city} Ramazan İmsakiyesi {year}',
           'desc': '{city} için {year} Ramazan imsakiyesi: her gün imsak (sahur sonu) ve iftar saatleri. Vakitler Huzur Vakti uygulamasının hesabıdır; uygulama her vakitte haber verir.',
           'intro': 'Ümmülkura takvimine göre Ramazan {start} günü başlar, Ramazan Bayramı {eid} günüdür. Bazı ülkelerde başlangıç bir gün sonra olabilir; o zaman oruç bu tablonun bitiminden bir gün sonra sona erer.',
           'cols': ['Gün', 'Tarih', 'İmsak', 'İftar', 'Süre'], 'link': 'Ramazan {year} imsakiyesi', 'list': 'Ramazan {year} imsakiyeleri',
           'cta_title': 'Sahur ve iftar vaktinde haber alın'},
    'en': {'title': 'Ramadan {year} Timetable for {city} – Suhoor and Iftar Times', 'h1': 'Ramadan {year} in {city}',
           'desc': 'Ramadan {year} timetable for {city}: the end of suhoor (imsak) and iftar time for every day, calculated by the Huzur Vakti app, which alerts you at each time.',
           'intro': 'By the Umm al-Qura calendar, Ramadan begins on {start} and Eid al-Fitr is on {eid}. In some countries it may begin a day later; the fast then runs one day past the end of this table.',
           'cols': ['Day', 'Date', 'Suhoor ends', 'Iftar', 'Fast'], 'link': 'Ramadan {year} timetable', 'list': 'Ramadan {year} timetables',
           'cta_title': 'Get an alert at suhoor and iftar'},
    'ar': {'title': 'إمساكية رمضان {year} في {city} – مواعيد السحور والإفطار', 'h1': 'إمساكية رمضان {year} في {city}',
           'desc': 'إمساكية رمضان {year} في {city}: موعد الإمساك (نهاية السحور) وموعد الإفطار لكل يوم، من حساب تطبيق Huzur Vakti الذي ينبّهك عند كل موعد.',
           'intro': 'بحسب تقويم أم القرى يبدأ رمضان يوم {start}، ويكون عيد الفطر يوم {eid}. وقد يبدأ رمضان في بعض البلدان بعد يوم، فيمتد الصيام يومًا بعد آخر هذا الجدول.',
           'cols': ['اليوم', 'التاريخ', 'الإمساك', 'الإفطار', 'مدة الصيام'], 'link': 'إمساكية رمضان {year}', 'list': 'إمساكيات رمضان {year}',
           'cta_title': 'تنبيه عند السحور والإفطار'},
    'fa': {'title': 'اوقات سحر و افطار رمضان {year} در {city}', 'h1': 'اوقات سحر و افطار رمضان {year} – {city}',
           'desc': 'اوقات امساک (پایان سحر) و افطار هر روز رمضان {year} در {city}، از محاسبهٔ اپلیکیشن Huzur Vakti که سر هر وقت به شما یادآوری می‌کند.',
           'intro': 'بر اساس تقویم امّ‌القری، رمضان {start} آغاز می‌شود و عید فطر {eid} است. در برخی کشورها ممکن است یک روز دیرتر آغاز شود؛ در آن صورت روزه یک روز پس از پایان این جدول ادامه دارد.',
           'cols': ['روز', 'تاریخ', 'امساک', 'افطار', 'مدت روزه'], 'link': 'اوقات سحر و افطار رمضان {year}', 'list': 'اوقات رمضان {year}',
           'cta_title': 'یادآور سحر و افطار'},
    'ur': {'title': '{city} – رمضان {year} سحری و افطار کے اوقات', 'h1': '{city} – رمضان {year} کے اوقاتِ سحر و افطار',
           'desc': '{city} میں رمضان {year} کے ہر دن کا وقتِ امساک (سحری کا اختتام) اور افطار، Huzur Vakti ایپ کے حساب سے، جو ہر وقت پر اطلاع بھی دیتی ہے۔',
           'intro': 'ام القریٰ کیلنڈر کے مطابق رمضان {start} کو شروع ہوگا اور عید الفطر {eid} کو ہے۔ بعض ملکوں میں آغاز ایک دن بعد ہو سکتا ہے؛ اس صورت میں روزے اس جدول کے آخر سے ایک دن آگے چلیں گے۔',
           'cols': ['روزہ', 'تاریخ', 'امساک', 'افطار', 'دورانیہ'], 'link': 'رمضان {year} کے اوقاتِ سحر و افطار', 'list': 'رمضان {year} کے اوقات',
           'cta_title': 'سحری اور افطار پر اطلاع'},
    'bn': {'title': '{city} রমজান {year} সেহরি ও ইফতারের সময়সূচি', 'h1': '{city} – রমজান {year} সেহরি ও ইফতার',
           'desc': '{city}-এ রমজান {year}-এর প্রতিদিনের সেহরির শেষ সময় (ইমসাক) ও ইফতারের সময়, Huzur Vakti অ্যাপের হিসাবে; অ্যাপটি প্রতিটি সময়ে নোটিফিকেশনও দেয়।',
           'intro': 'উম্মুল কুরা ক্যালেন্ডার অনুযায়ী রমজান শুরু {start}, ঈদুল ফিতর {eid}। কিছু দেশে একদিন পরে শুরু হতে পারে; তখন রোজা এই সারণির শেষের পরে আরও একদিন চলবে।',
           'cols': ['রোজা', 'তারিখ', 'সেহরি শেষ', 'ইফতার', 'সময়কাল'], 'link': 'রমজান {year} সময়সূচি', 'list': 'রমজান {year} সময়সূচি',
           'cta_title': 'সেহরি ও ইফতারে নোটিফিকেশন'},
    'fr': {'title': "Calendrier du Ramadan {year} à {city} – heures du sahour et de l'iftar", 'h1': 'Ramadan {year} à {city}',
           'desc': "Calendrier du Ramadan {year} à {city} : chaque jour, la fin du sahour (imsak) et l'heure de l'iftar, calculées par l'application Huzur Vakti, qui vous prévient à chaque heure.",
           'intro': "Selon le calendrier Umm al-Qura, le Ramadan commence le {start} et l'Aïd al-Fitr tombe le {eid}. Dans certains pays, il peut commencer un jour plus tard ; le jeûne dure alors un jour de plus que ce tableau.",
           'cols': ['Jour', 'Date', 'Fin du sahour', 'Iftar', 'Durée'], 'link': 'Calendrier du Ramadan {year}', 'list': 'Calendriers du Ramadan {year}',
           'cta_title': "Soyez prévenu au sahour et à l'iftar"},
    'id': {'title': 'Jadwal Imsakiyah Ramadhan {year} {city} – Waktu Sahur dan Berbuka', 'h1': 'Imsakiyah Ramadhan {year} {city}',
           'desc': 'Jadwal imsakiyah Ramadhan {year} untuk {city}: waktu imsak dan berbuka setiap hari, dari perhitungan aplikasi Huzur Vakti yang juga mengingatkan Anda di setiap waktu.',
           'intro': 'Menurut kalender Umm al-Qura, Ramadhan dimulai pada {start} dan Idulfitri jatuh pada {eid}. Di beberapa negara awal puasa bisa sehari lebih lambat; puasa lalu berlangsung sehari setelah akhir tabel ini.',
           'cols': ['Hari', 'Tanggal', 'Imsak', 'Berbuka', 'Lama puasa'], 'link': 'Imsakiyah Ramadhan {year}', 'list': 'Imsakiyah Ramadhan {year}',
           'cta_title': 'Pengingat sahur dan berbuka'},
    'ms': {'title': 'Jadual Imsak dan Berbuka Puasa Ramadan {year} – {city}', 'h1': 'Waktu Imsak dan Berbuka Ramadan {year} – {city}',
           'desc': 'Jadual waktu imsak dan berbuka puasa Ramadan {year} bagi {city} untuk setiap hari, dikira oleh aplikasi Huzur Vakti yang turut memberi peringatan pada setiap waktu.',
           'intro': 'Mengikut kalendar Umm al-Qura, Ramadan bermula pada {start} dan Aidilfitri jatuh pada {eid}. Di sesetengah negara ia mungkin bermula sehari kemudian; puasa kemudian berterusan sehari selepas akhir jadual ini.',
           'cols': ['Hari', 'Tarikh', 'Imsak', 'Berbuka', 'Tempoh'], 'link': 'Jadual Ramadan {year}', 'list': 'Jadual Ramadan {year}',
           'cta_title': 'Peringatan sahur dan berbuka'},
    'ru': {'title': 'Рамадан {year}: время сухура и ифтара — {city}', 'h1': 'Рамадан {year} — {city}',
           'desc': 'Расписание Рамадана {year}, город {city}: окончание сухура (имсак) и время ифтара на каждый день — по расчёту приложения Huzur Vakti, которое напоминает о каждом времени.',
           'intro': 'По календарю Умм аль-Кура Рамадан начинается {start}, а Ураза-байрам приходится на {eid}. В некоторых странах начало может быть на день позже; тогда пост продлится на день дольше этой таблицы.',
           'cols': ['День', 'Дата', 'Имсак', 'Ифтар', 'Длительность'], 'link': 'Расписание Рамадана {year}', 'list': 'Расписание Рамадана {year}',
           'cta_title': 'Напоминание о сухуре и ифтаре'},
    'sw': {'title': 'Ratiba ya Ramadhani {year} – {city}: daku na futari', 'h1': 'Ramadhani {year} – {city}',
           'desc': 'Ratiba ya Ramadhani {year} kwa {city}: muda wa kuacha daku (imsaki) na wa futari kila siku, kwa hesabu ya programu ya Huzur Vakti inayokukumbusha kila wakati.',
           'intro': 'Kwa kalenda ya Umm al-Qura, Ramadhani inaanza {start} na Idi el-Fitri ni {eid}. Katika baadhi ya nchi inaweza kuanza siku moja baadaye; hapo mfungo huendelea siku moja zaidi ya mwisho wa jedwali hili.',
           'cols': ['Siku', 'Tarehe', 'Imsaki', 'Futari', 'Muda'], 'link': 'Ratiba ya Ramadhani {year}', 'list': 'Ratiba za Ramadhani {year}',
           'cta_title': 'Kikumbusho cha daku na futari'},
    'de': {
        'title': 'Ramadan {year} in {city} – Sahur- und Iftar-Zeiten',
        'h1': 'Ramadan-Kalender {year} für {city}',
        'desc': 'Ramadan-Kalender {year} für {city}: für jeden Tag das Ende des Sahur (Imsak) und die Iftar-Zeit, berechnet von der App Huzur Vakti, die Sie zu jeder Zeit erinnert.',
        'intro': 'Nach dem Umm-al-Qura-Kalender beginnt der Ramadan am {start}, das Ramadanfest ist am {eid}. In manchen Ländern beginnt er einen Tag später; dann dauert das Fasten einen Tag über das Ende dieser Tabelle hinaus.',
        'cols': ['Tag', 'Datum', 'Sahur-Ende', 'Iftar', 'Dauer'],
        'link': 'Ramadan-Kalender {year}',
        'list': 'Ramadan-Kalender {year}',
        'cta_title': 'Erinnerung zu Sahur und Iftar',
    },
    'az': {
        'title': '{city} Ramazan təqvimi {year} – imsak və iftar vaxtları',
        'h1': '{city} Ramazan təqvimi {year}',
        'desc': '{city} üçün {year} Ramazan təqvimi: hər gün imsak (sahurun sonu) və iftar vaxtı. Vaxtlar Huzur Vakti tətbiqinin hesablamasıdır; tətbiq hər vaxtda xəbər verir.',
        'intro': 'Ümmülqura təqviminə görə Ramazan {start} tarixində başlayır, Ramazan bayramı {eid} tarixindədir. Bəzi ölkələrdə bir gün gec başlaya bilər; o zaman oruc bu cədvəlin sonundan bir gün çox davam edir.',
        'cols': ['Gün', 'Tarix', 'İmsak', 'İftar', 'Müddət'],
        'link': 'Ramazan {year} təqvimi',
        'list': 'Ramazan {year} təqvimləri',
        'cta_title': 'İmsak və iftar vaxtında xəbər alın',
    },
    'uz': {
        'title': '{city} Ramazon taqvimi {year} – saharlik va iftorlik vaqtlari',
        'h1': '{city} Ramazon taqvimi {year}',
        'desc': '{city} uchun {year} Ramazon taqvimi: har kuni saharlik tugashi (imsok) va iftorlik vaqti. Vaqtlar Huzur Vakti ilovasining hisobi; ilova har vaqtda eslatadi.',
        'intro': 'Ummul-Quro taqvimiga koʻra Ramazon {start} kuni boshlanadi, Ramazon hayiti {eid} kuni. Baʼzi mamlakatlarda bir kun kech boshlanishi mumkin; unda roʻza bu jadval oxiridan bir kun koʻproq davom etadi.',
        'cols': ['Kun', 'Sana', 'Saharlik', 'Iftorlik', 'Davomiyligi'],
        'link': 'Ramazon {year} taqvimi',
        'list': 'Ramazon {year} taqvimlari',
        'cta_title': 'Saharlik va iftorlikda eslatma oling',
    },
    'bs': {
        'title': 'Ramazanska vaktija {year} – {city}: sehur i iftar',
        'h1': 'Ramazanska vaktija {year} za {city}',
        'desc': 'Ramazanska vaktija {year} za {city}: za svaki dan kraj sehura (imsak) i vrijeme iftara, prema izračunu aplikacije Huzur Vakti, koja vas podsjeti na svako vrijeme.',
        'intro': 'Prema kalendaru Umm al-Qura ramazan počinje {start}, a Ramazanski bajram je {eid}. U nekim zemljama može početi dan kasnije; tada post traje dan duže od kraja ove tabele.',
        'cols': ['Dan', 'Datum', 'Imsak', 'Iftar', 'Trajanje'],
        'link': 'Ramazanska vaktija {year}',
        'list': 'Ramazanske vaktije {year}',
        'cta_title': 'Podsjetnik za sehur i iftar',
    },
}


def esc(s):
    return html.escape(str(s), quote=True)


def digits(s, lang):
    zero = ZERO.get(lang)
    if not zero:
        return str(s)
    return re.sub(r'[0-9]', lambda m: chr(zero + ord(m.group()) - 48), str(s))


def slugify(name):
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_name.lower()).strip('-')


def distance_km(lat, lon):
    la1, lo1, la2, lo2 = map(math.radians, (lat, lon, *KAABA))
    a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def play_link(lang, campaign):
    referrer = quote(f'utm_source=huzur-web&utm_medium=site&utm_campaign={campaign}', safe='')
    return f'{PLAY}&hl={lang}&referrer={referrer}'


def head(lang, title, desc, url, rel, alternates=None, jsonld=None):
    tags = [
        '<!doctype html>',
        f'<html lang="{lang}" dir="{"rtl" if lang in RTL else "ltr"}">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>{esc(title)}</title>',
        f'<meta name="description" content="{esc(desc)}">',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{BASE}static/og.png">',
        '<meta name="theme-color" content="#1d5c58">',
        f'<link rel="icon" href="{rel}static/icon-192.png" type="image/png">',
        f'<link rel="apple-touch-icon" href="{rel}static/icon-192.png">',
        f'<link rel="stylesheet" href="{rel}static/style.css">',
    ]
    for code, href in (alternates or []):
        tags.append(f'<link rel="alternate" hreflang="{code}" href="{href}">')
    if jsonld:
        tags.append('<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False) + '</script>')
    tags.append('</head>')
    return '\n'.join(tags)


def top(lang, rel):
    home = f'{rel}{lang}/' if lang else rel
    return (f'<header class="top"><div class="wrap">'
            f'<a class="brand" href="{home}"><img src="{rel}static/icon-192.png" alt="" width="32" height="32">Huzur Vakti</a>'
            f'<a class="langlink" href="{rel}">🌐 {esc(T[lang]["name"]) if lang else "Languages"}</a>'
            f'</div></header>')


def cta(lang, strings, rel, campaign, title=None):
    t = T[lang]
    text = t['cta_text'] or strings[lang]['short']
    return (f'<section class="cta"><img src="{rel}static/icon-192.png" alt="" width="64" height="64">'
            f'<div class="text"><h2>{esc(title or t["cta_title"])}</h2><p>{esc(text)}</p>'
            f'<p class="free">{esc(t["free"])}</p></div>'
            f'<div class="stores"><a class="store" href="{esc(play_link(lang, campaign))}" rel="noopener">{esc(t["play"])}</a>'
            f'<a class="store alt" href="{APPSTORE}" rel="noopener">{esc(t["appstore"])}</a></div></section>')


def foot(lang):
    t = T[lang or 'en']
    return (f'<footer><div class="wrap"><span>© {date.today().year} Huzur Vakti</span>'
            f'<a href="{PRIVACY}">{esc(t["privacy"])}</a><a href="{SUPPORT}">{esc(t["support"])}</a>'
            f'<a href="{PLAY}">Google Play</a><a href="{APPSTORE}">App Store</a></div></footer>')


def grouped(cities, lang):
    """Cities of one language page, grouped by country in the order listed."""
    groups = {}
    for c in cities:
        groups.setdefault(c['country'], []).append(c)
    return [(cs[0]['countryNames'][lang], cs) for cs in groups.values()]


def city_list(cities, lang, rel, skip=None):
    parts = []
    for country, cs in grouped(cities, lang):
        items = ''.join(f'<li><a href="{rel}{lang}/{c["slug"]}/">{esc(c["names"][lang])}</a></li>'
                        for c in cs if c is not skip)
        if items:
            parts.append(f'<h3 class="country">{esc(country)}</h3><ul class="cities">{items}</ul>')
    return ''.join(parts)


def city_page(c, by_lang, strings, start, today):
    lang = c['lang']
    t = T[lang]
    p = strings[lang]['prayers']
    name = c['names'][lang]
    rel = '../../'
    url = f'{BASE}{lang}/{c["slug"]}/'
    title = t['title'].format(city=name, p=p)
    desc = t['desc'].format(city=name)
    month_names = t['months']

    index = max(0, min((today - start).days, len(c['days']) - 1))
    times = c['days'][index]
    printed = date.fromordinal(start.toordinal() + index)
    of = t.get('months_of', month_names)
    dateline = digits(f'{printed.day} {of[printed.month - 1]} {printed.year}', lang)

    first = date(printed.year, printed.month, 1)
    first_index = (first - start).days
    rows = []
    day = first
    while day.month == printed.month:
        i = first_index + day.day - 1
        if 0 <= i < len(c['days']):
            cls = ' class="now"' if day == printed else ''
            cells = ''.join(f'<td>{digits(v, lang)}</td>' for v in c['days'][i])
            rows.append(f'<tr data-d="{day.day}"{cls}><td>{digits(day.day, lang)}</td>{cells}</tr>')
        day = date.fromordinal(day.toordinal() + 1)
    month_title = t['month_title'].format(month=month_names[printed.month - 1], year=digits(printed.year, lang))

    km = distance_km(c['lat'], c['lon'])
    facts = [(t['method'], c['methodTitles'][lang]),
             (t['asr'], t['asr_hanafi'] if c['madhab'] == 'hanafi' else t['asr_shafi'])]
    if km > 5:
        facts.append((t['qibla'], t['qibla_value'].format(deg=digits(round(c['qibla']) % 360, lang))))
        facts.append((t['distance'], f'{digits(round(km), lang)} {t["km"]}'))
    facts.append((t['zone'], c['tz']))
    facts_html = ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in facts)

    data = {
        'from': start.isoformat(), 'tz': c['tz'], 'locale': INTL.get(lang, lang),
        'zero': ZERO.get(lang, 48), 'sep': '—' if lang == 'ar' else '·',
        'months': month_names, 'monthTitle': t['month_title'],
        'days': ''.join(''.join(v.replace(':', '') for v in day_times) for day_times in c['days']),
    }
    crumbs = {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': t['index_h1'], 'item': f'{BASE}{lang}/'},
            {'@type': 'ListItem', 'position': 2, 'name': name, 'item': url},
        ],
    }
    cards = ''.join(f'<li><span class="name">{esc(n)}</span><span class="time">{digits(v, lang)}</span></li>'
                    for n, v in zip(p, times))
    header_cells = ''.join(f'<th>{esc(n)}</th>' for n in p)
    others = [o for o in by_lang[lang] if o is not c]
    body = [
        head(lang, title, desc, url, rel, jsonld=crumbs),
        f'<body>{top(lang, rel)}<main><div class="wrap">',
        f'<p class="crumbs"><a href="{rel}{lang}/">{esc(t["index_h1"])}</a> › {esc(c["countryNames"][lang])}</p>',
        f'<h1>{esc(t["h1"].format(city=name))}</h1>',
        f'<p class="dateline">{esc(dateline)}</p>',
        f'<ul class="today">{cards}</ul>',
        f'<p class="countdown" data-label="{esc(t["next"])}"></p>',
        ramadan_link(c),
        cta(lang, strings, rel, c['slug']),
        f'<h2 id="month-title">{esc(month_title)}</h2>',
        f'<div class="tablewrap"><table class="month" data-month="{printed.year}-{printed.month:02d}">'
        f'<thead><tr><th>{esc(t["day"])}</th>{header_cells}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
        f'<h2>{esc(t["facts"])}</h2><dl class="facts">{facts_html}</dl>',
        f'<p class="note">{esc(t["note"].format(method=c["methodTitles"][lang]))}</p>',
    ]
    if others:
        # With GeoNames' towns a language holds hundreds of cities; listing all
        # of them under every page was 350 links of noise. The same country's
        # nearest 30, and the language index for the rest.
        near = sorted((o for o in by_lang[lang] if o['country'] == c['country'] and o is not c),
                      key=lambda o: (o['lat'] - c['lat']) ** 2 + (o['lon'] - c['lon']) ** 2)[:30]
        body.append(f'<h2>{esc(t["more"])}</h2>{city_list(near, lang, rel)}'
                    f'<p><a href="{rel}{lang}/">{esc(t["index_h1"])} – {esc(t["cities"])}</a></p>')
    body += [
        '</div></main>', foot(lang),
        '<script id="pt" type="application/json">' + json.dumps(data, ensure_ascii=False) + '</script>',
        f'<script src="{rel}static/app.js" defer></script>',
        '</body></html>',
    ]
    return '\n'.join(body)


def date_text(d, lang):
    t = T[lang]
    return digits(f'{d.day} {t.get("months_of", t["months"])[d.month - 1]} {d.year}', lang)


def shift(clock, minutes):
    h, m = map(int, clock.split(':'))
    total = (h * 60 + m + minutes) % 1440
    return f'{total // 60:02d}:{total % 60:02d}'


def span(a, b):
    ah, am = map(int, a.split(':'))
    bh, bm = map(int, b.split(':'))
    minutes = (bh * 60 + bm) - (ah * 60 + am)
    return f'{minutes // 60}:{minutes % 60:02d}'


def ramadan_slug(ramadan):
    return f'ramazan-{date.fromisoformat(ramadan["start"]).year}'


def ramadan_page(c, by_lang, strings, start, ramadan):
    lang = c['lang']
    t, r = T[lang], R[lang]
    name = c['names'][lang]
    first = date.fromisoformat(ramadan['start'])
    year = digits(first.year, lang)
    rel = '../../../'
    url = f'{BASE}{lang}/{c["slug"]}/{ramadan_slug(ramadan)}/'
    title = r['title'].format(city=name, year=year)
    desc = r['desc'].format(city=name, year=year)
    eid = date.fromordinal(first.toordinal() + ramadan['days'])
    rows = []
    for n in range(ramadan['days']):
        day = date.fromordinal(first.toordinal() + n)
        times = c['days'][(day - start).days]
        imsak, iftar = shift(times[0], c.get('imsakOffset', 0)), times[4]
        cells = [digits(n + 1, lang), date_text(day, lang), digits(imsak, lang), digits(iftar, lang),
                 digits(span(imsak, iftar), lang)]
        rows.append(f'<tr data-date="{day.isoformat()}">' + ''.join(f'<td>{esc(v)}</td>' for v in cells) + '</tr>')
    crumbs = {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': t['index_h1'], 'item': f'{BASE}{lang}/'},
            {'@type': 'ListItem', 'position': 2, 'name': name, 'item': f'{BASE}{lang}/{c["slug"]}/'},
            {'@type': 'ListItem', 'position': 3, 'name': r['link'].format(year=year), 'item': url},
        ],
    }
    head_cells = ''.join(f'<th>{esc(x)}</th>' for x in r['cols'])
    others = ' · '.join(f'<a href="{rel}{lang}/{o["slug"]}/{ramadan_slug(ramadan)}/">{esc(o["names"][lang])}</a>'
                        for o in by_lang[lang] if o is not c)
    # During Ramadan the visitor's day is marked, in the city's own time zone.
    today_js = ('<script>(function(){try{var d=new Intl.DateTimeFormat("en-CA",{timeZone:' + json.dumps(c['tz'])
                + ',year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());'
                'var r=document.querySelector(\'tr[data-date="\'+d+\'"]\');if(r)r.className="now";}catch(e){}})();</script>')
    return '\n'.join([
        head(lang, title, desc, url, rel, jsonld=crumbs),
        f'<body>{top(lang, rel)}<main><div class="wrap">',
        f'<p class="crumbs"><a href="{rel}{lang}/">{esc(t["index_h1"])}</a> › <a href="{rel}{lang}/{c["slug"]}/">{esc(name)}</a></p>',
        f'<h1>{esc(r["h1"].format(city=name, year=year))}</h1>',
        f'<p class="intro">{esc(r["intro"].format(start=date_text(first, lang), eid=date_text(eid, lang)))}</p>',
        f'<div class="tablewrap"><table class="month ramadan"><thead><tr>{head_cells}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
        f'<p class="note">{esc(t["note"].format(method=c["methodTitles"][lang]))}</p>',
        cta(lang, strings, rel, f'ramazan-{c["slug"]}', r['cta_title']),
        f'<p><a href="{rel}{lang}/{c["slug"]}/">{esc(t["h1"].format(city=name))}</a></p>',
        f'<h2>{esc(r["list"].format(year=year))}</h2><p>{others}</p>' if others else '',
        '</div></main>', foot(lang), today_js, '</body></html>',
    ])


RAMADANS = []


def ramadan_link(c):
    """Links to the city's Ramadan timetables."""
    links = []
    for ramadan in RAMADANS:
        lang = c['lang']
        year = digits(date.fromisoformat(ramadan['start']).year, lang)
        links.append(f'<p class="ramadan-link">🌙 <a href="{ramadan_slug(ramadan)}/">{esc(R[lang]["link"].format(year=year))}</a></p>')
    return ''.join(links)


def ramadan_list(lang, by_lang, rel):
    parts = []
    for ramadan in RAMADANS:
        year = digits(date.fromisoformat(ramadan['start']).year, lang)
        items = ' · '.join(f'<a href="{rel}{lang}/{c["slug"]}/{ramadan_slug(ramadan)}/">{esc(c["names"][lang])}</a>'
                           for c in by_lang[lang])
        parts.append(f'<h2>🌙 {esc(R[lang]["list"].format(year=year))}</h2><p>{items}</p>')
    return ''.join(parts)


APP_JSONLD = {
    '@context': 'https://schema.org', '@type': 'MobileApplication',
    'name': 'Huzur Vakti', 'operatingSystem': 'Android, iOS',
    'applicationCategory': 'LifestyleApplication',
    'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'},
    'url': BASE, 'sameAs': [PLAY, APPSTORE],
}


def language_alternates(langs):
    return [(l, f'{BASE}{l}/') for l in langs] + [('x-default', BASE)]


def language_page(lang, by_lang, strings, langs):
    t = T[lang]
    rel = '../'
    url = f'{BASE}{lang}/'
    others = ''.join(f'<li><a href="{rel}{l}/">{esc(T[l]["name"])}</a></li>' for l in langs if l != lang)
    return '\n'.join([
        head(lang, t['index_title'], t['index_desc'], url, rel, language_alternates(langs), APP_JSONLD),
        f'<body>{top(lang, rel)}<main><div class="wrap">',
        f'<h1>{esc(t["index_h1"])}</h1>',
        f'<p class="intro">{esc(strings[lang]["intro"])}</p>',
        f'<p>{esc(strings[lang]["about"])}</p>',
        cta(lang, strings, rel, f'index-{lang}'),
        f'<h2>{esc(t["cities"])}</h2>{city_list(by_lang[lang], lang, rel)}',
        ramadan_list(lang, by_lang, rel),
        f'<h2>{esc(t["languages"])}</h2><ul class="langs">{others}</ul>',
        '</div></main>', foot(lang), '</body></html>',
    ])


def root_page(by_lang, strings, langs):
    rel = ''
    t = T['en']
    blocks = [f'<li><a href="{l}/">{esc(T[l]["name"])}</a></li>' for l in langs]
    featured = ''.join(
        f'<h3 class="country" lang="{l}" dir="{"rtl" if l in RTL else "ltr"}">{esc(T[l]["name"])}</h3>'
        f'<p lang="{l}" dir="{"rtl" if l in RTL else "ltr"}">'
        + ' · '.join(f'<a href="{l}/{c["slug"]}/">{esc(c["names"][l])}</a>' for c in by_lang[l]) + '</p>'
        for l in langs)
    return '\n'.join([
        head('en', 'Huzur Vakti – Prayer Times, Adhan and Qibla', t['index_desc'], BASE, rel,
             language_alternates(langs), APP_JSONLD),
        f'<body>{top("en", rel)}<main><div class="wrap">',
        '<h1>Huzur Vakti</h1>',
        f'<p class="intro">{esc(strings["en"]["intro"])}</p>',
        f'<ul class="langs">{"".join(blocks)}</ul>',
        cta('en', strings, rel, 'root'),
        f'<h2>{esc(t["cities"])}</h2>{featured}',
        '</div></main>', foot('en'), '</body></html>',
    ])


def not_found():
    return '\n'.join([
        head('en', 'Page not found – Huzur Vakti', 'This page does not exist.', BASE, '/huzur-vakti/'),
        f'<body>{top("en", "/huzur-vakti/")}<main><div class="wrap"><h1>404</h1>',
        '<p><a href="/huzur-vakti/">Huzur Vakti</a></p></div></main>', foot('en'), '</body></html>',
    ])


def main():
    data = json.loads((ROOT / 'data' / 'times.json').read_text(encoding='utf-8'))
    strings = json.loads((ROOT / 'data' / 'app_strings.json').read_text(encoding='utf-8'))
    start = date.fromisoformat(data['from'])
    today = datetime.now(timezone.utc).date()
    cities = data['cities']
    langs = [l for l in LANGS if any(c['lang'] == l for c in cities)]
    # Every Ramadan in the data, past ones too: an indexed page that disappears
    # after Eid has to be found again from nothing the next year.
    RAMADANS[:] = data.get('ramadans', [])

    by_lang = {l: [] for l in langs}
    seen = set()
    for c in cities:
        c['slug'] = slugify(c['names']['en'])
        key = (c['lang'], c['slug'])
        if key in seen:
            # The app's own cities come first in cities.json; a GeoNames town
            # that lands on the same slug (a district of Algiers named
            # "Algiers") is the duplicate and is left out.
            print(f'aynı adres atlandı: {key} ({c["id"]})')
            continue
        seen.add(key)
        by_lang[c['lang']].append(c)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'static').mkdir(parents=True)
    for f in (ROOT / 'static').iterdir():
        shutil.copy2(f, OUT / 'static' / f.name)
    (OUT / '.nojekyll').write_text('', encoding='utf-8')
    # Files that must sit at the site root as they are, e.g. Search Console's
    # ownership file (deleting it un-verifies the property).
    for f in (ROOT / 'root').iterdir():
        shutil.copy2(f, OUT / f.name)
    # Hand-written pages (e.g. /indir/: one link that opens AppGallery on Huawei, Play on other Android phones, App Store on iPhone).
    if (ROOT / 'pages').exists():
        shutil.copytree(ROOT / 'pages', OUT, dirs_exist_ok=True)

    urls = [BASE]
    (OUT / 'index.html').write_text(root_page(by_lang, strings, langs), encoding='utf-8')
    for lang in langs:
        (OUT / lang).mkdir()
        (OUT / lang / 'index.html').write_text(language_page(lang, by_lang, strings, langs), encoding='utf-8')
        urls.append(f'{BASE}{lang}/')
        for c in by_lang[lang]:
            folder = OUT / lang / c['slug']
            folder.mkdir()
            (folder / 'index.html').write_text(city_page(c, by_lang, strings, start, today), encoding='utf-8')
            urls.append(f'{BASE}{lang}/{c["slug"]}/')
            for ramadan in RAMADANS:
                rfolder = folder / ramadan_slug(ramadan)
                rfolder.mkdir()
                (rfolder / 'index.html').write_text(ramadan_page(c, by_lang, strings, start, ramadan), encoding='utf-8')
                urls.append(f'{BASE}{lang}/{c["slug"]}/{ramadan_slug(ramadan)}/')
    (OUT / '404.html').write_text(not_found(), encoding='utf-8')

    stamp = today.isoformat()
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sitemap += [f'<url><loc>{u}</loc><lastmod>{stamp}</lastmod></url>' for u in urls]
    sitemap.append('</urlset>')
    (OUT / 'sitemap.xml').write_text('\n'.join(sitemap) + '\n', encoding='utf-8')
    (OUT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n', encoding='utf-8')
    key_file = ROOT / 'data' / 'indexnow.key'
    if key_file.exists():
        key = key_file.read_text(encoding='utf-8').strip()
        (OUT / f'{key}.txt').write_text(key, encoding='utf-8')
    print(f'{len(urls)} sayfa yazıldı ({len(cities)} şehir, {len(langs)} dil); bugün {stamp}, veri {data["from"]} – {data["to"]}')


if __name__ == '__main__':
    main()
