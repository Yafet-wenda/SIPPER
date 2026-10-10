"""Tes laporan PDF verifikasi petugas: siapa boleh mengunduh, apa isinya,
dan apakah penarikannya meninggalkan jejak audit.

NIK, nama, dan alamat sengaja dipakai utuh sebagai penanda: pageCompression=0
di core.pdf_report membuat teks di dalam berkas bisa dicari, jadi tes ini benar
memeriksa isi dokumen, bukan hanya header responsnya.
"""
import shutil
from datetime import date
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan
from .pdf_report import _teks
from .tests import TEST_MEDIA_ROOT


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class LaporanPdfTests(TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.warga = User.objects.create_user(username='warta@example.com', password='password123')
        self.petugas = User.objects.create_user(username='petugas@example.com', password='password123', is_staff=True)
        self.penduduk = Penduduk.objects.create(
            user=self.warga, nama='Otomasi Warga', nik='9606060606060606',
            daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pekerjaan',
        )
        self.pengajuan = Pengajuan.objects.create(penduduk=self.penduduk, status='disetujui', catatan='Berkas sesuai')
        self.dokumen = Dokumen.objects.create(
            penduduk=self.penduduk, nama='ktp.png', jenis='ktp',
            file='dokumen/ktp.png', ukuran=20480, status='valid',
            ocr_confidence=91.5, extracted_nik='9606060606060606',
            extracted_data={'nama': 'OTOMASI WARGA', 'nik': '9606060606060606', 'alamat': 'JL SENTANI RTRW'},
            ai_verified=True, ai_verification_notes='NIK cocok', ocr_text='isi teks ocr',
        )

    def alamat_laporan(self, pk=None):
        return f'/petugas/pengajuan/{pk if pk is not None else self.pengajuan.pk}/laporan.pdf'

    def test_pengunjung_anonim_diarahkan_ke_login(self):
        response = self.client.get(self.alamat_laporan())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/login/'))

    def test_warga_biasa_tidak_mengunduh_laporan_pribadinya_sendiri(self):
        # Bukan celah: laporan data lengkap memang jalur kerja petugas. Warga
        # tetap melihat datanya sendiri di dashboard, tanpa berkas PDF berisi
        # hasil OCR dan catatan internal.
        self.client.force_login(self.warga)
        response = self.client.get(self.alamat_laporan())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith('/login/'))

    def test_petugas_mengunduh_laporan_dan_tercatat_di_audit(self):
        self.client.force_login(self.petugas)
        response = self.client.get(self.alamat_laporan())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('attachment', response['Content-Disposition'])
        # Berkas berisi NIK dan hasil OCR: browser bersama tidak boleh menyimpannya.
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        log = AuditLog.objects.get(aksi='cetak_laporan')
        self.assertEqual(log.user, self.petugas)
        self.assertIn(str(self.pengajuan.pk), log.deskripsi)

    def test_laporan_memuat_isian_warga_dan_hasil_baca_ocr(self):
        self.client.force_login(self.petugas)
        isi = self.client.get(self.alamat_laporan()).content
        for penanda in [b'Otomasi Warga', b'9606060606060606', b'Jayapura', b'Malang',
                        b'Berkas sesuai', b'JL SENTANI RTRW', b'NIK cocok', b'Laporan Verifikasi']:
            self.assertIn(penanda, isi, f'{penanda!r} tidak ditemukan di PDF')

    def test_laporan_tidak_mengandung_teks_rahasia_dari_template(self):
        # CSRF token halaman detail tidak boleh ikut tersalin ke berkas.
        self.client.force_login(self.petugas)
        self.assertNotIn(b'csrfmiddlewaretoken', self.client.get(self.alamat_laporan()).content)

    def test_pengajuan_yang_tidak_ada_untuk_petugas_memberi_404(self):
        self.client.force_login(self.petugas)
        self.assertEqual(self.client.get(self.alamat_laporan(pk=999999)).status_code, 404)

    def test_hasil_scan_tanpa_tautan_data_lengkap_bagi_pengunjung_umum(self):
        KartuDigital.objects.create(penduduk=self.penduduk, kode='SPR-SCAN-0001', berlaku_sampai='2027-01-01')
        halaman = self.client.get('/kartu/SPR-SCAN-0001/').content
        self.assertNotIn(b'Lihat data lengkap', halaman)
        self.assertNotIn(b'/petugas/pengajuan/', halaman)

    def test_hasil_scan_menampilkan_tautan_petugas_yang_sudah_login(self):
        KartuDigital.objects.create(penduduk=self.penduduk, kode='SPR-SCAN-0002', berlaku_sampai='2027-01-01')
        self.client.force_login(self.petugas)
        response = self.client.get('/kartu/SPR-SCAN-0002/')
        self.assertContains(response, 'Lihat data lengkap')
        self.assertContains(response, f'/petugas/pengajuan/{self.pengajuan.pk}/')

    def test_laporan_bisa_dibuat_meski_belum_ada_kartu_dan_dokumen(self):
        warga = User.objects.create_user(username='kosong@example.com', password='password123')
        penduduk = Penduduk.objects.create(user=warga, nama='Warga kosong', nik='9707070707070707',
                                           daerah_asal='Merauke', kota_tujuan='Surabaya', tujuan='sekolah')
        Pengajuan.objects.create(penduduk=penduduk, status='menunggu')
        self.client.force_login(self.petugas)
        response = self.client.get(f'/petugas/pengajuan/{penduduk.pengajuan.pk}/laporan.pdf')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Warga kosong', response.content)
        self.assertIn(b'Belum ada berkas', response.content)

    def test_tanggal_pendaftaran_warga_tidak_membatalkan_pembuatan_laporan(self):
        # Regresi: tanggal_mulai/perkiraan_kembali adalah DateField (bukan
        # datetime). Pernah membuat laporan 500 karena timezone.is_aware()
        # dipanggil pada objek date.
        self.penduduk.tanggal_mulai = date(2026, 9, 1)
        self.penduduk.perkiraan_kembali = date(2027, 3, 1)
        self.penduduk.save()
        self.client.force_login(self.petugas)
        response = self.client.get(self.alamat_laporan())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'01/09/2026', response.content)
        self.assertIn(b'01/03/2027', response.content)

    def test_karakter_di_luar_winansi_diganti_sebelum_dicetak(self):
        # Helvetica reportlab hanya mengenal WinAnsi; karakter lain jadi kotak
        # kosong di berkas PDF, jadi diganti padanan ASCII lebih dulu. Tanda
        # ampersand ikut di-escape karena nilai dimasukkan ke Paragraph.
        self.assertEqual(_teks('PT — X → 1 & Co'), 'PT - X &gt; 1 &amp; Co')
        self.assertTrue(_teks('x' * 400).endswith('...'))
        self.assertEqual(len(_teks('x' * 400)), 323)  # 320 karakter + '...'

    def test_nilai_warga_berisi_pisah_panjang_tetap_bisa_dicetak(self):
        self.dokumen.extracted_data['alamat'] = 'JL BESAR — NO 12'
        self.dokumen.save()
        self.client.force_login(self.petugas)
        response = self.client.get(self.alamat_laporan())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'JL BESAR - NO 12', response.content)
        self.assertNotIn(b'\xe2\x80\x94', response.content)

    def test_ampersand_hanya_di_escape_satu_kali(self):
        # Label dan nilai sama-sama lewat _teks. Kalau salah satu meng-escape
        # dua kali, 'A & B' tercetak sebagai 'A &amp; B' di berkas.
        self.dokumen.extracted_data = {'Kunci & uji': 'PT A & B'}
        self.dokumen.save()
        self.client.force_login(self.petugas)
        isi = self.client.get(self.alamat_laporan()).content
        self.assertIn(b'PT A & B', isi)
        self.assertIn(b'Kunci & Uji', isi)  # nama field ikut di-title-case
        self.assertNotIn(b'&amp;', isi)

    def test_extracted_data_berbentuk_list_tidak_membuat_laporan_gagal(self):
        self.dokumen.extracted_data = ['baris satu', 'baris dua']
        self.dokumen.save()
        self.client.force_login(self.petugas)
        response = self.client.get(self.alamat_laporan())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'baris satu', response.content)
