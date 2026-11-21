/* Dashboard admin SIPPER.
   Semua nilai datang dari /admin/live-stats/ yang dihitung dari database, jadi
   tidak ada angka contoh di sisi klien. Teks milik warga (nama, kota,
   deskripsi) selalu ditulis dengan textContent, bukan innerHTML. */
(function () {
  'use strict';

  var root = document.getElementById('sipper-dashboard');
  if (!root) return;

  var STATS_URL = root.dataset.statsUrl;
  var PENGAJUAN_BASE = root.dataset.pengajuanBase;
  var REFRESH_MS = 5000;
  var STATUS_LABEL = {
    menunggu: 'Menunggu',
    disetujui: 'Disetujui',
    ditolak: 'Ditolak',
    perlu_perbaikan: 'Perlu perbaikan'
  };
  var SVG_NS = 'http://www.w3.org/2000/svg';

  var state = {
    paused: false,
    offline: false,
    period: 14,
    // Jam server dipakai sebagai acuan "sekarang" supaya selisih waktu relatif
    // tidak rusak bila jam laptop petugas meleset.
    serverNow: null,
    fetchedAt: null,
    data: null
  };

  var el = {
    state: document.getElementById('sip-live-state'),
    stateText: document.getElementById('sip-live-text'),
    updated: document.getElementById('sip-live-updated'),
    toggle: document.getElementById('sip-live-toggle'),
    pulse: document.getElementById('sip-pulse'),
    pulseSummary: document.getElementById('sip-pulse-summary'),
    rerata: document.getElementById('sip-m-rerata'),
    composition: document.getElementById('sip-composition'),
    queue: document.getElementById('sip-queue'),
    activity: document.getElementById('sip-activity')
  };

  function number(value) {
    if (value === null || value === undefined) return '—';
    return Number(value).toLocaleString('id-ID');
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function relativeTime(iso) {
    if (!iso || state.serverNow === null || state.fetchedAt === null) return '';
    var then = Date.parse(iso);
    if (isNaN(then)) return '';
    var now = state.serverNow + (performance.now() - state.fetchedAt);
    var detik = Math.max(0, Math.round((now - then) / 1000));
    if (detik < 10) return 'baru saja';
    if (detik < 60) return detik + ' detik lalu';
    var menit = Math.round(detik / 60);
    if (menit < 60) return menit + ' menit lalu';
    var jam = Math.round(menit / 60);
    if (jam < 24) return jam + ' jam lalu';
    var hari = Math.round(jam / 24);
    if (hari < 14) return hari + ' hari lalu';
    var tanggal = new Date(then);
    return String(tanggal.getDate()).padStart(2, '0') + '/' +
      String(tanggal.getMonth() + 1).padStart(2, '0') + ' ' +
      String(tanggal.getHours()).padStart(2, '0') + ':' +
      String(tanggal.getMinutes()).padStart(2, '0');
  }

  /* Waktu relatif diperbarui lewat atribut data-at, tanpa membangun ulang baris,
     supaya fokus keyboard dan status hover pengguna tidak hilang tiap detik. */
  function stamp(node, iso) {
    node.dataset.at = iso;
    node.textContent = relativeTime(iso);
    return node;
  }

  function refreshStamps() {
    root.querySelectorAll('[data-at]').forEach(function (node) {
      var teks = relativeTime(node.dataset.at);
      if (node.dataset.prefix) {
        node.textContent = teks + (node.dataset.suffix || '');
      } else {
        node.textContent = teks;
      }
    });
  }

  function setState(kind, label) {
    el.state.classList.toggle('is-stale', kind === 'stale');
    el.state.classList.toggle('is-offline', kind === 'offline');
    el.stateText.textContent = label;
  }

  /* -------------------------------------------------------------- metrik */

  function renderMetrics(data) {
    Object.keys(data.status).forEach(function (key) {
      setText('sip-m-' + key, number(data.status[key]));
      setText('sip-b-' + key, number(data.status[key]));
    });
    setText('sip-m-dokumen', number(data.dokumen_pending));
    setText('sip-m-kartu', number(data.kartu_berlaku));
    setText('sip-m-warga', number(data.warga));

    /* Prapemilahan AI: angka besar = antrean yang masih harus dibaca manusia,
       keterangan = berapa berkas yang sudah lolos ambang mesin. Ambangnya ikut
       dari server supaya label tidak pernah menyebut angka lain. */
    setText('sip-m-ai-review', number(data.ai_review));
    var aiNote = document.getElementById('sip-m-ai-note');
    if (aiNote && data.ai_valid !== undefined) {
      aiNote.textContent = number(data.ai_valid) + ' berkas lolos ambang '
        + number(Math.round(data.ai_ambang)) + '%';
    }

    var dokumen = document.querySelector('#sip-m-dokumen + em');
    if (dokumen) dokumen.textContent = 'dari ' + number(data.dokumen_total) + ' berkas';
    var kartu = document.querySelector('#sip-m-kartu + em');
    if (kartu) kartu.textContent = number(data.kartu_habis) + ' habis atau nonaktif';
    var warga = document.querySelector('#sip-m-warga + em');
    if (warga) warga.textContent = number(data.total_pengajuan) + ' pengajuan total';
    setText('sip-m-terlambat', number(data.antrean_terlambat));
    setText('sip-m-kartu-hampir-habis', number(data.kartu_hampir_habis));
    setText('sip-m-email-gagal', number(data.kegagalan_email_24_jam));
    setText('sip-m-email-gagal-7',
      number(data.kegagalan_email_7_hari) + ' kegagalan dalam 7 hari');
    setText('sip-average-7',
      data.rerata_7_hari === null ? '—' : data.rerata_7_hari.toFixed(1) + ' jam');
    setText('sip-average-30',
      data.rerata_30_hari === null ? '—' : data.rerata_30_hari.toFixed(1) + ' jam');
    el.rerata.textContent = data.rerata_jam === null ? '—' : data.rerata_jam.toFixed(1);
  }

  function renderComposition(data) {
    var total = data.total_pengajuan;
    Object.keys(data.status).forEach(function (key) {
      var bagian = total ? (data.status[key] / total) * 100 : 0;
      var bar = el.composition.querySelector('[data-status="' + key + '"]');
      if (bar) bar.style.width = bagian.toFixed(1) + '%';
      setText('sip-p-' + key, total ? bagian.toFixed(0) + '%' : '—');
    });
  }

  function renderServices(data) {
    var label = {
      ok: 'Normal',
      configured: 'Aktif',
      console: 'Console',
      lokal: 'Lokal',
      aktif: 'Aktif',
      unavailable: 'Tidak tersedia',
      belum_dikonfigurasi: 'Belum dikonfigurasi',
      folder_tidak_ada: 'Folder tidak ada',
      tidak_dapat_ditulis: 'Tidak dapat ditulis',
      belum_dikonfigurasi: 'Belum dikonfigurasi'
    };
    Object.keys(data.layanan || {}).forEach(function (key) {
      var value = data.layanan[key];
      setText('sip-service-' + key, label[value] || value);
      var node = document.getElementById('sip-service-' + key);
      if (node) {
        node.dataset.status = value;
        node.classList.toggle('is-normal',
          value === 'ok' || value === 'configured' || value === 'lokal' || value === 'aktif');
        node.classList.toggle('is-warning',
          value === 'console' || value === 'belum_dikonfigurasi');
        node.classList.toggle('is-danger',
          value === 'unavailable' || value === 'folder_tidak_ada' || value === 'tidak_dapat_ditulis');
      }
    });
  }

  /* ------------------------------------------------------- denyut 14 hari */

  function renderPulse(data) {
    var deret = data.deret_hari || [];
    var ada = deret.some(function (item) { return item.masuk || item.selesai; });
    el.pulse.textContent = '';

    if (!deret.length || !ada) {
      el.pulse.appendChild(element('p', 'sipper-empty',
        'Belum ada pengajuan masuk maupun selesai dalam ' + state.period + ' hari terakhir.'));
      el.pulseSummary.textContent = state.period + ' hari: kosong';
      return;
    }

    var tinggi = 104;
    var lebar = 560;
    var dasar = tinggi;
    var kolom = lebar / deret.length;
    var lebarBar = Math.max(6, kolom * 0.27);
    var jarak = 2;
    var puncak = 1;
    deret.forEach(function (item) {
      puncak = Math.max(puncak, item.masuk, item.selesai);
    });

    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + lebar + ' ' + (tinggi + 20));

    var sumbu = document.createElementNS(SVG_NS, 'line');
    sumbu.setAttribute('x1', '0');
    sumbu.setAttribute('y1', String(dasar + 0.5));
    sumbu.setAttribute('x2', String(lebar));
    sumbu.setAttribute('y2', String(dasar + 0.5));
    sumbu.setAttribute('class', 'sip-axis');
    svg.appendChild(sumbu);

    function rect(x, y, w, h, kelas) {
      var batang = document.createElementNS(SVG_NS, 'rect');
      batang.setAttribute('x', x.toFixed(2));
      batang.setAttribute('y', y.toFixed(2));
      batang.setAttribute('width', w.toFixed(2));
      batang.setAttribute('height', h.toFixed(2));
      batang.setAttribute('rx', '1.5');
      batang.setAttribute('class', kelas);
      return batang;
    }

    deret.forEach(function (item, indeks) {
      var tengah = indeks * kolom + kolom / 2;
      var terakhir = indeks === deret.length - 1;
      var denyut = terakhir ? ' sip-bar--now' : '';

      var masukT = (item.masuk / puncak) * tinggi;
      if (item.masuk) {
        svg.appendChild(rect(tengah - lebarBar - jarak / 2, dasar - masukT,
          lebarBar, masukT, 'sip-bar--masuk' + denyut));
      }
      var selesaiT = (item.selesai / puncak) * tinggi;
      if (item.selesai) {
        svg.appendChild(rect(tengah + jarak / 2, dasar - selesaiT,
          lebarBar, selesaiT, 'sip-bar--selesai' + denyut));
      }

      if (indeks % 2 === 1 || terakhir) {
        var label = document.createElementNS(SVG_NS, 'text');
        label.setAttribute('x', tengah.toFixed(2));
        label.setAttribute('y', String(dasar + 14));
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('class', 'sip-label');
        label.textContent = item.tanggal.slice(8, 10);
        svg.appendChild(label);
      }
    });

    el.pulse.appendChild(svg);

    var hariIni = deret[deret.length - 1];
    el.pulseSummary.textContent = 'Hari ini: ' + number(hariIni.masuk) + ' masuk, ' +
      number(hariIni.selesai) + ' selesai';
    el.pulse.setAttribute('aria-label',
      'Grafik batang 14 hari terakhir. Hari ini ' + hariIni.masuk +
      ' pengajuan masuk dan ' + hariIni.selesai + ' selesai diverifikasi.');
  }

  /* ---------------------------------------------------------------- antrean */

  function renderQueue(data) {
    el.queue.textContent = '';
    if (!data.antrean.length) {
      el.queue.appendChild(element('p', 'sipper-empty',
        'Tidak ada pengajuan yang menunggu petugas.'));
      return;
    }

    var tabel = element('table');
    var kepala = document.createElement('thead');
    var barisKepala = document.createElement('tr');
    ['Menunggu sejak', 'Warga', 'Tujuan', 'Status'].forEach(function (teks) {
      barisKepala.appendChild(element('th', '', teks));
    });
    kepala.appendChild(barisKepala);
    tabel.appendChild(kepala);

    var badan = document.createElement('tbody');
    data.antrean.forEach(function (item) {
      var baris = document.createElement('tr');
      baris.appendChild(stamp(element('td', 'sipper-time'), item.submitted_at));

      var tautan = element('a', '', item.nama);
      tautan.href = PENGAJUAN_BASE + item.pk + '/change/';
      var selNama = element('td');
      selNama.appendChild(tautan);
      baris.appendChild(selNama);

      baris.appendChild(element('td', '', item.kota));

      var selStatus = element('td');
      selStatus.appendChild(element('span', 'sip-status sip-status--' + item.status,
        STATUS_LABEL[item.status] || item.status));
      baris.appendChild(selStatus);
      badan.appendChild(baris);
    });
    tabel.appendChild(badan);
    el.queue.appendChild(tabel);
  }

  /* -------------------------------------------------------------- aktivitas */

  function renderActivity(data) {
    el.activity.textContent = '';
    if (!data.aktivitas.length) {
      el.activity.appendChild(element('li')).appendChild(
        element('span', '', 'Belum ada aktivitas tercatat.'));
      return;
    }

    data.aktivitas.forEach(function (item) {
      var baris = document.createElement('li');
      baris.appendChild(element('b', '',
        item.aksi.charAt(0).toUpperCase() + item.aksi.slice(1)));

      var waktu = stamp(element('small'), item.created_at);
      waktu.dataset.prefix = '1';
      waktu.dataset.suffix = item.user ? ' · ' + item.user : '';
      waktu.textContent = relativeTime(item.created_at) + waktu.dataset.suffix;
      baris.appendChild(waktu);

      baris.appendChild(element('span', '', item.deskripsi));
      el.activity.appendChild(baris);
    });
  }

  /* ------------------------------------------------------------------ loop */

  function tickClock() {
    if (!state.data) return;
    var detik = Math.round((performance.now() - state.fetchedAt) / 1000);
    el.updated.textContent = state.offline
      ? 'Data terakhir ' + detik + ' detik lalu'
      : 'Diperbarui ' + detik + ' detik lalu';
    refreshStamps();
  }

  function apply(data) {
    state.data = data;
    state.serverNow = Date.parse(data.server_time);
    state.fetchedAt = performance.now();
    state.offline = false;
    setState(state.paused ? 'stale' : 'live', state.paused ? 'Jeda' : 'Langsung');
    renderMetrics(data);
    renderServices(data);
    renderComposition(data);
    renderPulse(data);
    renderQueue(data);
    renderActivity(data);
    el.updated.textContent = 'Diperbarui baru saja';

    var offlineAlert = document.getElementById('sip-offline-alert');
    if (offlineAlert) offlineAlert.hidden = true;
    var operationalAlert = document.getElementById('sip-operational-alert');
    var operationalTitle = document.getElementById('sip-operational-alert-title');
    var operationalText = document.getElementById('sip-operational-alert-text');
    var masalah = [];
    if (data.antrean_terlambat) masalah.push(data.antrean_terlambat + ' antrean melewati 48 jam');
    if (data.kartu_hampir_habis) masalah.push(data.kartu_hampir_habis + ' kartu hampir kedaluwarsa');
    if (data.kegagalan_email_24_jam) masalah.push(data.kegagalan_email_24_jam + ' kegagalan email 24 jam');
    if (data.layanan.database !== 'ok') masalah.push('database tidak normal');
    if (data.layanan.media !== 'ok') masalah.push('media tidak dapat ditulis');
    if (operationalAlert && operationalTitle && operationalText) {
      operationalAlert.hidden = masalah.length === 0;
      operationalTitle.textContent = masalah.length ? 'Perhatian operasional' : 'Operasional normal';
      operationalText.textContent = masalah.length
        ? masalah.join('; ') + '.'
        : 'Tidak ada antrean terlambat, kartu mendesak, atau kegagalan layanan utama yang terdeteksi.';
    }
  }

  function failed() {
    state.offline = true;
    setState('offline', 'Terputus');
    el.updated.textContent = 'Tidak dapat menghubungi server; angka terakhir tetap ditampilkan.';
    var alert = document.getElementById('sip-offline-alert');
    if (alert) alert.hidden = false;
  }

  function refresh() {
    if (state.paused || document.hidden || !navigator.onLine) return;
    var separator = STATS_URL.indexOf('?') === -1 ? '?' : '&';
    fetch(STATS_URL + separator + 'period=' + state.period, {
      credentials: 'same-origin',
      headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
      .then(function (respons) {
        if (!respons.ok) throw new Error('HTTP ' + respons.status);
        return respons.json();
      })
      .then(apply)
      .catch(failed);
  }

  el.toggle.addEventListener('click', function () {
    state.paused = !state.paused;
    el.toggle.setAttribute('aria-pressed', String(state.paused));
    el.toggle.textContent = state.paused ? 'Lanjutkan' : 'Jeda';
    setState(state.paused ? 'stale' : 'live', state.paused ? 'Jeda' : 'Langsung');
    if (!state.paused) refresh();
  });

  document.querySelectorAll('.sip-period-picker button[data-period]').forEach(function (button) {
    button.addEventListener('click', function () {
      state.period = Number(button.dataset.period);
      document.querySelectorAll('.sip-period-picker button[data-period]').forEach(function (item) {
        item.classList.toggle('is-active', item === button);
      });
      var judul = document.querySelector('.sipper-pulse-chart .sipper-panel__head h2');
      if (judul) judul.textContent = 'Denyut ' + state.period + ' hari';
      refresh();
    });
  });

  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && !state.paused) refresh();
  });

  setInterval(refresh, REFRESH_MS);
  setInterval(tickClock, 1000);
  refresh();
})();
