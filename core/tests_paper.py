"""Eksperimen terukur untuk artikel KELOMPOK 8 - SIPPER (Workshop Pemrograman Framework).

Dua uji dari panduan: Uji 1 (data ganda dan nama mirip) serta Uji 2 (siklus
pembaruan). Seluruh skenario berjalan lewat jalur HTTP sistem yang sebenarnya
(test client Django) di atas basis data uji (test_sipper_db), memakai identitas
sintetis: NIK 16 digit berawalan nol (tidak mungkin milik orang nyata) dan nama
rekaan. OCR di-mock karena pengenalan gambar bukan variabel yang diuji; sandi
akun uji memakai hasher MD5 agar pembuatan 100+ akun tidak membebani durasi
uji (peng-hash-an sandi tidak terlibat pada jalur yang diukur).

Hasil per kasus ditulis ke paper/uji1-kasus.csv dan paper/uji2-kasus.csv,
ringkasan agregat ke paper/ringkasan-eksperimen.json, supaya tabel artikel
dibangun dari data yang sama persis dengan yang direkam saat uji. Berkas-berkas
itu sudah di-commit dan dikutip artikel, jadi penulisan hanya terjadi bila
`PAPER_UJI_SIMPAN=1` — lihat tulis_csv().
"""
import csv
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from PIL import Image

from .models import KartuDigital, Penduduk, Pengajuan, Pemutakhiran

PAPER_DIR = Path(__file__).resolve().parents[1] / 'paper'
TEST_MEDIA_ROOT = tempfile.gettempdir() + '/sipper-paper-media'
SANDI_UJI = 'sandiuci123'
ORIGIN_UJI = 'Kota Asal Sintetis'
DESTINATION_UJI = 'Kota Tujuan Sintetis'

# 15 pasangan nama mirip (semua rekaan). Orang kiri muncul pada 70 entri unik,
# orang kanan adalah orang berbeda yang didaftarkan belakangan dengan NIK baru.
NAMA_ASLI = [
    'Andi Saputra', 'Siti Rahayu', 'Budi Santoso', 'Dewi Lestari', 'Agus Prasetyo',
    'Rina Wulandari', 'Eko Susanto', 'Fitri Handayani', 'Joko Priyanto', 'Sri Wahyuni',
    'Hendra Gunawan', 'Maya Anggraini', 'Rudi Hartono', 'Lia Permata Sari', 'Tono Wijaya',
]
NAMA_MIRIP = [
    'Andi Saputro', 'Siti Rahayuningsih', 'Budi Santosa', 'Dewi Lestari Putri', 'Agus Prasetio',
    'Rina Wulandari Hapsari', 'Eko Susanti', 'Fitri Handayani Sari', 'Joko Priyatno', 'Sri Wahyuningsih',
    'Hendra Gunarto', 'Maya Anggraini Puspita', 'Rudi Hartanto', 'Lia Permata Sari Dewi', 'Toni Wijaya',
]


def nik_ke(n):
    """NIK sintetis 16 digit berawalan nol: tidak mungkin NIK asli mana pun."""
    return f'{n:016d}'


def png(nama):
    output = BytesIO()
    Image.new('RGB', (1, 1), 'white').save(output, format='PNG')
    return SimpleUploadedFile(nama, output.getvalue(), content_type='image/png')


def pesan_respons(resp):
    if resp.status_code == 302:
        return f'302 -> {resp.url}'
    konteks = getattr(resp, 'context', None) or {}
    teks = [str(m) for m in konteks.get('messages', [])]
    # Permintaan berbalas 302 tidak me-render halaman, jadi pesan sukses
    # sebelumnya menumpuk di sesi dan ikut ter-render pada respons 200
    # berikutnya. Pesan terakhir adalah pesan permintaan yang berjalan.
    return teks[-1] if teks else f'HTTP {resp.status_code}'


def p95(nilai):
    data = sorted(nilai)
    return round(data[min(len(data) - 1, int(0.95 * (len(data) - 1)))], 1)


