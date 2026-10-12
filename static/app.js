// Brings a city page up to the visitor's moment: the page is built once a month,
// so the "today" it was printed with is usually not today any more. All the
// times are already in the page (computed by the app itself); this only picks
// the right day in the city's own time zone and marks the next prayer.
(function () {
  var el = document.getElementById('pt');
  if (!el) return;
  var d = JSON.parse(el.textContent);
  var zero = d.zero || 48;

  function loc(s) {
    if (zero === 48) return s;
    return String(s).replace(/[0-9]/g, function (c) {
      return String.fromCharCode(zero + c.charCodeAt(0) - 48);
    });
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }

  // The wall clock in the city, whatever zone the visitor's device is in.
  function cityNow() {
    var parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: d.tz, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
    }).formatToParts(new Date());
    var o = {};
    parts.forEach(function (p) { o[p.type] = p.value; });
    return { y: +o.year, m: +o.month, d: +o.day, s: (+o.hour % 24) * 3600 + (+o.minute) * 60 + (+o.second) };
  }
  var f = d.from.split('-');
  var origin = Date.UTC(+f[0], +f[1] - 1, +f[2]);
  function indexOf(y, m, day) { return Math.round((Date.UTC(y, m - 1, day) - origin) / 86400000); }
  function dayTimes(i) {
    var raw = d.days.substr(i * 24, 24);
    if (raw.length < 24) return null;
    var out = [];
    for (var k = 0; k < 6; k++) out.push(raw.substr(k * 4, 2) + ':' + raw.substr(k * 4 + 2, 2));
    return out;
  }
  function secs(t) { return (+t.substr(0, 2)) * 3600 + (+t.substr(3, 2)) * 60; }

  var cards = document.querySelectorAll('.today li');
  var names = [];
  cards.forEach(function (li) { names.push(li.querySelector('.name').textContent); });
  var cd = document.querySelector('.countdown');
  var dateline = document.querySelector('.dateline');

  var shownDay = null;
  function render() {
    var now = cityNow();
    var i = indexOf(now.y, now.m, now.d);
    var today = dayTimes(i);
    if (!today) return;
    var key = now.y + '-' + now.m + '-' + now.d;
    if (key !== shownDay) {
      shownDay = key;
      cards.forEach(function (li, k) { li.querySelector('.time').textContent = loc(today[k]); });
      if (dateline) {
        try {
          dateline.textContent = new Intl.DateTimeFormat(d.locale, {
            timeZone: d.tz, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
          }).format(new Date());
        } catch (e) { /* keep the printed date */ }
      }
      renderMonth(now);
    }
    var next = -1;
    for (var k = 0; k < 6; k++) { if (secs(today[k]) > now.s) { next = k; break; } }
    var target, label;
    if (next >= 0) {
      target = secs(today[next]);
      label = names[next];
    } else {
      var tomorrow = dayTimes(i + 1);
      if (!tomorrow) return;
      target = secs(tomorrow[0]) + 86400;
      label = names[0];
    }
    // After isha the next one is tomorrow's fajr, which is not on these cards.
    cards.forEach(function (li, k) { li.classList.toggle('next', k === next); });
    if (cd) {
      var left = Math.max(0, target - now.s);
      var text = pad(Math.floor(left / 3600)) + ':' + pad(Math.floor(left % 3600 / 60)) + ':' + pad(left % 60);
      cd.innerHTML = '';
      cd.appendChild(document.createTextNode(cd.getAttribute('data-label') + ': ' + label + ' ' + d.sep + ' '));
      var strong = document.createElement('strong');
      strong.textContent = loc(text);
      cd.appendChild(strong);
    }
  }

  function renderMonth(now) {
    var table = document.querySelector('table.month');
    if (!table) return;
    var want = now.y + '-' + pad(now.m);
    var body = table.tBodies[0];
    if (table.getAttribute('data-month') !== want) {
      var first = indexOf(now.y, now.m, 1);
      var length = new Date(Date.UTC(now.y, now.m, 0)).getUTCDate();
      var rows = [];
      for (var day = 1; day <= length; day++) {
        var t = dayTimes(first + day - 1);
        if (!t) break;
        rows.push('<tr data-d="' + day + '"><td>' + loc(day) + '</td><td>' + t.map(loc).join('</td><td>') + '</td></tr>');
      }
      if (!rows.length) return;
      body.innerHTML = rows.join('');
      table.setAttribute('data-month', want);
      var title = document.getElementById('month-title');
      if (title && d.months) title.textContent = d.monthTitle.replace('{month}', d.months[now.m - 1]).replace('{year}', loc(now.y));
    }
    Array.prototype.forEach.call(body.rows, function (r) {
      r.classList.toggle('now', +r.getAttribute('data-d') === now.d);
    });
  }

  render();
  setInterval(render, 1000);
})();
