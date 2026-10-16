"""Tes modul AI OCR: rumus skor, jalur pemrosesan berkas, dan panel review admin."""

import shutil
import tempfile
from importlib import import_module
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from core import ocr_processor
from core.ai_verifikasi import (
    AMBAT_VALID, JENIS_BERNILAI, baris_perbandingan, hitung_skor, nilai_berkas,
)
from core.ktp_parser import parse_ktp_data as parse_ktp_parser
from core.models import AuditLog, Dokumen, Penduduk

from . import admin as admin_modul
from .models import TinjauanOcr

TEST_MEDIA_ROOT = tempfile.gettempdir() + '/sipper-test-ai-ocr'


def warga_palsu(nik='9101010101010101', nama='Ani Lestari'):
    """Instance Penduduk tanpa disimpan ke database: penilaian hanya baca atribut."""
    return Penduduk(nik=nik, nama=nama)


class RumusSkorTests(TestCase):
    """Skor dan ambang 85% persis seperti yang dipaparkan laporan."""

    def test_berkas_sempurna_lolos_ambang(self):
        hasil = nilai_berkas(
            warga_palsu(),
            {'nik': '9101010101010101', 'nama': 'Ani Lestari'},
            96.0, 'ktp',
        )
        self.assertEqual(hasil['prescreen'], 'valid')
        self.assertGreater(hasil['skor'], AMBAT_VALID)

    def test_nik_beda_selalu_dibawah_ambang(self):
        """NIK berbobot 0,45: kalau salah, skor maksimal tinggal 55 -> review."""
        hasil = nilai_berkas(
            warga_palsu(),
            {'nik': '9999999999999999', 'nama': 'Ani Lestari'},
            99.0, 'ktp',
        )
        self.assertEqual(hasil['prescreen'], 'review')
        self.assertLessEqual(hasil['skor'], 55.0)

    def test_tepat_di_ambang_tidak_disebut_valid(self):
        """Laporan menulis "> 85%". Nilai 85,0 pas tidak boleh dibulatkan naik."""
        data = {'nik': '9101010101010101', 'nama': 'Ani Lestari'}
        skor = hitung_skor(baris_perbandingan(warga_palsu(), data, 40.0))
        self.assertEqual(skor, 85.0)
        self.assertEqual(nilai_berkas(warga_palsu(), data, 40.0, 'ktp')['prescreen'], 'review')

    def test_nik_berformat_spasi_tetap_dicocokkan(self):
        hasil = nilai_berkas(
            warga_palsu(),
            {'nik': '9101 0101 0101 0101', 'nama': 'Ani Lestari'},
            96.0, 'ktp',
        )
        self.assertEqual(hasil['prescreen'], 'valid')

    def test_urutan_kata_nama_tidak_menjatuhkan_skor(self):
        """OCR pada foto miring sering membalik urutan kata nama."""
        baris = baris_perbandingan(warga_palsu(), {'nama': 'LESTARI ANI'}, 96.0)
        nama = [b for b in baris if b['field'] == 'nama'][0]
        self.assertEqual(nama['kecocokan'], 1.0)

    def test_berkas_non_ktp_tidak_dipaksa_menjadi_skor(self):
        selain_ktp = [kode for kode, _ in Dokumen.JENIS if kode not in JENIS_BERNILAI]
        self.assertTrue(selain_ktp)
        for jenis in selain_ktp:
            hasil = nilai_berkas(warga_palsu(), {'nik': '9101010101010101'}, 99.0, jenis)
            self.assertIsNone(hasil['skor'], f'{jenis} tidak boleh punya skor')
            self.assertEqual(hasil['prescreen'], 'belum_dinilai')

    def test_catatan_menyebut_angka_dan_keputusannya(self):
        catatan = nilai_berkas(warga_palsu(), {'nik': '1'}, 10.0, 'ktp')['catatan']
        self.assertIn('Kecocokan', catatan)
        self.assertIn('review manual', catatan.lower())