@override_settings(
    MEDIA_ROOT=TEST_MEDIA_ROOT,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class UjiPaperTests(TestCase):
    rows_uji1 = []
    rows_uji2 = []

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().setUpClass()
        cls.env = {
            'engine': connection.settings_dict['ENGINE'],
            'nama_database_uji': connection.settings_dict['NAME'],
            'host': connection.settings_dict['HOST'],
        }

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        cls.tulis_csv()

    @classmethod
    def tulis_csv(cls):
        if os.getenv('PAPER_UJI_SIMPAN') != '1':
            # Angka di paper/uji*-kasus.csv adalah yang dikutip artikel konferensi, dan
            # latensi berbeda tiap jalan. Run test biasa tidak boleh menimpanya; untuk
            # regenerasi sadar: PAPER_UJI_SIMPAN=1 manage.py test core.tests_paper.
            return
        PAPER_DIR.mkdir(parents=True, exist_ok=True)
        if cls.rows_uji1:
            kolom = ['urutan', 'kategori', 'nama', 'nik', 'hasil_acuan', 'hasil_aktual',
                     'sesuai', 'baris_penduduk_baru', 'pesan_sistem', 'ms']
            with open(PAPER_DIR / 'uji1-kasus.csv', 'w', newline='', encoding='utf-8-sig') as f:
                penulis = csv.DictWriter(f, fieldnames=kolom)
                penulis.writeheader()
                penulis.writerows(cls.rows_uji1)
        if cls.rows_uji2:
            kolom = ['id_kasus', 'kategori', 'pelaku', 'permintaan', 'sebelum', 'usulan',
                     'sesudah', 'status_sebelum', 'status_sesudah', 'verified_by',
                     'verified_at', 'pemutakhiran_baru', 'audit', 'hasil_acuan',
                     'hasil_aktual', 'sesuai', 'ms']
            with open(PAPER_DIR / 'uji2-kasus.csv', 'w', newline='', encoding='utf-8-sig') as f:
                penulis = csv.DictWriter(f, fieldnames=kolom)
                penulis.writeheader()
                penulis.writerows(cls.rows_uji2)
        ringkasan = {
            'dibuat': datetime.now().isoformat(timespec='seconds'),
            'lingkungan': cls.env,
            'uji1': cls.ringkas_uji1(),
            'uji2': cls.ringkas_uji2(),
        }
        with open(PAPER_DIR / 'ringkasan-eksperimen.json', 'w', encoding='utf-8') as f:
            json.dump(ringkasan, f, ensure_ascii=False, indent=2)

    @classmethod
    def ringkas_uji1(cls):
        rows = cls.rows_uji1
        if not rows:
            return {}
        unik = [b for b in rows if b['kategori'] == 'unik']
        duplikat = [b for b in rows if b['kategori'] == 'duplikat']
        mirip = [b for b in rows if b['kategori'] == 'nama mirip']
        return {
            'total_entri': len(rows),
            'unik': {'diuji': len(unik), 'diterima': sum(b['hasil_aktual'] == 'diterima' for b in unik)},
            'duplikat': {
                'diuji': len(duplikat),
                'terdeteksi': sum(b['hasil_aktual'] == 'ditolak' for b in duplikat),
                'terlewat': sum(b['hasil_aktual'] == 'diterima' for b in duplikat),
            },
            'nama_mirip': {
                'diuji': len(mirip),
                'diterima': sum(b['hasil_aktual'] == 'diterima' for b in mirip),
                'salah_tolak': sum(b['hasil_aktual'] == 'ditolak' for b in mirip),
            },
            'latensi_ms': {'median': round(statistics_median(b['ms'] for b in rows), 1),
                           'p95': p95([b['ms'] for b in rows])},
        }

    @classmethod
    def ringkas_uji2(cls):
        rows = cls.rows_uji2
        if not rows:
            return {}
        kategori = {}
        for baris in rows:
            isi = kategori.setdefault(baris['kategori'], {'diuji': 0, 'sesuai': 0})
            isi['diuji'] += 1
            isi['sesuai'] += 1 if baris['sesuai'] else 0
        return {
            'total_skenario': len(rows),
            'per_kategori': kategori,
            'latensi_ms': {'median': round(statistics_median(b['ms'] for b in rows if b['ms']), 1),
                           'p95': p95([b['ms'] for b in rows if b['ms']])},
        }

    def setUp(self):
        cache.clear()

    def _post_pengajuan(self, akun, nama, nik):
        self.client.force_login(akun)
        mulai = time.perf_counter()
        resp = self.client.post('/pengajuan/', {
            'name': nama, 'nik': nik, 'origin': ORIGIN_UJI, 'destination': DESTINATION_UJI,
            'purpose': 'pekerjaan', 'phone': '', 'tanggal_mulai': '', 'perkiraan_kembali': '',
            'ktp': png('ktp.png'), 'kk': png('kk.png'),
        })
        return resp, round((time.perf_counter() - mulai) * 1000, 1)

    @mock.patch('core.views.picu_async')
    def test_uji1_data_ganda_dan_nama_mirip(self, _picu):
        rows = UjiPaperTests.rows_uji1

        def jalankan(kategori, nama, nik, nomor_akun, hasil_acuan):
            akun = User.objects.create_user(username=f'uji{nomor_akun:03d}@uji.invalid',
                                            password=SANDI_UJI, first_name=nama)
            jumlah_sebelum = Penduduk.objects.count()
            resp, ms = self._post_pengajuan(akun, nama, nik)
            # Diterima = pengajuan ini menciptakan baris baru. Untuk duplikat,
            # baris dengan NIK itu sudah ada milik pemohon pertama, jadi
            # keberadaan baris saja tidak bisa dipakai sebagai penanda.
            diterima = Penduduk.objects.count() - jumlah_sebelum == 1
            rows.append({
                'urutan': len(rows) + 1, 'kategori': kategori, 'nama': nama, 'nik': nik,
                'hasil_acuan': hasil_acuan,
                'hasil_aktual': 'diterima' if diterima else 'ditolak',
                'sesuai': (hasil_acuan == 'diterima') == diterima,
                'baris_penduduk_baru': 'ya' if diterima else 'tidak',
                'pesan_sistem': pesan_respons(resp), 'ms': ms,
            })

        # 70 entri unik, urutan tercatat; 15 di antaranya punya "kembaran" nama mirip.
        for i in range(1, 71):
            nama = NAMA_ASLI[i - 1] if i <= 15 else f'Warga Sintetis {i:03d}'
            jalankan('unik', nama, nik_ke(i), i, 'diterima')
        # 15 duplikat: NIK sama dengan identitas sebelumnya (10 nama sama, 5 nama beda).
        for k in range(1, 16):
            nama = NAMA_ASLI[k - 1] if k <= 10 else f'Pemohon Lain {k:02d}'
            jalankan('duplikat', nama, nik_ke(k), 70 + k, 'ditolak')
        # 15 orang berbeda dengan nama mirip, NIK baru: tidak boleh disamakan.
        for k in range(1, 16):
            jalankan('nama mirip', NAMA_MIRIP[k - 1], nik_ke(70 + k), 85 + k, 'diterima')

        unik = [b for b in rows if b['kategori'] == 'unik']
        duplikat = [b for b in rows if b['kategori'] == 'duplikat']
        mirip = [b for b in rows if b['kategori'] == 'nama mirip']
        self.assertEqual(len(rows), 100)
        self.assertEqual(sum(b['hasil_aktual'] == 'diterima' for b in unik), 70)
        self.assertEqual(sum(b['hasil_aktual'] == 'ditolak' for b in duplikat), 15)
        self.assertEqual(sum(b['hasil_aktual'] == 'diterima' for b in mirip), 15)
        self.assertEqual(Penduduk.objects.count(), 85)
        self.assertEqual(Pengajuan.objects.count(), 85)

    @mock.patch('core.views.picu_async')
    def test_uji2_siklus_pembaruan(self, _picu):
        rows = UjiPaperTests.rows_uji2
        petugas = User.objects.create_user(username='petugas@uji.invalid',
                                           password=SANDI_UJI, is_staff=True)

        def buat_warga(seq, nama, disetujui):
            akun = User.objects.create_user(username=f'warga{seq}@uji.invalid',
                                            password=SANDI_UJI, first_name=nama)
            self._post_pengajuan(akun, nama, nik_ke(1000 + seq))
            person = Penduduk.objects.get(user=akun)
            pengajuan = person.pengajuan
            if disetujui:
                self.client.force_login(petugas)
                self.client.post('/petugas/', {'id': pengajuan.pk, 'status': 'disetujui'})
            return akun, person, pengajuan

        akun_a, person_a, pengajuan_a = buat_warga(1, 'A Warga Satu', True)
        akun_b, person_b, pengajuan_b = buat_warga(2, 'B Warga Dua', True)
        akun_c, person_c, pengajuan_c = buat_warga(3, 'C Warga Tiga', False)
        akun_d, person_d, pengajuan_d = buat_warga(4, 'D Warga Empat', False)
        akun_e, person_e, pengajuan_e = buat_warga(5, 'E Warga Lima', False)

        def kondisi(person, pengajuan):
            person.refresh_from_db()
            pengajuan.refresh_from_db()
            verifikator = pengajuan.verified_by.username if pengajuan.verified_by_id else '-'
            return ('|'.join([person.daerah_asal, person.kota_tujuan, person.tujuan]),
                    pengajuan.status, verifikator, 'ada' if pengajuan.verified_at else 'tidak')

        def catat(no, kategori, pelaku, permintaan, sebelum, usulan, sesudah,
                  status_sebelum, status_sesudah, verified_by, verified_at,
                  pemutakhiran_baru, audit, hasil_acuan, hasil_aktual, sesuai, ms):
            rows.append({
                'id_kasus': f'S{no:02d}', 'kategori': kategori, 'pelaku': pelaku,
                'permintaan': permintaan, 'sebelum': sebelum, 'usulan': usulan,
                'sesudah': sesudah, 'status_sebelum': status_sebelum,
                'status_sesudah': status_sesudah, 'verified_by': verified_by,
                'verified_at': verified_at, 'pemutakhiran_baru': pemutakhiran_baru,
                'audit': audit, 'hasil_acuan': hasil_acuan, 'hasil_aktual': hasil_aktual,
                'sesuai': sesuai, 'ms': ms,
            })

        def coba_pemutakhiran(akun, origin, destination, purpose):
            self.client.force_login(akun)
            delta = Pemutakhiran.objects.count()
            mulai = time.perf_counter()
            resp = self.client.post('/pemutakhiran/', {
                'origin': origin, 'destination': destination, 'purpose': purpose})
            ms = round((time.perf_counter() - mulai) * 1000, 1)
            return resp, ms, Pemutakhiran.objects.count() - delta

        # ---- S01-S04: pemutakhiran sah ----
        sebelum, st, vb, va = kondisi(person_a, pengajuan_a)
        resp, ms, delta = coba_pemutakhiran(akun_a, ORIGIN_UJI, 'Kota Baru Satu', 'pekerjaan')
        sesudah, st2, vb2, va2 = kondisi(person_a, pengajuan_a)
        catat(1, 'sah', 'A (warga)', 'ubah kota tujuan', sebelum, 'Kota Asal Sintetis|Kota Baru Satu|pekerjaan',
              sesudah, st, st2, vb2, va2, delta, 'pemutakhiran', 'diterapkan',
              'diterapkan' if sesudah.endswith('Kota Baru Satu|pekerjaan') and delta == 1 else 'gagal',
              sesudah.endswith('Kota Baru Satu|pekerjaan') and delta == 1, ms)

        sebelum, st, vb, va = kondisi(person_a, pengajuan_a)
        resp, ms, delta = coba_pemutakhiran(akun_a, 'Asal Baru Dua', 'Kota Baru Dua', 'pendidikan')
        sesudah, st2, vb2, va2 = kondisi(person_a, pengajuan_a)
        catat(2, 'sah', 'A (warga)', 'ubah tiga field sekaligus', sebelum,
              'Asal Baru Dua|Kota Baru Dua|pendidikan', sesudah, st, st2, vb2, va2, delta,
              'pemutakhiran', 'diterapkan',
              'diterapkan' if sesudah == 'Asal Baru Dua|Kota Baru Dua|pendidikan' and delta == 1 else 'gagal',
              sesudah == 'Asal Baru Dua|Kota Baru Dua|pendidikan' and delta == 1, ms)

        sebelum, st, vb, va = kondisi(person_a, pengajuan_a)
        resp, ms, delta = coba_pemutakhiran(akun_a, 'Asal Baru Dua', 'Kota Baru Dua', 'pendidikan')
        sesudah, st2, vb2, va2 = kondisi(person_a, pengajuan_a)
        catat(3, 'sah', 'A (warga)', 'kirim ulang nilai yang sama', sebelum, sebelum, sesudah,
              st, st2, vb2, va2, delta, 'pemutakhiran', 'diterapkan dan tercatat',
              'diterapkan' if sesudah == sebelum and delta == 1 else 'gagal',
              sesudah == sebelum and delta == 1, ms)

        sebelum, st, vb, va = kondisi(person_a, pengajuan_a)
        resp, ms, delta = coba_pemutakhiran(akun_a, 'Asal Baru Dua', 'Kota Baru Dua', 'keluarga')
        sesudah, st2, vb2, va2 = kondisi(person_a, pengajuan_a)
        catat(4, 'sah', 'A (warga)', 'ubah tujuan merantau', sebelum,
              'Asal Baru Dua|Kota Baru Dua|keluarga', sesudah, st, st2, vb2, va2, delta,
              'pemutakhiran', 'diterapkan',
              'diterapkan' if sesudah.endswith('keluarga') and delta == 1 else 'gagal',
              sesudah.endswith('keluarga') and delta == 1, ms)

        # ---- S05-S09: pemutakhiran tidak lengkap ----
        kasus_tak_lengkap = [
            (5, 'kota tujuan kosong', ORIGIN_UJI, '', 'pekerjaan'),
            (6, 'daerah asal kosong', '', 'Kota X', 'pekerjaan'),
            (7, 'semua isian kosong', '', '', ''),
            (8, 'tujuan tidak resmi', ORIGIN_UJI, 'Kota X', 'acak-adul'),
            (9, 'tujuan kosong', ORIGIN_UJI, 'Kota X', ''),
        ]
        for no, permintaan, origin, destination, purpose in kasus_tak_lengkap:
            sebelum, st, vb, va = kondisi(person_a, pengajuan_a)
            resp, ms, delta = coba_pemutakhiran(akun_a, origin, destination, purpose)
            sesudah, st2, vb2, va2 = kondisi(person_a, pengajuan_a)
            catat(no, 'tidak lengkap', 'A (warga)', permintaan, sebelum,
                  f'{origin}|{destination}|{purpose}', sesudah, st, st2, vb2, va2, delta,
                  '-', 'ditolak', 'ditolak' if sesudah == sebelum and delta == 0 else 'gagal',
                  sesudah == sebelum and delta == 0, ms)

        # ---- S10-S12: menunggu verifikasi ----
        sebelum, st, vb, va = kondisi(person_c, pengajuan_c)
        resp, ms, delta = coba_pemutakhiran(akun_c, ORIGIN_UJI, 'Kota C Baru', 'pekerjaan')
        sesudah, st2, vb2, va2 = kondisi(person_c, pengajuan_c)
        catat(10, 'menunggu verifikasi', 'C (warga)', 'ubah domisili saat pengajuan menunggu',
              sebelum, 'Kota Asal Sintetis|Kota C Baru|pekerjaan', sesudah, st, st2, vb2, va2,
              delta, 'pemutakhiran', 'diterapkan tanpa gerbang persetujuan',
              'diterapkan' if sesudah.endswith('Kota C Baru|pekerjaan') and st2 == 'menunggu' and delta == 1 else 'gagal',
              sesudah.endswith('Kota C Baru|pekerjaan') and st2 == 'menunggu' and delta == 1, ms)

        self.client.force_login(akun_c)
        mulai = time.perf_counter()
        resp = self.client.get('/dashboard/')
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        person_c.refresh_from_db()
        pengajuan_c.refresh_from_db()
        catat(11, 'menunggu verifikasi', 'C (warga)', 'observasi: data aktif vs status pengajuan',
              'menunggu', 'menunggu', person_c.kota_tujuan, 'menunggu', 'menunggu', '-', 'tidak',
              0, '-', 'data aktif sudah berubah, status tetap menunggu',
              f'aktif={person_c.kota_tujuan} status={pengajuan_c.status}',
              person_c.kota_tujuan == 'Kota C Baru' and pengajuan_c.status == 'menunggu', ms)

        self.client.force_login(petugas)
        mulai = time.perf_counter()
        resp = self.client.post('/petugas/', {'id': pengajuan_c.pk, 'status': 'disetujui'})
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        pengajuan_c.refresh_from_db()
        catat(12, 'menunggu verifikasi', 'petugas', 'setujui pengajuan C',
              'menunggu', 'disetujui', pengajuan_c.status, 'menunggu', pengajuan_c.status,
              pengajuan_c.verified_by.username if pengajuan_c.verified_by_id else '-',
              'ada' if pengajuan_c.verified_at else 'tidak', 0, 'verifikasi',
              'disetujui + verifikator + waktu + kartu terbit',
              'disetujui' if pengajuan_c.status == 'disetujui' else 'gagal',
              pengajuan_c.status == 'disetujui' and pengajuan_c.verified_by_id
              and pengajuan_c.verified_at and KartuDigital.objects.filter(penduduk=person_c).exists(), ms)

        # ---- S13-S15: ditolak ----
        self.client.force_login(petugas)
        mulai = time.perf_counter()
        resp = self.client.post('/petugas/', {'id': pengajuan_d.pk, 'status': 'ditolak',
                                              'catatan': 'Foto KTP buram, silakan unggah ulang.'})
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        pengajuan_d.refresh_from_db()
        catat(13, 'ditolak', 'petugas', 'tolak pengajuan D dengan catatan', 'menunggu', 'ditolak',
              pengajuan_d.status, 'menunggu', pengajuan_d.status,
              pengajuan_d.verified_by.username if pengajuan_d.verified_by_id else '-',
              'ada' if pengajuan_d.verified_at else 'tidak', 0, 'verifikasi',
              'ditolak + catatan + verifikator + waktu',
              'ditolak' if pengajuan_d.status == 'ditolak' else 'gagal',
              pengajuan_d.status == 'ditolak' and pengajuan_d.catatan
              and pengajuan_d.verified_by_id and pengajuan_d.verified_at, ms)

        self.client.force_login(petugas)
        mulai = time.perf_counter()
        resp = self.client.post('/petugas/', {'id': pengajuan_e.pk, 'status': 'ditolak'})
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        pengajuan_e.refresh_from_db()
        catat(14, 'ditolak', 'petugas', 'tolak pengajuan E tanpa catatan', 'menunggu', 'ditolak',
              pengajuan_e.status, 'menunggu', pengajuan_e.status, '-',
              'tidak', 0, '-', 'tetap menunggu (penolakan tanpa alasan dilarang)',
              'tetap menunggu' if pengajuan_e.status == 'menunggu' else 'gagal',
              pengajuan_e.status == 'menunggu' and not pengajuan_e.verified_by_id
              and not pengajuan_e.verified_at, ms)

        sebelum, st, vb, va = kondisi(person_d, pengajuan_d)
        resp, ms, delta = coba_pemutakhiran(akun_d, ORIGIN_UJI, 'Kota D Baru', 'pekerjaan')
        sesudah, st2, vb2, va2 = kondisi(person_d, pengajuan_d)
        catat(15, 'ditolak', 'D (warga)', 'pemutakhiran valid setelah pengajuan ditolak',
              sebelum, 'Kota Asal Sintetis|Kota D Baru|pekerjaan', sesudah, st, st2, vb2, va2,
              delta, 'pemutakhiran', 'diterapkan (pemutakhiran tidak dikunci status pengajuan)',
              'diterapkan' if sesudah.endswith('Kota D Baru|pekerjaan') and delta == 1 else 'gagal',
              sesudah.endswith('Kota D Baru|pekerjaan') and delta == 1, ms)

        # ---- S16-S20: perubahan oleh akun lain ----
        sebelum_b, st_b, vb_b, va_b = kondisi(person_b, pengajuan_b)
        sebelum_a = kondisi(person_a, pengajuan_a)[0]
        resp, ms, delta = coba_pemutakhiran(akun_b, ORIGIN_UJI, 'Kota B Baru', 'pekerjaan')
        sesudah_b, st2_b, vb2_b, va2_b = kondisi(person_b, pengajuan_b)
        sesudah_a = kondisi(person_a, pengajuan_a)[0]
        catat(16, 'akun lain', 'B (warga)', 'B ubah data sendiri; data A harus utuh',
              sebelum_b, 'Kota Asal Sintetis|Kota B Baru|pekerjaan', sesudah_b, st_b, st2_b, vb2_b,
              va2_b, delta, 'pemutakhiran', 'data B berubah, data A tidak tersentuh',
              'aman' if sesudah_b.endswith('Kota B Baru|pekerjaan') and sesudah_a == sebelum_a else 'gagal',
              sesudah_b.endswith('Kota B Baru|pekerjaan') and sesudah_a == sebelum_a, ms)

        self.client.force_login(akun_b)
        mulai = time.perf_counter()
        resp = self.client.post(f'/pengajuan/{pengajuan_a.pk}/kirim-ulang/')
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        catat(17, 'akun lain', 'B (warga)', 'kirim ulang pengajuan milik A lewat URL langsung',
              '-', '-', '-', '-', '-', '-', '-', 0, '-', 'ditolak (404)',
              f'HTTP {resp.status_code}', resp.status_code == 404, ms)

        self.client.logout()
        mulai = time.perf_counter()
        resp = self.client.post('/pemutakhiran/', {'origin': 'X', 'destination': 'Y', 'purpose': 'pekerjaan'})
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        catat(18, 'akun lain', 'anonim', 'ubah data tanpa login', '-', '-', '-', '-', '-', '-',
              '-', 0, '-', 'diarahkan ke halaman masuk (302)', f'HTTP {resp.status_code}',
              resp.status_code == 302 and '/login/' in resp.url, ms)

        self.client.force_login(akun_b)
        mulai = time.perf_counter()
        resp = self.client.get('/pemutakhiran/')
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        milik = resp.context['person'].user_id == akun_b.id if resp.status_code == 200 else False
        self.client.force_login(akun_b)
        resp_api = self.client.get('/api/pending-count/')
        catat(19, 'akun lain', 'B (warga)', 'buka halaman pemutakhiran + API khusus petugas',
              '-', '-', '-', '-', '-', '-', '-', 0, '-', 'halaman milik sendiri (200), API petugas ditolak (403)',
              f'HTTP {resp.status_code} / HTTP {resp_api.status_code}',
              milik and resp_api.status_code == 403, ms)

        self.client.force_login(akun_b)
        mulai = time.perf_counter()
        resp = self.client.post('/petugas/', {'id': pengajuan_a.pk, 'status': 'ditolak',
                                              'catatan': 'coba dari akun lain'})
        ms = round((time.perf_counter() - mulai) * 1000, 1)
        pengajuan_a.refresh_from_db()
        catat(20, 'akun lain', 'B (warga)', 'ubah status pengajuan A dari antrean petugas',
              'disetujui', 'ditolak', pengajuan_a.status, 'disetujui', pengajuan_a.status, '-',
              '-', 0, '-', 'ditolak (diarahkan ke halaman masuk), status A utuh',
              f'HTTP {resp.status_code}', resp.status_code == 302 and pengajuan_a.status == 'disetujui', ms)

        # ---- agregat keras (klaim artikel) ----
        self.assertEqual(len(rows), 20)
        self.assertEqual(Pemutakhiran.objects.count(), 7)
        kategori_hasil = {b['kategori'] for b in rows if b['sesuai']}
        self.assertTrue({'sah', 'tidak lengkap', 'menunggu verifikasi', 'ditolak', 'akun lain'}
                        .issubset(kategori_hasil))


def statistics_median(nilai):
    import statistics
    data = list(nilai)
    return statistics.median(data) if data else 0