class ParserKtpTests(TestCase):
    """Jaga agar bug bayangan nama tidak kembali."""

    def test_ocr_processor_memakai_parser_dari_ktp_parser(self):
        """Dulu ocr_processor mendefinisikan ulang parse_ktp_data yang lebih lemah,
        sehingga parser format kolom di ktp_parser.py tidak pernah terpakai."""
        self.assertIs(ocr_processor.parse_ktp_data, parse_ktp_parser)

    def test_format_kolom_terbaca(self):
        teks = ('PROVINSI PAPUA NIK 9101010101010101 Nama ANI LESTARI '
                'Tempat/Tgl Lahir SENTANI, 01-01-1995 Jenis Kelamin LAKI-LAKI '
                'Agama KRISTEN Alamat JL SENTANI NO 5 RT/RW 001/002')
        self.assertEqual(parse_ktp_parser({'text': teks}).get('nik'), '9101010101010101')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class JalurPemrosesanTests(TestCase):
    """Proses berkas: pilihan praproses, berkas PDF, dan penulisan hasil."""

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.warga = Penduduk.objects.create(
            nama='Ani Lestari', nik='9101010101010101', daerah_asal='Sentani',
            kota_tujuan='Surabaya', tujuan='pekerjaan')

    def berkas(self, nama='ktp.png', jenis='ktp'):
        isi = b'%PDF-1.4 palsu' if nama.endswith('.pdf') else b'\x89PNG palsu'
        return Dokumen.objects.create(
            penduduk=self.warga, nama=nama, jenis=jenis,
            file=SimpleUploadedFile(nama, isi))

    def test_confidence_rendah_dicoba_ulang_dengan_praproses_agresif(self):
        panggilan = []

        def pura(path, lang='ind+eng', aggressive_preprocess=False):
            panggilan.append(aggressive_preprocess)
            return {'text': 'x' * 80, 'confidence': 20 if not aggressive_preprocess else 75}

        with mock.patch.object(ocr_processor, 'extract_text_from_image', pura):
            hasil = ocr_processor.ekstrak_dengan_pilihan_praproses('apa.png')
        self.assertEqual(panggilan, [False, True], 'jalur agresif harus dicoba')
        self.assertEqual(hasil['confidence'], 75)

    def test_confidence_tinggi_tidak_memicu_praproses_kedua(self):
        panggilan = []

        def pura(path, lang='ind+eng', aggressive_preprocess=False):
            panggilan.append(aggressive_preprocess)
            return {'text': 'x' * 80, 'confidence': 95}

        with mock.patch.object(ocr_processor, 'extract_text_from_image', pura):
            ocr_processor.ekstrak_dengan_pilihan_praproses('apa.png')
        self.assertEqual(panggilan, [False])

    def test_pdf_dilewati_dengan_alasan_tertulis(self):
        doc = self.berkas('kk-scan.pdf', 'kk')
        hasil = ocr_processor.process_document(doc)
        doc.refresh_from_db()
        self.assertFalse(hasil['success'])
        self.assertTrue(hasil.get('skipped'), 'PDF bukan kegagalan yang perlu diulang')
        self.assertEqual(doc.ai_prescreen, 'belum_dinilai')
        self.assertIn('PDF', doc.ai_verification_notes)

    def test_hasil_ktp_dinilai_dan_tersimpan_di_model(self):
        doc = self.berkas()
        teks = ('NIK 9101010101010101 Nama ANI LESTARI Tempat/Tgl Lahir SENTANI, '
                '01-01-1995 Alamat JL SENTANI NO 5 RT/RW 001/002 Agama KRISTEN')
        with mock.patch.object(ocr_processor, 'ekstrak_dengan_pilihan_praproses',
                               return_value={'text': teks, 'confidence': 96.0}):
            hasil = ocr_processor.process_document(doc)
        doc.refresh_from_db()
        self.assertTrue(hasil['success'])
        self.assertEqual(doc.extracted_nik, '9101010101010101')
        self.assertEqual(doc.ai_prescreen, 'valid')
        self.assertTrue(doc.ai_verified)
        self.assertGreater(doc.ai_score, AMBAT_VALID)
        self.assertIsNotNone(doc.ocr_processed_at)

    def test_keputusan_petugas_saat_ocr_berjalan_tidak_ditimpa(self):
        """Salinan basi dari thread OCR tidak boleh menulis ulang kolom lain.

        Skenario nyata: berkas masuk, thread OCR membacanya, lalu Tesseract
        berjalan beberapa detik (jalur agresif mencoba empat mode PSM). Selama
        itu petugas yang sudah membuka berkas yang sama bisa menekan Valid.
        Kalau hasil OCR disimpan penuh, status yang tadi dibaca thread — masih
        'pending' — ikut ditulis kembali dan keputusan petugas hilang tanpa jejak
        audit. Panel review menjanjikan mesin tidak mengubah status, jadi hanya
        kolom hasil OCR/AI yang boleh tersimpan.
        """
        doc = self.berkas()
        teks = ('NIK 9101010101010101 Nama ANI LESTARI Tempat/Tgl Lahir SENTANI, '
                '01-01-1995 Alamat JL SENTANI NO 5 RT/RW 001/002 Agama KRISTEN')
        salinan_thread = Dokumen.objects.get(pk=doc.pk)
        doc.status = 'valid'
        doc.save(update_fields=['status'])
        with mock.patch.object(ocr_processor, 'ekstrak_dengan_pilihan_praproses',
                               return_value={'text': teks, 'confidence': 96.0}):
            hasil = ocr_processor.process_document(salinan_thread)
        tersimpan = Dokumen.objects.get(pk=doc.pk)
        self.assertTrue(hasil['success'])
        self.assertEqual(tersimpan.status, 'valid', 'status hasil keputusan petugas')
        self.assertEqual(tersimpan.ai_prescreen, 'valid', 'kolom AI tetap ditulis mesin')
        self.assertIsNotNone(tersimpan.ocr_text)

    def test_berkas_hilang_tidak_meninggalkan_panel_kosong(self):
        doc = self.berkas()
        doc.file.delete(save=False)
        hasil = ocr_processor.process_document(doc)
        doc.refresh_from_db()
        self.assertFalse(hasil['success'])
        self.assertEqual(doc.ai_prescreen, 'belum_dinilai')
        self.assertTrue(doc.ai_verification_notes)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PanelReviewAdminTests(TestCase):
    """Blok "AI OCR" di admin: daftar, filter, koreksi manual, dan batas izin."""

    def setUp(self):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        self.superuser = User.objects.create_superuser(
            username='boss@example.com', email='boss@example.com', password='password123')
        self.warga = Penduduk.objects.create(
            nama='Ani Lestari', nik='9101010101010101', daerah_asal='Sentani',
            kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.berkas = Dokumen.objects.create(
            penduduk=self.warga, nama='ktp.png', jenis='ktp',
            file='dokumen/2026/10/ktp.png',
            ocr_text='NIK 9999 Nama ANI', ocr_confidence=41.0,
            extracted_nik='9999999999999999',
            extracted_data={'nik': '9999999999999999', 'nama': 'ANI'},
            ai_score=12.3, ai_prescreen='review',
            ai_verification_notes='Kecocokan 12.3%',
            ocr_processed_at=timezone.now())

    def test_halaman_utama_admin_punya_blok_ai_ocr(self):
        self.client.force_login(self.superuser)
        isi = self.client.get('/admin/').content.decode()
        self.assertIn('AI OCR', isi, 'modul AI OCR harus tampil sebagai blok tersendiri')
        self.assertIn('/admin/ai_ocr/tinjauanocr/', isi)

    def test_changelist_tampil_skor_dan_hasil_prapemilahan(self):
        self.client.force_login(self.superuser)
        isi = self.client.get('/admin/ai_ocr/tinjauanocr/').content.decode()
        self.assertIn('Ani Lestari', isi)
        self.assertIn('Perlu review manual', isi)
        self.assertIn('12.3%', isi)

    def test_filter_prapemilahan_hanya_tampilkan_yang_cocok(self):
        Dokumen.objects.create(
            penduduk=self.warga, nama='ktp2.png', jenis='ktp',
            file='dokumen/2026/10/ktp2.png', ocr_confidence=99.0,
            extracted_nik='9101010101010101',
            extracted_data={'nik': '9101010101010101', 'nama': 'Ani Lestari'},
            ai_score=99.0, ai_prescreen='valid', ocr_processed_at=timezone.now())
        self.client.force_login(self.superuser)
        isi = self.client.get('/admin/ai_ocr/tinjauanocr/?ai_prescreen=valid').content.decode()
        self.assertIn('99.0%', isi)
        self.assertNotIn('12.3%', isi, 'baris berstatus review tidak boleh ikut tampil')

    def test_form_review_menampilkan_perbandingan_formulir_dengan_ocr(self):
        self.client.force_login(self.superuser)
        isi = self.client.get(
            f'/admin/ai_ocr/tinjauanocr/{self.berkas.pk}/change/').content.decode()
        self.assertIn('Isian formulir', isi)
        self.assertIn('Hasil OCR', isi)
        self.assertIn('9101010101010101', isi, 'NIK dari formulir harus terlihat')
        self.assertIn('Koreksi manual hasil OCR', isi)

    def test_teks_hasil_ocr_terlihat_saat_form_dibuka(self):
        """Petugas membuka panel ini justru untuk membaca isi berkas.

        Selama teks mentah disimpan di fieldset ber-class `collapse`, layar
        pertama form review terlihat kosong dan muncul pertanyaan "hasil OCR-nya
        di mana". Jadi teksnya harus ada di HTML tanpa perlu diklik dulu.
        """
        self.client.force_login(self.superuser)
        isi = self.client.get(
            f'/admin/ai_ocr/tinjauanocr/{self.berkas.pk}/change/').content.decode()
        self.assertIn('NIK 9999 Nama ANI', isi, 'teks OCR harus langsung terlihat')
        self.assertIn('sip-ai-teks', isi)
        self.assertNotIn('<fieldset class="module collapsed"', isi,
                         'fieldset keluaran mesin tidak boleh ditutup rapat')

    def test_form_berkas_non_ktp_menjelaskan_tanpa_tabel_kosong(self):
        kk = Dokumen.objects.create(
            penduduk=self.warga, nama='kk.png', jenis='kk',
            file='dokumen/2026/10/kk.png', ocr_confidence=80.0,
            extracted_data={'no_kk': '9101010101010101'}, ocr_processed_at=timezone.now())
        self.client.force_login(self.superuser)
        isi = self.client.get(f'/admin/ai_ocr/tinjauanocr/{kk.pk}/change/').content.decode()
        self.assertIn('tidak punya field padanannya', isi)
        self.assertNotIn('<table class="sip-ai-tabel"', isi,
                         'berkas non-KTP tidak boleh menampilkan tabel kosong')
        self.assertIn('Belum dinilai', isi)

    def test_koreksi_manual_menghitung_ulang_skor_dan_dicatat(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            f'/admin/ai_ocr/tinjauanocr/{self.berkas.pk}/change/',
            {'extracted_nik': '9101010101010101',
             'extracted_nama': 'Ani Lestari',
             'ai_verification_notes': 'Kecocokan 12.3%',
             '_save': 'Simpan'})
        self.assertEqual(response.status_code, 302)
        self.berkas.refresh_from_db()
        self.assertEqual(self.berkas.ai_prescreen, 'valid')
        self.assertGreater(self.berkas.ai_score, AMBAT_VALID)
        self.assertTrue(self.berkas.ai_verified)
        self.assertEqual(self.berkas.extracted_data['nik'], '9101010101010101',
                         'NIK harus tersinkron ke data terstruktur')
        self.assertEqual(self.berkas.extracted_data['nama'], 'Ani Lestari')
        log = AuditLog.objects.filter(aksi='ai_koreksi_manual').first()
        self.assertIsNotNone(log, 'koreksi tangan wajib meninggalkan jejak audit')
        self.assertEqual(log.user, self.superuser)

    def test_mengubah_kolom_lain_tidak_menimpa_catatan_petugas(self):
        """Tanpa koreksi nilai OCR, catatan tulisan tangan petugas tetap utuh."""
        self.client.force_login(self.superuser)
        self.client.post(
            f'/admin/ai_ocr/tinjauanocr/{self.berkas.pk}/change/',
            {'extracted_nik': '9999999999999999', 'extracted_nama': 'ANI',
             'ai_verification_notes': 'Catatan petugas dipertahankan', '_save': 'Simpan'})
        self.berkas.refresh_from_db()
        self.assertEqual(self.berkas.ai_verification_notes, 'Catatan petugas dipertahankan')

    def test_aksi_proses_ulang_mengirim_setiap_berkas_ke_mesin(self):
        self.client.force_login(self.superuser)
        with mock.patch.object(admin_modul, 'threading') as th:
            response = self.client.post(
                '/admin/ai_ocr/tinjauanocr/',
                {'action': 'proses_ulang_ocr', '_selected_action': [self.berkas.pk]})
        self.assertEqual(response.status_code, 302)
        th.Thread.assert_called_once()
        self.assertEqual(th.Thread.call_args.kwargs['args'], (self.berkas.pk,))
        from core.views import _trigger_ocr_async
        self.assertIs(th.Thread.call_args.kwargs['target'], _trigger_ocr_async)

    def test_aksi_tandai_review_manual_mencatat_audit(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            '/admin/ai_ocr/tinjauanocr/',
            {'action': 'tandai_review_manual', '_selected_action': [self.berkas.pk]})
        self.assertEqual(response.status_code, 302)
        self.berkas.refresh_from_db()
        self.assertEqual(self.berkas.ai_prescreen, 'review')
        self.assertFalse(self.berkas.ai_verified)
        self.assertIn('Ditandai perlu review manual oleh', self.berkas.ai_verification_notes)
        self.assertTrue(AuditLog.objects.filter(aksi='ai_tandai_review').exists())

    def test_warga_tidak_bisa_membuka_panel(self):
        warga = User.objects.create_user(username='warga@example.com', password='password123')
        self.client.force_login(warga)
        self.assertNotEqual(self.client.get('/admin/ai_ocr/tinjauanocr/').status_code, 200)

    def test_panel_tidak_bisa_menambah_atau_menghapus_berkas(self):
        """Proxy menunjuk baris dokumen yang sama: tambah/hapus ditutup di sini."""
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get('/admin/ai_ocr/tinjauanocr/add/').status_code, 403)
        response = self.client.post(
            f'/admin/ai_ocr/tinjauanocr/{self.berkas.pk}/delete/', {'post': 'yes'})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Dokumen.objects.filter(pk=self.berkas.pk).exists())

    def test_ekspor_csv_berisi_skor_dan_keputusan(self):
        import csv
        import io
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/ai_ocr/tinjauanocr/export.csv/')
        self.assertEqual(response.status_code, 200)
        baris = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(baris[0][0], 'Warga')
        self.assertIn('12.3', ''.join(baris[1]))
        self.assertIn('Perlu review manual', ''.join(baris[1]))

    def test_prapemilahan_tidak_pernah_mengubah_status_dokumen(self):
        """Janji panel: mesin hanya memilah antrean, keputusan tetap manusia."""
        self.client.force_login(self.superuser)
        status_awal = self.berkas.status
        self.client.post(
            f'/admin/ai_ocr/tinjauanocr/{self.berkas.pk}/change/',
            {'extracted_nik': '9101010101010101', 'extracted_nama': 'Ani Lestari',
             'ai_verification_notes': '', '_save': 'Simpan'})
        self.client.post(
            '/admin/ai_ocr/tinjauanocr/',
            {'action': 'tandai_review_manual', '_selected_action': [self.berkas.pk]})
        self.berkas.refresh_from_db()
        self.assertEqual(self.berkas.status, status_awal)


class BackfillMigrasiTests(TestCase):
    """Berkas lama harus tetap muncul di panel tanpa perlu diunggah ulang."""

    def test_fungsi_backfill_mengisi_skor_berkas_ktp_lama(self):
        from django.apps import apps as global_apps

        migrasi = import_module('core.migrations.0015_dokumen_ai_prescreen')
        warga = Penduduk.objects.create(
            nama='Budi Santoso', nik='9202020202020202', daerah_asal='Sentani',
            kota_tujuan='Bandung', tujuan='pendidikan')
        doc = Dokumen.objects.create(
            penduduk=warga, nama='ktp-lama.png', jenis='ktp',
            file='dokumen/2026/10/ktp-lama.png',
            ocr_text='NIK 9202020202020202 Nama BUDI SANTOSO',
            ocr_confidence=97.0, extracted_nik='9202020202020202',
            extracted_data={'nik': '9202020202020202', 'nama': 'BUDI SANTOSO'})
        self.assertIsNone(doc.ai_score)

        migrasi.isi_prapemilahan(global_apps, None)

        doc.refresh_from_db()
        self.assertEqual(doc.ai_prescreen, 'valid')
        self.assertGreater(doc.ai_score, AMBAT_VALID)
        self.assertTrue(doc.ai_verified)

    def test_backfill_melewatkan_berkas_yang_belum_pernah_diocr(self):
        from django.apps import apps as global_apps

        migrasi = import_module('core.migrations.0015_dokumen_ai_prescreen')
        warga = Penduduk.objects.create(
            nama='Citra Dewi', nik='9303030303030303', daerah_asal='Wamena',
            kota_tujuan='Medan', tujuan='usaha')
        doc = Dokumen.objects.create(
            penduduk=warga, nama='belum.png', jenis='ktp',
            file='dokumen/2026/10/belum.png')

        migrasi.isi_prapemilahan(global_apps, None)

        doc.refresh_from_db()
        self.assertIsNone(doc.ai_score)
        self.assertEqual(doc.ai_prescreen, 'belum_dinilai')


class TabelMetrikTests(TestCase):
    """Angka prapemilahan ikut muncul di pusat kendali."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='boss3@example.com', email='boss3@example.com', password='password123')
        warga = Penduduk.objects.create(
            nama='Doni Pras', nik='9404040404040404', daerah_asal='Jayapura',
            kota_tujuan='Semarang', tujuan='pekerjaan')
        Dokumen.objects.create(penduduk=warga, nama='a.png', jenis='ktp',
                               file='dokumen/2026/10/a.png', ai_prescreen='review')
        Dokumen.objects.create(penduduk=warga, nama='b.png', jenis='ktp',
                               file='dokumen/2026/10/b.png', ai_prescreen='valid')

    def test_dashboard_menyebut_dua_angka_prapemilahan(self):
        self.client.force_login(self.superuser)
        isi = self.client.get('/admin/').content.decode()
        self.assertIn('Prapemilahan AI', isi)
        self.assertIn('1 berkas lolos ambang 85%', isi)

    def test_live_stats_membawa_angka_ai(self):
        from core.admin_site import SipperAdminSite

        data = SipperAdminSite.dashboard_data(self.superuser)
        self.assertEqual(data['ai_review'], 1)
        self.assertEqual(data['ai_valid'], 1)
        self.assertEqual(data['ai_ambang'], AMBAT_VALID)
