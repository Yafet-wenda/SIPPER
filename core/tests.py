import csv
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock
from urllib.parse import urlparse
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from io import BytesIO
from PIL import Image
from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan, UserRole
from .middleware import HARD_LIMIT_BYTES, MaxUploadSizeMiddleware
from .uploads import MAX_UPLOAD_BYTES, SEMUA_LAMPILAN

# Tes mengunggah dokumen; arahkan MEDIA_ROOT ke folder sementara supaya
# folder media/ asli tidak ikut tertumpuk file uji.
TEST_MEDIA_ROOT = tempfile.gettempdir() + '/sipper-test-media'


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SipperFlowTests(TestCase):
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
        self.user = User.objects.create_user(username='citizen@example.com', password='password123', first_name='Citizen')
        self.staff = User.objects.create_user(username='officer@example.com', password='password123', is_staff=True)

    def png_upload(self, name='document.png'):
        output = BytesIO()
        Image.new('RGB', (1, 1), 'white').save(output, format='PNG')
        return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')

    def test_registration_requires_password_and_logs_user_in(self):
        response = self.client.post('/daftar/', {'name': 'New User', 'email': 'new@example.com', 'password': 'password123'})
        self.assertRedirects(response, '/pengajuan/')
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_application_login_accepts_account_email(self):
        response = self.client.post('/login/', {'email': 'CITIZEN@EXAMPLE.COM', 'password': 'password123'})
        self.assertRedirects(response, '/dashboard/')
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_citizen_cannot_open_officer_panel(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/petugas/').status_code, 302)

    def test_invalid_nik_does_not_create_record(self):
        self.client.force_login(self.user)
        response = self.client.post('/pengajuan/', {'name': 'Citizen', 'nik': '123', 'origin': 'Jayapura', 'destination': 'Surabaya', 'purpose': 'pekerjaan'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_staff_approval_creates_valid_card(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen', nik='9101010101010101', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person)
        self.client.force_login(self.staff)
        response = self.client.post('/petugas/', {'id': application.id, 'status': 'disetujui'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(KartuDigital.objects.count(), 1)
        self.assertTrue(KartuDigital.objects.first().is_valid())
        self.assertEqual(self.client.get(f'/kartu/{KartuDigital.objects.first().kode}/').status_code, 200)

    def test_staff_can_search_and_review_application_detail(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen Detail', nik='9202020202020202', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        application = Pengajuan.objects.create(penduduk=person)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get('/petugas/?q=Citizen%20Detail'), 'Citizen Detail')
        response = self.client.post(f'/petugas/pengajuan/{application.pk}/', {'status': 'perlu_perbaikan', 'catatan': 'Mohon unggah dokumen yang lebih jelas.'})
        self.assertRedirects(response, f'/petugas/pengajuan/{application.pk}/')
        application.refresh_from_db()
        self.assertEqual(application.catatan, 'Mohon unggah dokumen yang lebih jelas.')

    def _pending_application(self, nama='Warga Antrean', nik='9303030303030303'):
        """Pengajuan baru berstatus menunggu, siap untuk aksi cepat antrean."""
        person = Penduduk.objects.create(user=self.user, nama=nama, nik=nik,
                                         daerah_asal='Jayapura', kota_tujuan='Surabaya',
                                         tujuan='pekerjaan')
        return Pengajuan.objects.create(penduduk=person)

    def test_queue_tolak_tanpa_catatan_ditolak(self):
        """Menolak dari antrean wajib disertai catatan, bukan sunyi-sunyi."""
        application = self._pending_application()
        self.client.force_login(self.staff)
        self.client.post('/petugas/', {'id': application.pk, 'status': 'ditolak'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'menunggu')

    def test_queue_perlu_perbaikan_tanpa_catatan_ditolak(self):
        application = self._pending_application(nik='9313131313131313')
        self.client.force_login(self.staff)
        self.client.post('/petugas/', {'id': application.pk, 'status': 'perlu_perbaikan'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'menunggu')

    def test_queue_tolak_dengan_catatan_menyimpan_catatan(self):
        application = self._pending_application(nik='9323232323232323')
        self.client.force_login(self.staff)
        self.client.post('/petugas/', {'id': application.pk, 'status': 'ditolak',
                                       'catatan': 'Foto KTP buram, silakan unggah ulang.'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'ditolak')
        self.assertEqual(application.catatan, 'Foto KTP buram, silakan unggah ulang.')

    def test_queue_kembalikan_ke_menunggu(self):
        """Empat status bisa dipilih ulang dari antrean, termasuk kembali menunggu."""
        application = self._pending_application(nik='9333333333333333')
        self.client.force_login(self.staff)
        self.client.post('/petugas/', {'id': application.pk, 'status': 'disetujui'})
        self.client.post('/petugas/', {'id': application.pk, 'status': 'menunggu'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'menunggu')

    def test_detail_tolak_tanpa_catatan_ditolak(self):
        application = self._pending_application(nik='9343434343434343')
        self.client.force_login(self.staff)
        self.client.post(f'/petugas/pengajuan/{application.pk}/', {'status': 'ditolak', 'catatan': ''})
        application.refresh_from_db()
        self.assertEqual(application.status, 'menunggu')

    def post_document(self, uploaded, other=None):
        """Kirim pengajuan lengkap. `uploaded` dipakai untuk KTP, `other` untuk KK.

        Defaultnya KK yang sah supaya tes yang menguji satu berkas tidak
        gagal karena berkas satunya.
        """
        data = {'name': 'Citizen', 'nik': '9101010101010101', 'origin': 'Jayapura',
                'destination': 'Surabaya', 'purpose': 'pekerjaan',
                'ktp': uploaded, 'kk': other if other is not None else self.png_upload('kk.png')}
        return self.client.post('/pengajuan/', data)

    def test_application_requires_both_ktp_and_kk(self):
        self.client.force_login(self.user)
        response = self.client.post('/pengajuan/', {'name': 'Citizen', 'nik': '9101010101010101',
                                                    'origin': 'Jayapura', 'destination': 'Surabaya',
                                                    'purpose': 'pekerjaan', 'ktp': self.png_upload('ktp.png')})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kartu Keluarga')
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_two_full_size_lampiran_pass_the_request_size_gate(self):
        """Semua slot unggah 5 MB sekaligus tidak boleh dipotong lebih awal.

        Gerbang Content-Length dulu dihitung untuk satu slot unggah. Setelah
        form wajib mengirim KTP dan KK, kiriman sah seukuran dua berkas akan
        berbalas 413 polos sebelum Django sempat memberi pesan yang jelas.
        Sekarang pasfoto menambah slot ketiga, jadi jatah dihitung dari
        SEMUA_LAMPILAN, bukan hanya berkas yang wajib.
        """
        middleware = MaxUploadSizeMiddleware(lambda request: HttpResponse(status=200))
        request = RequestFactory().post('/pengajuan/', {'nik': '9101010101010101'})
        request.META['CONTENT_LENGTH'] = str(MAX_UPLOAD_BYTES * len(SEMUA_LAMPILAN))
        self.assertNotEqual(middleware(request).status_code, 413)

    def test_request_over_total_lampiran_budget_is_rejected_early(self):
        """Gerbangnya tetap menutup; yang berubah hanya jatah totalnya."""
        middleware = MaxUploadSizeMiddleware(lambda request: HttpResponse(status=200))
        request = RequestFactory().post('/pengajuan/', {'nik': '9101010101010101'})
        request.META['CONTENT_LENGTH'] = str(MAX_UPLOAD_BYTES * len(SEMUA_LAMPILAN) + 4 * 1024 * 1024)
        self.assertEqual(middleware(request).status_code, 413)

    def test_application_stores_ktp_and_kk_as_two_labeled_documents(self):
        self.client.force_login(self.user)
        response = self.post_document(self.png_upload('ktp.png'), self.png_upload('kk.png'))
        self.assertRedirects(response, '/dashboard/')
        documents = list(Dokumen.objects.order_by('jenis').values_list('jenis', 'nama'))
        self.assertEqual(documents, [('kk', 'kk.png'), ('ktp', 'ktp.png')])
        self.assertEqual(Dokumen.objects.get(jenis='ktp').get_jenis_display(), 'KTP')
        self.assertEqual(Dokumen.objects.get(jenis='kk').get_jenis_display(), 'Kartu Keluarga')

    def test_upload_rejects_unsupported_extension(self):
        self.client.force_login(self.user)
        response = self.post_document(SimpleUploadedFile('data.exe', b'not allowed'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_upload_rejects_oversized_file(self):
        self.client.force_login(self.user)
        oversized = SimpleUploadedFile('document.png', self.png_upload().read() + b'x' * (6 * 1024 * 1024))
        self.post_document(oversized)
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_upload_rejects_content_that_is_not_its_extension(self):
        # Nama file .pdf tapi isinya PNG (dan sebaliknya): header harus cocok.
        self.client.force_login(self.user)
        self.post_document(SimpleUploadedFile('dokumen.pdf', self.png_upload().read()))
        self.post_document(SimpleUploadedFile('dokumen.png', b'%PDF-1.4 bukan gambar'))
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_oversized_request_body_is_rejected_before_parsing(self):
        # 413 dari middleware, bukan 403 CSRF: badan permintaan tidak dibaca sama sekali.
        # Ukurannya dibaca dari konstanta yang sama supaya tes tidak salah duga
        # setiap kali jumlah slot unggah pada form pengajuan berubah.
        response = self.client.post('/login/', data=b'x' * (HARD_LIMIT_BYTES + 1024), content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 413)

    def test_citizen_can_update_destination(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen', nik='9303030303030303', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.client.force_login(self.user)
        response = self.client.post('/pemutakhiran/', {'origin': 'Jayapura', 'destination': 'Bandung', 'purpose': 'pendidikan'})
        self.assertRedirects(response, '/dashboard/')
        person.refresh_from_db()
        self.assertEqual(person.kota_tujuan, 'Bandung')

    def test_tujuan_menawarkan_pilihan_resmi(self):
        """Field tujuan menjadi choices, bukan teks bebas."""
        field = Penduduk._meta.get_field('tujuan')
        self.assertEqual([k for k, _ in field.choices],
                         ['pendidikan', 'pekerjaan', 'usaha', 'keluarga'])

    def test_pengajuan_ditolak_bila_tujuan_tidak_resmi(self):
        """Nilai purpose dari klien divalidasi di server, bukan dipercaya mentah.

        Berkas KTP+KK dibuat sah supaya satu-satunya alasan penolakan adalah
        tujuan yang tidak ada dalam daftar — bukan lampiran yang kurang.
        """
        self.client.force_login(self.user)
        response = self.client.post('/pengajuan/', {
            'name': 'Citizen', 'nik': '9101010101010101', 'origin': 'Jayapura',
            'destination': 'Surabaya', 'purpose': 'pindah-saja',
            'ktp': self.png_upload('ktp.png'), 'kk': self.png_upload('kk.png')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_pemutakhiran_ditolak_bila_tujuan_tidak_resmi(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen', nik='9303030303030304', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.client.force_login(self.user)
        response = self.client.post('/pemutakhiran/', {'origin': 'Jayapura', 'destination': 'Bandung', 'purpose': 'acak-adul'})
        self.assertEqual(response.status_code, 200)
        person.refresh_from_db()
        self.assertEqual(person.kota_tujuan, 'Surabaya')
        self.assertEqual(person.tujuan, 'pekerjaan')

    def test_pemutakhiran_menerima_tujuan_resmi(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen', nik='9303030303030305', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.client.force_login(self.user)
        response = self.client.post('/pemutakhiran/', {'origin': 'Jayapura', 'destination': 'Bandung', 'purpose': 'keluarga'})
        self.assertRedirects(response, '/dashboard/')
        person.refresh_from_db()
        self.assertEqual(person.tujuan, 'keluarga')

    def test_statistics_are_staff_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/petugas/statistik/').status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/petugas/statistik/').status_code, 200)

    def test_explicit_officer_role_can_access_staff_panel(self):
        UserRole.objects.create(user=self.user, role='petugas')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/petugas/').status_code, 200)

    def test_card_can_be_downloaded_as_pdf(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen', nik='9404040404040404', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        card = KartuDigital.objects.create(penduduk=person, kode='SPR-PDF-0001', berlaku_sampai='2027-01-01')
        self.client.force_login(self.user)
        response = self.client.get(f'/kartu/{card.kode}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_officer_can_export_filtered_report(self):
        person = Penduduk.objects.create(user=self.user, nama='CSV Citizen', nik='9505050505050505', daerah_asal='Jayapura', kota_tujuan='Jakarta', tujuan='usaha')
        Pengajuan.objects.create(penduduk=person, status='ditolak')
        self.client.force_login(self.staff)
        response = self.client.get('/petugas/?status=ditolak&export=csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(b'CSV Citizen', response.content)

    def test_citizen_can_resubmit_rejected_application(self):
        person = Penduduk.objects.create(user=self.user, nama='Retry Citizen', nik='9606060606060606', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person, status='perlu_perbaikan', catatan='Perbaiki dokumen.')
        self.client.force_login(self.user)
        response = self.client.post(f'/pengajuan/{application.pk}/kirim-ulang/')
        self.assertRedirects(response, '/dashboard/')
        application.refresh_from_db()
        self.assertEqual(application.status, 'menunggu')

    def test_profile_and_password_reset_pages_are_available(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/profil/').status_code, 200)
        self.assertEqual(self.client.get('/lupa-password/').status_code, 200)

    def test_password_reset_email_carries_a_working_link(self):
        # Regresi nyata: view auth Django me-reverse 'password_reset_done' dan
        # template email bawaan me-reverse 'password_reset_confirm' tanpa namespace,
        # sementara semua nama URL di proyek ini ada di namespace 'core'.
        self.user.email = 'reset@example.com'
        self.user.save(update_fields=['email'])
        response = self.client.post('/lupa-password/', {'email': self.user.email})
        self.assertRedirects(response, '/lupa-password/terkirim/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['reset@example.com'])
        tautan = re.search(r'https?://[^\s]+/reset-password/[^/]+/[^/]+/', mail.outbox[0].body)
        self.assertIsNotNone(tautan, mail.outbox[0].body)
        dibuka = self.client.get(urlparse(tautan.group(0)).path, follow=True)
        self.assertEqual(dibuka.status_code, 200)
        self.assertContains(dibuka, 'name="new_password1"')
        ditolak = self.client.get(urlparse(tautan.group(0)).path.replace('reset-password/', 'reset-password/x/'))
        self.assertEqual(ditolak.status_code, 404)

    def test_resubmit_accepts_new_document_and_history_is_visible(self):
        person = Penduduk.objects.create(user=self.user, nama='History Citizen', nik='9707070707070707', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person, status='ditolak')
        self.client.force_login(self.user)
        response = self.client.post(f'/pengajuan/{application.pk}/kirim-ulang/', {'ktp': self.png_upload('new.png')})
        self.assertRedirects(response, '/dashboard/')
        self.assertEqual(Dokumen.objects.count(), 1)
        self.assertEqual(self.client.get('/histori/').status_code, 200)

    def make_review_case(self, status='perlu_perbaikan'):
        person = Penduduk.objects.create(user=self.user, nama='Review Citizen', nik='9808080808080807',
                                         daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        application = Pengajuan.objects.create(penduduk=person, status=status)
        ktp = Dokumen.objects.create(penduduk=person, nama='ktp.png', jenis='ktp',
                                     file=self.png_upload('ktp.png'), ukuran=5)
        return person, application, ktp

    def test_officer_detail_preselects_the_current_status(self):
        """Regresi: dropdown tanpa `selected` membuat status tereset ke 'menunggu'.

        Petugas yang hanya mengedit catatan lalu menekan Simpan mengirim option
        yang sedang tampil. Kalau yang tampil selalu 'Menunggu', keputusan yang
        sudah dibuat hilang tanpa sengaja.
        """
        _, application, _ = self.make_review_case()
        self.client.force_login(self.staff)
        page = self.client.get(f'/petugas/pengajuan/{application.pk}/')
        self.assertContains(page, '<option value="perlu_perbaikan" selected>Perlu perbaikan</option>', html=True)
        self.assertNotContains(page, '<option value="menunggu" selected>Menunggu</option>', html=True)

    def test_officer_detail_previews_document_images(self):
        _, application, ktp = self.make_review_case()
        self.client.force_login(self.staff)
        page = self.client.get(f'/petugas/pengajuan/{application.pk}/')
        self.assertContains(page, f'<img src="/dokumen/{ktp.pk}/file/"', html=False)
        self.assertContains(page, 'KTP')

    def test_officer_list_shows_which_lampiran_already_in(self):
        person, application, _ = self.make_review_case(status='menunggu')
        self.client.force_login(self.staff)
        page = self.client.get('/petugas/')
        self.assertContains(page, 'Berkas')
        self.assertContains(page, 'KK belum')

    def test_resubmit_replaces_document_of_the_same_jenis(self):
        from django.core.files.storage import default_storage

        person, application, ktp = self.make_review_case()
        nama_lama = ktp.file.name
        self.client.force_login(self.user)
        response = self.client.post(f'/pengajuan/{application.pk}/kirim-ulang/',
                                    {'ktp': self.png_upload('ktp-baru.png')})
        self.assertRedirects(response, '/dashboard/')
        self.assertEqual(person.dokumen.count(), 1)
        ktp.refresh_from_db()
        self.assertEqual(ktp.nama, 'ktp-baru.png')
        self.assertEqual(ktp.jenis, 'ktp')
        self.assertEqual(ktp.status, 'pending')
        self.assertFalse(default_storage.exists(nama_lama), 'berkas lama harus dihapus dari storage')

    def test_staff_can_review_document(self):
        person = Penduduk.objects.create(user=self.user, nama='Document Citizen', nik='9808080808080808', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        application = Pengajuan.objects.create(penduduk=person)
        document = Dokumen.objects.create(penduduk=person, nama='ktp.png', file=self.png_upload('ktp.png'), ukuran=5)
        self.client.force_login(self.staff)
        response = self.client.post(f'/petugas/dokumen/{document.pk}/', {'status': 'valid'})
        self.assertRedirects(response, f'/petugas/pengajuan/{application.pk}/')
        document.refresh_from_db()
        self.assertEqual(document.status, 'valid')

    def test_document_file_requires_ownership_or_officer(self):
        person = Penduduk.objects.create(user=self.user, nama='Private Citizen', nik='9808080808080809', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        other = User.objects.create_user(username='other@example.com', password='password123')
        other_person = Penduduk.objects.create(user=other, nama='Other Citizen', nik='9808080808080810', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        document = Dokumen.objects.create(penduduk=person, nama='ktp.png', file=self.png_upload('ktp.png'), ukuran=5)
        url = f'/dokumen/{document.pk}/file/'

        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Content-Security-Policy'], "default-src 'none'; sandbox")

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_card_qr_image_is_served_through_view(self):
        person = Penduduk.objects.create(user=self.user, nama='QR Citizen', nik='9808080808080811', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        card = KartuDigital.objects.create(penduduk=person, kode='SPR-QR-0001', berlaku_sampai='2027-01-01', qr_code=self.png_upload('SPR-QR-0001.png'))
        response = self.client.get(f'/kartu/{card.kode}/qr.png')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertIn(f'src="/kartu/{card.kode}/qr.png"', self.client.get(f'/kartu/{card.kode}/').content.decode())

    def test_media_is_never_publicly_aliased(self):
        person = Penduduk.objects.create(user=self.user, nama='Alias Citizen', nik='9808080808080899', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        document = Dokumen.objects.create(penduduk=person, nama='ktp.png', file=self.png_upload('ktp.png'), ukuran=5)
        self.client.force_login(self.staff)
        public_path = f'/media/{document.file.name}'
        self.assertEqual(self.client.get(public_path).status_code, 404)

    def test_dashboard_scope_follows_petugas_role_not_is_staff(self):
        """Petugas UserRole melihat antrean penuh; warga hanya punyanya sendiri.

        Dasbor dulu menyaring dengan is_staff. Petugas yang diangkat lewat
        perintah promote_officer tidak punya is_staff, sehingga dia membuka
        dasbor petugas berisi satu baris miliknya sendiri — dan sebaliknya,
        akun is_staff tanpa UserRole tetap dianggap petugas oleh is_officer.
        """
        warga = User.objects.create_user(username='warga2@example.com', password='password123')
        person = Penduduk.objects.create(user=warga, nama='Warga Lain', nik='9707070707070797',
                                         daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        Pengajuan.objects.create(penduduk=person)
        milik_sendiri = Penduduk.objects.create(user=self.user, nama='Milik Sendiri', nik='9606060606060696',
                                                daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pekerjaan')
        Pengajuan.objects.create(penduduk=milik_sendiri)

        self.client.force_login(self.user)
        context = self.client.get('/dashboard/').context
        self.assertEqual([item.penduduk_id for item in context['latest']], [milik_sendiri.pk])
        self.assertEqual(context['total'], 1)

        petugas = User.objects.create_user(username='petugasrole@example.com', password='password123')
        UserRole.objects.create(user=petugas, role='petugas')
        self.client.force_login(petugas)
        response = self.client.get('/dashboard/')
        self.assertTemplateUsed(response, 'dashboard.html')
        context = response.context
        self.assertEqual(context['total'], Pengajuan.objects.count())
        self.assertEqual(context['total'], 2)

    def test_invalid_date_and_protected_apis(self):
        self.client.force_login(self.user)
        response = self.client.post('/pengajuan/', {'name': 'Date Citizen', 'nik': '9909090909090909', 'origin': 'Jayapura', 'destination': 'Jakarta', 'purpose': 'pekerjaan', 'tanggal_mulai': 'invalid-date'})
        self.assertEqual(response.status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get('/api/pending-count/').status_code, 403)
        self.assertFalse(self.client.get('/api/validate-nik/?nik=9909090909090909').json().get('registered', False))

    def test_health_endpoint_reports_database(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'ok'})

    def test_landing_stats_track_the_database(self):
        first = self.client.get('/api/landing-stats/')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first['Cache-Control'], 'no-store')
        base_warga = Penduduk.objects.count()
        base_setuju = Pengajuan.objects.filter(status='disetujui').count()
        self.assertEqual(first.json(), {'warga': base_warga, 'disetujui': base_setuju})

        person = Penduduk.objects.create(user=self.user, nama='Stat Citizen', nik='9911111111111111', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        Pengajuan.objects.create(penduduk=person, status='disetujui')

        second = self.client.get('/api/landing-stats/').json()
        self.assertEqual(second, {'warga': base_warga + 1, 'disetujui': base_setuju + 1})
        self.assertContains(self.client.get('/'), f'<b id="stat-warga">{base_warga + 1}</b>', html=True)
        self.assertContains(self.client.get('/'), f'<b id="stat-disetujui">{base_setuju + 1}</b>', html=True)

    def test_expired_card_is_persisted_as_expired(self):
        person = Penduduk.objects.create(user=self.user, nama='Expired Citizen', nik='9910101010101010', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        card = KartuDigital.objects.create(penduduk=person, kode='SPR-EXPIRED-01', berlaku_sampai='2020-01-01')
        self.client.get(f'/kartu/{card.kode}/')
        card.refresh_from_db()
        self.assertEqual(card.status, 'expired')

    def test_public_endpoint_rejects_burst_from_one_ip(self):
        codes = [self.client.get('/api/validate-nik/', {'nik': '1' * 16}).status_code for _ in range(60)]
        self.assertIn(429, codes)
        first_block = codes.index(429)
        self.assertGreaterEqual(first_block, 10)
        self.assertTrue(all(code == 200 for code in codes[:first_block]))
        self.assertEqual(self.client.get('/api/validate-nik/', {'nik': '1' * 16})['Retry-After'], '300')

    def test_throttle_counts_per_forwarded_client_ip(self):
        # Apache menambah IP klien di akhir X-Forwarded-For; IP berbeda dapat jatah sendiri.
        for _ in range(30):
            self.client.get('/api/validate-nik/', {'nik': '1' * 16}, HTTP_X_FORWARDED_FOR='10.0.0.1')
        self.assertEqual(self.client.get('/api/validate-nik/', {'nik': '1' * 16}, HTTP_X_FORWARDED_FOR='10.0.0.2').status_code, 200)
        self.assertEqual(self.client.get('/api/validate-nik/', {'nik': '1' * 16}, HTTP_X_FORWARDED_FOR='palsu, 10.0.0.1').status_code, 429)

    def test_officer_status_change_emails_the_citizen(self):
        self.user.email = 'citizen@example.com'
        self.user.save(update_fields=['email'])
        person = Penduduk.objects.create(user=self.user, nama='Notified Citizen', nik='9920202020202020', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person)
        self.client.force_login(self.staff)
        self.client.post('/petugas/', {'id': application.pk, 'status': 'disetujui'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['citizen@example.com'])
        self.assertTrue(AuditLog.objects.filter(aksi='notifikasi').exists())
        self.assertTrue(KartuDigital.objects.filter(penduduk=person).exists())

    def test_broken_email_backend_does_not_break_verification(self):
        from unittest import mock
        self.user.email = 'broken-address'
        self.user.save(update_fields=['email'])
        person = Penduduk.objects.create(user=self.user, nama='Warga', nik='9940404040404040', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person)
        self.client.force_login(self.staff)
        with mock.patch('core.emails.send_mail', side_effect=ValueError('alamat email tidak valid')):
            response = self.client.post('/petugas/', {'id': application.pk, 'status': 'disetujui'})
        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, 'disetujui')
        self.assertTrue(KartuDigital.objects.filter(penduduk=person).exists())
        self.assertTrue(AuditLog.objects.filter(aksi='notifikasi-gagal').exists())

    def test_missing_citizen_email_does_not_break_verification(self):
        person = Penduduk.objects.create(user=self.user, nama='No Email', nik='9930303030303030', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person)
        self.client.force_login(self.staff)
        self.client.post('/petugas/', {'id': application.pk, 'status': 'ditolak',
                                       'catatan': 'Data tidak sesuai berkas.'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'ditolak')
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(AuditLog.objects.filter(aksi='verifikasi').exists())

    def admin_user(self):
        user = User.objects.create_user(username='super@example.com', password='password123',
                                       is_staff=True, is_superuser=True)
        self.client.force_login(user)
        return user

    def make_person(self, nama, nik, **kwargs):
        return Penduduk.objects.create(user=self.user, nama=nama, nik=nik,
                                       daerah_asal='Jayapura', kota_tujuan='Surabaya',
                                       tujuan='pekerjaan', **kwargs)

    def test_admin_dashboard_theme_loads_on_every_admin_page(self):
        self.admin_user()
        for path in ['/admin/', '/admin/core/pengajuan/', '/admin/core/pengajuan/?status__exact=menunggu']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertContains(response, '/static/css/admin.css')
        response = self.client.get('/admin/')
        self.assertContains(response, 'sipper-dashboard')
        self.assertContains(response, '/static/js/admin-dashboard.js')
        # Modul model harus tetap tampil di halaman depan admin.
        self.assertContains(response, '/admin/core/penduduk/')
        # Nama modul memakai bentuk Indonesia, bukan akhiran 's' bahasa Inggris.
        for label_inggris in ('Penduduks', 'Pengajuans', 'Dokumens', 'Kartu digitals', 'Pemutakhirans', 'User roles'):
            self.assertNotContains(response, label_inggris)
        self.assertContains(response, 'Kartu digital')

    def test_admin_live_stats_requires_staff(self):
        self.assertEqual(self.client.get('/admin/live-stats/').status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/live-stats/').status_code, 302)

    def test_admin_live_stats_counts_match_the_database(self):
        from django.utils import timezone
        person = self.make_person('Warga Satu', '9101010101010111')
        Pengajuan.objects.create(penduduk=person)
        # Penduduk kini OneToOne dengan akun, jadi warga kedua butuh user sendiri.
        warga_dua = User.objects.create_user(username='warga2@example.com', password='password123')
        other = Penduduk.objects.create(user=warga_dua, nama='Warga Dua', nik='9101010101010112',
                                        daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        disetujui = Pengajuan.objects.create(penduduk=other, status='disetujui')
        disetujui.refresh_from_db()
        disetujui.verified_at = timezone.now()
        disetujui.save(update_fields=['verified_at'])
        self.admin_user()
        data = self.client.get('/admin/live-stats/').json()

        self.assertEqual(len(data['deret_hari']), 14)
        self.assertEqual(data['deret_hari'][-1]['tanggal'], timezone.localdate().isoformat())
        self.assertEqual(data['deret_hari'][-1]['masuk'], 2)
        self.assertEqual(data['deret_hari'][-1]['selesai'], 1)
        self.assertEqual(data['status']['menunggu'], 1)
        self.assertEqual(data['status']['disetujui'], 1)
        self.assertEqual(data['total_pengajuan'], 2)
        self.assertEqual(data['hari_ini'], 2)
        self.assertEqual(len(data['antrean']), 1)
        self.assertEqual(data['antrean'][0]['nama'], 'Warga Satu')
        self.assertIsNotNone(data['rerata_jam'])
        self.assertGreaterEqual(data['rerata_jam'], 0.0)

    def test_admin_changelist_shows_status_badge(self):
        person = self.make_person('Warga Tiga', '9101010101010113')
        Pengajuan.objects.create(penduduk=person)
        self.admin_user()
        response = self.client.get('/admin/core/pengajuan/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sip-status--menunggu')
        # Kepala kolom memakai label Indonesia, bukan nama field mentah.
        self.assertContains(response, 'Dikirim pada')
        self.assertNotContains(response, 'Submitted at')

    def test_admin_bulk_approve_uses_the_decision_path(self):
        """Aksi massal 'Setujui' harus memberi efek yang sama dengan petugas.

        Dulu aksi ini hanya queryset.update(status=...), sehingga verified_at
        kosong, kartu tidak terbit, email tidak jalan, dan AuditLog tidak
        mencatat — padahal keputusan.py menjanjikan satu jalur untuk semua pintu
        (antrean petugas, detail pengajuan, dan aksi massal admin).
        """
        person = self.make_person('Warga Setuju', '9101010101010121')
        # Warga harus punya email agar jalur pemberitahuan benar-benar teruji.
        self.user.email = 'warga-setuju@example.com'
        self.user.save(update_fields=['email'])
        application = Pengajuan.objects.create(penduduk=person)
        admin = self.admin_user()
        response = self.client.post('/admin/core/pengajuan/', {
            'action': 'approve_selected',
            '_selected_action': [application.pk],
            'select_across': '0',
            'index': '0',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, 'disetujui')
        self.assertIsNotNone(application.verified_at, 'jalur lama meninggalkan verified_at kosong')
        self.assertEqual(application.verified_by, admin)
        self.assertTrue(KartuDigital.objects.filter(penduduk=person).exists(),
                        'persetujuan harus menerbitkan kartu digital')
        self.assertTrue(AuditLog.objects.filter(aksi='verifikasi').exists(),
                        'persetujuan harus tercatat di log audit')
        self.assertEqual(len(mail.outbox), 1, 'warga diberi tahu sekali')

    def test_admin_has_no_bulk_reject_action(self):
        """Penolakan massal dihapus dari admin.

        Status negatif (ditolak / perlu perbaikan) wajib disertai catatan per
        warga; aksi massal tidak bisa mengumpulkan catatan itu, jadi jalur ini
        membuka celah keputusan tanpa alasan. Penolakan cukup lewat /petugas/.
        """
        person = self.make_person('Warga Tolak', '9101010101010122')
        Pengajuan.objects.create(penduduk=person)
        self.admin_user()
        response = self.client.get('/admin/core/pengajuan/')
        self.assertNotContains(response, 'Tolak pengajuan terpilih')
        self.assertNotContains(response, 'reject_selected')
        # Persetujuan massal tetap ada karena tidak butuh catatan.
        self.assertContains(response, 'Setujui pengajuan terpilih')

    def test_admin_time_filters_work_without_database_zoneinfo(self):
        """Filter waktu tidak boleh memakai lookup tanggal.

        MariaDB XAMPP di mesin ini tidak punya tabel zoneinfo, jadi CONVERT_TZ
        (dipakai lookup __date/__year) mengembalikan NULL dan halaman changelist
        rusak. Rentang datetime adalah jalur yang aman di semua engine.
        """
        person = self.make_person('Warga Empat', '9101010101010114')
        Pengajuan.objects.create(penduduk=person)
        self.admin_user()
        for path in [
            '/admin/core/pengajuan/?masuk=hari-ini',
            '/admin/core/pengajuan/?masuk=7-hari',
            '/admin/core/pengajuan/?masuk=90-hari',
            '/admin/core/pengajuan/?masuk=tidak-valid',
            '/admin/core/penduduk/?daftar=30-hari',
            '/admin/core/dokumen/?unggah=7-hari',
            '/admin/core/auditlog/?waktu=7-hari',
            '/admin/core/pengajuan/?q=Warga',
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
        hari_ini = self.client.get('/admin/core/pengajuan/?masuk=hari-ini')
        self.assertContains(hari_ini, 'Warga Empat')
        # Nilai tak dikenal diperlakukan sebagai "Semua", bukan error.
        nilai_asing = self.client.get('/admin/core/pengajuan/?masuk=900-hari')
        self.assertEqual(nilai_asing.status_code, 200)
        self.assertContains(nilai_asing, 'Warga Empat')

    def test_csv_export_neutralises_formula_like_cells(self):
        """Nama warga tidak boleh berubah jadi rumus saat CSV dibuka di Excel."""
        person = Penduduk.objects.create(user=self.user, nama='=HYPERLINK("http://situs", "buka")',
                                         nik='9707070707070707', daerah_asal='+62', kota_tujuan='Surabaya',
                                         tujuan='pekerjaan')
        Pengajuan.objects.create(penduduk=person, status='ditolak')
        self.client.force_login(self.staff)
        rows = list(csv.reader(io.StringIO(self.client.get('/petugas/?status=ditolak&export=csv').content.decode())))
        data = [row for row in rows if row and row[0] != 'Nama'][0]
        self.assertTrue(data[0].startswith("'"), 'sel yang diawali tanda rumus harus dinetralisasi')
        self.assertIn('HYPERLINK', data[0])
        self.assertTrue(data[2].startswith("'"), 'angka bertanda plus juga sumber rumus')
        self.assertEqual(data[3], 'Surabaya', 'nilai biasa tidak boleh ikut diberi apostrof')
        self.assertEqual(data[1], '9707070707070707', 'NIK harus tetap terbaca apa adanya')

    def test_login_lockout_follows_the_real_client_ip(self):
        """Penyerang di IP lain tidak boleh menghabiskan jatah 5 percobaan korban.

        Di topologi Apache -> Waitress, REMOTE_ADDR selalu 127.0.0.1, jadi kunci
        yang memakai REMOTE_ADDR menyatukan seluruh pengunjung dalam satu pencacah.
        """
        for _ in range(5):
            self.client.post('/login/', {'email': 'citizen@example.com', 'password': 'salah'},
                             HTTP_X_FORWARDED_FOR='203.0.113.7')
        response = self.client.post('/login/', {'email': 'citizen@example.com', 'password': 'password123'},
                                    HTTP_X_FORWARDED_FOR='198.51.100.9')
        self.assertRedirects(response, '/dashboard/', msg_prefix='login dari IP lain harus tetap boleh')

    def test_production_refuses_the_repo_default_secret_key(self):
        """Tanpa DJANGO_SECRET_KEY, proses non-debug harus menolak start.

        Kunci bawaan ada di repo, jadi memakainya di produksi berarti siapa pun
        yang bisa membaca repo dapat memalsukan cookie sesi dan token CSRF.
        """
        env = dict(os.environ, DJANGO_DEBUG='0', DB_ENGINE='sqlite', DJANGO_SECRET_KEY='')
        result = subprocess.run([sys.executable, 'manage.py', 'check'],
                                cwd=Path(__file__).resolve().parent.parent, env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, 'settings harus menolak kunci bawaan saat DEBUG=0')
        self.assertIn('DJANGO_SECRET_KEY', result.stderr + result.stdout)

    def test_ui_tidak_mencantumkan_data_pribadi_penyusun(self):
        """Contoh isi formulir tidak boleh memakai nama atau email asli.

        Halaman ini dilihat seluruh warga, jadi data pribadi penyusun yang
        tertinggal di antarmuka berarti PII tersebar tanpa keperluan.
        """
        terlarang = ['wendayafet', 'gamil.com', 'Yafet']
        root = Path(__file__).resolve().parent.parent / 'templates'
        temuan = []
        for berkas in sorted(root.rglob('*.html')):
            isi = berkas.read_text(encoding='utf-8')
            for kata in terlarang:
                if kata in isi:
                    temuan.append(f'{berkas.name}: {kata}')
        self.assertEqual(temuan, [], 'template masih memuat data pribadi penyusun')

    def test_form_autentikasi_memakai_attribut_autocomplete(self):
        """Manajer kata sandi hanya mengisi form dengan benar kalau atributnya ada."""
        halaman = [
            ('/login/', ['name="email"', 'autocomplete="username"', 'autocomplete="current-password"']),
            ('/daftar/', ['autocomplete="name"', 'autocomplete="email"', 'autocomplete="new-password"']),
            ('/lupa-password/', ['autocomplete="email"']),
        ]
        for url, wajib in halaman:
            isi = self.client.get(url).content.decode()
            for atribut in wajib:
                self.assertIn(atribut, isi, f'{url} belum memiliki {atribut}')

        self.client.force_login(self.user)
        isi = self.client.get('/password/').content.decode()
        self.assertIn('autocomplete="current-password"', isi, 'kolom sandi lama harus current-password')
        self.assertEqual(isi.count('autocomplete="new-password"'), 2,
                         'kedua kolom sandi baru harus new-password')

    def test_halaman_statistik_memakai_label_resmi_tanpa_sisa_kurung(self):
        """Grafik statistik memakai label pilihan, bukan kunci mentah.

        Kunci 'perlu_perbaikan' yang dilewatkan ke filter title menghasilkan
        'Perlu_Perbaikan' di layar, dan satu kurung kurawal lepas di template
        ikut tercetak di bawah setiap batang grafik.
        """
        orang = Penduduk.objects.create(user=self.user, nama='Citizen Statistik', nik='9505050505050505',
                                        daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        Pengajuan.objects.create(penduduk=orang, status='perlu_perbaikan')
        self.client.force_login(self.staff)
        isi = self.client.get('/petugas/statistik/').content.decode()
        self.assertIn('Perlu perbaikan', isi)
        self.assertNotIn('Perlu_Perbaikan', isi)
        self.assertNotIn('div>}', isi, 'kurung kurawal lepas ikut dirender sebagai teks')


class AdminExportCSVTests(TestCase):
    """Ekspor CSV dari changelist admin memakai jalur filter yang sama."""

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username='boss@example.com', email='boss@example.com', password='password123')
        self.citizen = User.objects.create_user(
            username='warga@example.com', password='password123')
        self.warga = Penduduk.objects.create(
            user=self.citizen, nama='Ani Lestari', nik='9101010101010101',
            daerah_asal='Jayapura', kota_tujuan='Jakarta', tujuan='pekerjaan')

    def rows(self, response):
        return list(csv.reader(io.StringIO(response.content.decode())))

    def test_superuser_can_export_pengajuan_as_csv(self):
        Pengajuan.objects.create(penduduk=self.warga, status='disetujui')
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/core/pengajuan/export.csv/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        isi = self.rows(response)
        self.assertEqual(isi[0], ['Warga', 'NIK', 'Status', 'Dikirim (WIB)', 'Catatan'])
        self.assertTrue(any('Ani Lestari' in baris for baris in isi[1:]))

    def test_export_times_are_wib_not_utc(self):
        from datetime import datetime, timezone as tz
        pengajuan = Pengajuan.objects.create(penduduk=self.warga, status='disetujui')
        pengajuan.submitted_at = datetime(2026, 10, 24, 10, 30, tzinfo=tz.utc)
        pengajuan.save(update_fields=['submitted_at'])
        self.client.force_login(self.superuser)
        isi = self.rows(self.client.get('/admin/core/pengajuan/export.csv/'))
        baris = [b for b in isi[1:] if 'Ani Lestari' in b[0]][0]
        self.assertEqual(baris[isi[0].index('Dikirim (WIB)')], '2026-10-24 17:30:00 WIB')

    def test_petugas_report_time_is_wib(self):
        from datetime import datetime, timezone as tz
        pengajuan = Pengajuan.objects.create(penduduk=self.warga, status='disetujui')
        pengajuan.submitted_at = datetime(2026, 10, 24, 10, 30, tzinfo=tz.utc)
        pengajuan.save(update_fields=['submitted_at'])
        self.client.force_login(self.superuser)
        isi = self.rows(self.client.get('/petugas/?export=csv'))
        self.assertEqual(isi[0][-1], 'Dikirim (WIB)')
        self.assertTrue(any('2026-10-24 17:30:00 WIB' in baris for baris in isi[1:]),
                        'laporan petugas harus memakai jam WIB')

    def test_export_respects_changelist_status_filter(self):
        Pengajuan.objects.create(penduduk=self.warga, status='disetujui')
        kedua = Penduduk.objects.create(
            user=User.objects.create_user(username='b@example.com', password='password123'),
            nama='Budi', nik='9202020202020202', daerah_asal='Jayapura',
            kota_tujuan='Bandung', tujuan='pendidikan')
        Pengajuan.objects.create(penduduk=kedua, status='ditolak', catatan='dokumen kurang')
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/core/pengajuan/export.csv/?status=ditolak')
        isi = self.rows(response)
        baris_data = isi[1:]
        self.assertEqual(len(baris_data), 1, 'hanya pengajuan ditolak yang boleh terekspor')
        self.assertIn('Budi', baris_data[0][0])

    def test_export_neutralizes_formula_injection(self):
        jahat = Penduduk.objects.create(
            user=User.objects.create_user(username='c@example.com', password='password123'),
            nama='=SUM(A1)', nik='9303030303030303', daerah_asal='Jayapura',
            kota_tujuan='Surabaya', tujuan='usaha')
        Pengajuan.objects.create(penduduk=jahat, status='menunggu')
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/core/pengajuan/export.csv/')
        isi = self.rows(response)
        target = [b for b in isi[1:] if 'SUM' in ''.join(b)][0]
        self.assertTrue(target[0].startswith("'="),
                        'sel diawali = harus dinetralkan dengan apostrof')

    def test_non_staff_cannot_download_export(self):
        self.client.force_login(self.citizen)
        response = self.client.get('/admin/core/pengajuan/export.csv/')
        self.assertNotEqual(response.status_code, 200,
                            'warga biasa tidak boleh mengunduh ekspor admin')

    def test_unmatched_filter_yields_empty_csv_not_error(self):
        Pengajuan.objects.create(penduduk=self.warga, status='menunggu')
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/core/pengajuan/export.csv/?status=tidak-ada')
        self.assertEqual(response.status_code, 200)
        isi = self.rows(response)
        self.assertEqual(len(isi), 1, 'filter tak cocok harus menghasilkan CSV tanpa baris data')
        self.assertEqual(isi[0], ['Warga', 'NIK', 'Status', 'Dikirim (WIB)', 'Catatan'])


class AdminDokumenFormTests(TestCase):
    """Form admin Dokumen hanya menampilkan field yang perlu diisi manusia.

    Field hasil OCR/AI adalah keluaran mesin (core/ocr_processor.py), jadi tidak
    boleh diketik tangan: disembunyikan dari form tambah dan read-only di form
    ubah. Ukuran berkas ikut dihitung otomatis saat admin menyimpan.
    """

    LABEL_MESIN = (
        'Teks hasil OCR', 'Confidence OCR', 'NIK dari OCR',
        'Data terstruktur dari OCR', 'Diverifikasi AI',
        'Catatan verifikasi AI', 'Diproses OCR pada',
    )

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username='boss2@example.com', email='boss2@example.com', password='password123')
        warga_user = User.objects.create_user(
            username='warga2@example.com', password='password123')
        self.warga = Penduduk.objects.create(
            user=warga_user, nama='Budi Santoso', nik='9202020202020202',
            daerah_asal='Sentani', kota_tujuan='Surabaya', tujuan='pekerjaan')

    def test_add_form_hides_machine_fields(self):
        self.client.force_login(self.superuser)
        isi = self.client.get('/admin/core/dokumen/add/').content.decode()
        self.assertIn('Jenis dokumen', isi, 'field identitas tetap tersedia')
        for label in self.LABEL_MESIN:
            self.assertNotIn(label, isi, f'{label} tidak boleh muncul di form tambah')

    def test_change_form_shows_machine_fields_readonly(self):
        doc = Dokumen.objects.create(
            penduduk=self.warga, nama='ktp-lama.png', jenis='ktp', status='valid',
            file='dokumen/2026/01/ktp-lama.png', ocr_text='HASIL MESIN',
            ocr_confidence=88.0, extracted_nik='9202020202020202')
        self.client.force_login(self.superuser)
        isi = self.client.get(f'/admin/core/dokumen/{doc.pk}/change/').content.decode()
        self.assertIn('Teks hasil OCR', isi, 'field mesin tampil (hanya-baca) saat mengedit')
        self.assertNotIn('name="ocr_text"', isi, 'field mesin tidak boleh berupa input')
        self.assertNotIn('name="extracted_data"', isi)

    def test_admin_save_fills_ukuran_from_file(self):
        self.client.force_login(self.superuser)
        isi_file = b'\x89PNG\r\n\x1a\n' + b'x' * 1234
        response = self.client.post('/admin/core/dokumen/add/', {
            'penduduk': self.warga.pk, 'nama': 'scan.png', 'jenis': 'ktp',
            'status': 'pending', 'file': SimpleUploadedFile('scan.png', isi_file,
                                                             content_type='image/png'),
        })
        self.assertEqual(response.status_code, 302, 'form harus menerima data')
        doc = Dokumen.objects.get(nama='scan.png')
        self.assertEqual(doc.ukuran, len(isi_file), 'ukuran dihitung dari berkas unggahan')
        doc.file.delete(save=False)

    def test_add_form_shows_manual_path_description(self):
        """Form tambah menjelaskan bahwa ini jalur manual, bukan satu-satunya sumber berkas."""
        self.client.force_login(self.superuser)
        isi = self.client.get('/admin/core/dokumen/add/').content.decode()
        self.assertIn('Jalur manual', isi, 'form tambah harus memberi konteks jalur manual')

    def test_admin_save_derives_nama_from_file_when_blank(self):
        """Nama berkas diturunkan otomatis dari nama file bila dibiarkan kosong."""
        self.client.force_login(self.superuser)
        isi_file = b'\x89PNG\r\n\x1a\n' + b'x' * 600
        response = self.client.post('/admin/core/dokumen/add/', {
            'penduduk': self.warga.pk, 'nama': '', 'jenis': 'ktp',
            'status': 'pending',
            'file': SimpleUploadedFile('ktp-budi.png', isi_file, content_type='image/png'),
        })
        self.assertEqual(response.status_code, 302, 'nama kosong harus tetap diterima')
        doc = Dokumen.objects.get(penduduk=self.warga)
        self.assertEqual(doc.nama, 'ktp-budi.png', 'nama diturunkan dari nama berkas')
        doc.file.delete(save=False)

    def test_admin_save_triggers_ocr_for_new_ktp(self):
        """Simpan KTP baru dari admin memicu OCR, sama seperti jalur warga."""
        self.client.force_login(self.superuser)
        isi_file = b'\x89PNG\r\n\x1a\n' + b'x' * 600
        with mock.patch('core.admin_site.picu_async') as ocr:
            response = self.client.post('/admin/core/dokumen/add/', {
                'penduduk': self.warga.pk, 'nama': 'ktp-ocr.png', 'jenis': 'ktp',
                'status': 'pending',
                'file': SimpleUploadedFile('ktp-ocr.png', isi_file, content_type='image/png'),
            })
        self.assertEqual(response.status_code, 302)
        doc = Dokumen.objects.get(nama='ktp-ocr.png')
        ocr.assert_called_once_with(doc.pk)
        doc.file.delete(save=False)

    def test_admin_edit_does_not_trigger_ocr(self):
        """Mengubah dokumen yang sudah ada tidak memicu ulang OCR."""
        doc = Dokumen.objects.create(
            penduduk=self.warga, nama='ktp-sudah.png', jenis='ktp', status='pending',
            file='dokumen/2026/01/ktp-sudah.png')
        self.client.force_login(self.superuser)
        isi_file = b'\x89PNG\r\n\x1a\n' + b'x' * 300
        with mock.patch('core.admin_site.picu_async') as ocr:
            response = self.client.post(f'/admin/core/dokumen/{doc.pk}/change/', {
                'penduduk': self.warga.pk, 'nama': 'ktp-diedit.png', 'jenis': 'ktp',
                'status': 'valid', '_save': 'Simpan',
                'file': SimpleUploadedFile('ktp-diedit.png', isi_file, content_type='image/png'),
            })
        self.assertEqual(response.status_code, 302)
        doc.refresh_from_db()
        self.assertEqual(doc.nama, 'ktp-diedit.png')
        ocr.assert_not_called()
        doc.file.delete(save=False)


class PengajuanAdminKeputusanTests(TestCase):
    """Halaman 'Ubah pengajuan' admin harus memberi efek yang sama dengan /petugas/.

    Mengubah status di sini wajib mengisi Diverifikasi oleh/pada, menulis Log
    Audit, dan menerbitkan kartu saat disetujui (semua lewat terapkan_status).
    Mengoreksi catatan tanpa ganti status tidak boleh memicu efek-efek itu.
    """

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username='boss3@example.com', email='boss3@example.com', password='password123')
        warga_user = User.objects.create_user(
            username='warga3@example.com', email='warga3@example.com', password='password123')
        self.warga = Penduduk.objects.create(
            user=warga_user, nama='Budi Santoso', nik='9202020202020303',
            daerah_asal='Sentani', kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.pengajuan = Pengajuan.objects.create(
            penduduk=self.warga, status='menunggu')

    def _post(self, status, catatan=''):
        return self.client.post(
            f'/admin/core/pengajuan/{self.pengajuan.pk}/change/',
            {'penduduk': self.warga.pk, 'status': status, 'catatan': catatan, '_save': 'Simpan'})

    def test_field_verifikasi_hanya_baca(self):
        self.client.force_login(self.superuser)
        isi = self.client.get(f'/admin/core/pengajuan/{self.pengajuan.pk}/change/').content.decode()
        self.assertNotIn('name="verified_by"', isi, 'verified_by diisi otomatis, bukan diketik')
        self.assertNotIn('name="verified_at"', isi, 'verified_at diisi otomatis, bukan diketik')

    def test_ganti_status_mengisi_verifikasi_dan_audit(self):
        self.client.force_login(self.superuser)
        with mock.patch('core.keputusan.notify_status', return_value=(False, 'test')):
            response = self._post('ditolak', catatan='dokumen kurang jelas')
        self.assertEqual(response.status_code, 302)
        self.pengajuan.refresh_from_db()
        self.assertEqual(self.pengajuan.status, 'ditolak')
        self.assertEqual(self.pengajuan.verified_by, self.superuser)
        self.assertIsNotNone(self.pengajuan.verified_at)
        self.assertTrue(
            AuditLog.objects.filter(aksi='verifikasi', deskripsi__contains='lewat admin').exists(),
            'keputusan admin harus tercatat di Log Audit')

    def test_disetujui_menerbitkan_kartu(self):
        self.client.force_login(self.superuser)
        with mock.patch('core.keputusan.notify_status', return_value=(False, 'test')):
            response = self._post('disetujui', catatan='lengkap')
        self.assertEqual(response.status_code, 302)
        self.pengajuan.refresh_from_db()
        self.assertEqual(self.pengajuan.status, 'disetujui')
        self.assertTrue(KartuDigital.objects.filter(penduduk=self.warga).exists(),
                        'status disetujui harus menerbitkan kartu digital')

    def test_koreksi_catatan_tanpa_ganti_status_tanpa_efek(self):
        self.client.force_login(self.superuser)
        sebelum = AuditLog.objects.count()
        response = self._post('menunggu', catatan='sedang ditinjau')
        self.assertEqual(response.status_code, 302)
        self.pengajuan.refresh_from_db()
        self.assertEqual(self.pengajuan.catatan, 'sedang ditinjau')
        self.assertIsNone(self.pengajuan.verified_by, 'tanpa perubahan status, verifikasi tidak diisi')
        self.assertEqual(AuditLog.objects.count(), sebelum, 'tidak ada log verifikasi baru')


    def test_admin_edit_blank_nama_uses_existing_file(self):
        """Edit yang mengosongkan nama (tanpa berkas baru) memakai nama berkas tersimpan."""
        doc = Dokumen.objects.create(
            penduduk=self.warga, nama='kk-warga.png', jenis='kk', status='pending',
            file='dokumen/2026/01/kk-warga.png')
        self.client.force_login(self.superuser)
        response = self.client.post(f'/admin/core/dokumen/{doc.pk}/change/', {
            'penduduk': self.warga.pk, 'nama': '', 'jenis': 'kk', 'status': 'valid',
            '_save': 'Simpan',
        })
        self.assertEqual(response.status_code, 302, 'kosongkan nama harus tetap tersimpan')
        doc.refresh_from_db()
        self.assertEqual(doc.nama, 'kk-warga.png', 'nama diturunkan dari berkas yang ada')
        doc.file.delete(save=False)


class PengajuanAdminSubmitLineTests(TestCase):
    """Halaman pengajuan hanya boleh punya tombol Simpan (+ Hapus), tanpa yang lain.

    Setiap warga punya tepat satu pengajuan (relasi OneToOne), jadi 'Simpan dan
    tambahkan lagi' tidak pernah bermakna di sini. 'Simpan dan terus mengedit'
    juga dibuang karena keputusan langsung tersimpan dan memberi efek (email,
    kartu, audit) saat status berubah — tidak ada tahap 'simpan sementara'.
    Cakupan harus per-model: model lain (Penduduk) tetap memakai tombol bawaan.
    """

    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username='boss4@example.com', email='boss4@example.com', password='password123')
        warga_user = User.objects.create_user(
            username='warga4@example.com', email='warga4@example.com', password='password123')
        self.warga = Penduduk.objects.create(
            user=warga_user, nama='Citra Permata', nik='9303030303030404',
            daerah_asal='Jayapura', kota_tujuan='Jakarta', tujuan='kuliah')
        self.pengajuan = Pengajuan.objects.create(penduduk=self.warga, status='menunggu')

    def _isi(self, path):
        self.client.force_login(self.superuser)
        return self.client.get(path).content.decode()

    def test_ubah_pengajuan_tanpa_tombol_tambahan(self):
        isi = self._isi(f'/admin/core/pengajuan/{self.pengajuan.pk}/change/')
        self.assertIn('name="_save"', isi, 'tombol Simpan tetap ada')
        self.assertNotIn('name="_addanother"', isi, 'tanpa Simpan dan tambahkan lagi')
        self.assertNotIn('name="_continue"', isi, 'tanpa Simpan dan terus mengedit')
        self.assertIn('deletelink', isi, 'tautan Hapus tetap tersedia')

    def test_tambah_pengajuan_tanpa_tombol_tambahan(self):
        isi = self._isi('/admin/core/pengajuan/add/')
        self.assertIn('name="_save"', isi)
        self.assertNotIn('name="_addanother"', isi)
        self.assertNotIn('name="_continue"', isi)

    def test_model_lain_tetap_pakai_tombol_bawaan(self):
        """Pengurangan tombol hanya untuk Pengajuan, bukan seluruh admin."""
        isi = self._isi(f'/admin/core/penduduk/{self.warga.pk}/change/')
        self.assertIn('name="_addanother"', isi, 'Penduduk tetap punya Simpan dan tambahkan lagi')
        self.assertIn('name="_continue"', isi, 'Penduduk tetap punya Simpan dan terus mengedit')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PasfotoKartuTests(TestCase):
    """Kartu digital warga ditata seperti kartu pada landing page: pasfoto di kiri,
    nama + NIK tersamar, QR di kanan, lalu blok "Batasan & operasional sistem".

    Dua aturan yang mengikat seluruh tes di kelas ini:
    1. Pasfoto bersifat opsional. Warga yang mendaftar sebelum kolomnya ada harus
       tetap bisa memakai kartunya, jadi setiap tampilan kartu butuh fallback
       inisial dan jalur unggah tidak boleh menolaknya karena kosong.
    2. Wajah warga adalah data pribadi. Halaman kartu bisa dibuka publik lewat
       tautan QR, jadi foto hanya dikirim ke pemilik kartu dan petugas.
    """

    def setUp(self):
        cache.clear()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        self.user = User.objects.create_user(username='pemilik@example.com', email='pemilik@example.com', password='password123', first_name='Yafet')
        self.staff = User.objects.create_user(username='petugasfoto@example.com', email='petugasfoto@example.com', password='password123', is_staff=True)

    def tearDown(self):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def jpg_upload(self, name='pasfoto.jpg'):
        output = BytesIO()
        Image.new('RGB', (200, 260), 'salmon').save(output, format='JPEG')
        return SimpleUploadedFile(name, output.getvalue(), content_type='image/jpeg')

    def png_upload(self, name='dokumen.png'):
        output = BytesIO()
        Image.new('RGB', (1, 1), 'white').save(output, format='PNG')
        return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')

    def _kirim_pengajuan(self, **tambahan):
        data = {'name': 'Yafet Wenda', 'nik': '9707070707070707', 'origin': 'Jayapura',
                'destination': 'Surabaya', 'purpose': 'pekerjaan',
                'ktp': self.png_upload('ktp.png'), 'kk': self.png_upload('kk.png')}
        data.update(tambahan)
        self.client.force_login(self.user)
        return self.client.post('/pengajuan/', data)

    def _warga_dengan_kartu(self, foto=None, kode='SPR-FOTO-0001'):
        """Warga punya kartu; `foto` berupa berkas unggah bila kartu perlu pasfoto."""
        person = Penduduk.objects.create(user=self.user, nama='Yafet Wenda', nik='9808080808080808',
                                         daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        if foto is not None:
            person.foto.save('pasfoto.jpg', foto, save=True)
        return KartuDigital.objects.create(penduduk=person, kode=kode, berlaku_sampai='2027-10-09')

    def test_penduduk_punya_foto_yang_boleh_kosong(self):
        field = Penduduk._meta.get_field('foto')
        self.assertTrue(field.blank, 'pasfoto tidak boleh memaksa warga yang sudah terdaftar')
        person = Penduduk.objects.create(user=self.user, nama='Tanpa Foto', nik='9909090909090909',
                                         daerah_asal='Jayapura', kota_tujuan='Manokwari', tujuan='keluarga')
        self.assertFalse(bool(person.foto))

    def test_inisial_nama_untuk_fallback_kartu(self):
        person = Penduduk(nama='Yafet Wenda')
        self.assertEqual(person.inisial, 'YW')
        self.assertEqual(Penduduk(nama='Yafet').inisial, 'Y')
        self.assertEqual(Penduduk(nama='Maria Christina Klambu').inisial, 'MC')

    def test_form_pengajuan_menawarkan_isian_pasfoto(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/pengajuan/'), 'name="pasfoto"')

    def test_pengajuan_menyimpan_pasfoto(self):
        response = self._kirim_pengajuan(pasfoto=self.jpg_upload())
        self.assertRedirects(response, '/dashboard/')
        person = Penduduk.objects.get(nik='9707070707070707')
        self.assertTrue(bool(person.foto), 'pasfoto tersimpan pada data warga')
        self.assertTrue(os.path.exists(person.foto.path))

    def test_pengajuan_tetap_sah_tanpa_pasfoto(self):
        response = self._kirim_pengajuan()
        self.assertRedirects(response, '/dashboard/')
        self.assertFalse(bool(Penduduk.objects.get(nik='9707070707070707').foto))

    def test_pasfoto_bukan_gambar_ditolak(self):
        response = self._kirim_pengajuan(pasfoto=SimpleUploadedFile('pasfoto.pdf', b'%PDF-1.4 bukan gambar', content_type='application/pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pasfoto')
        self.assertEqual(Penduduk.objects.count(), 0, 'pengajuan ditolak sebelum data warga ditulis')

    def test_pasfoto_terlalu_besar_ditolak(self):
        bongsor = SimpleUploadedFile('pasfoto.jpg', self.jpg_upload().read() + b'x' * (6 * 1024 * 1024))
        response = self._kirim_pengajuan(pasfoto=bongsor)
        self.assertContains(response, 'Pasfoto')
        self.assertEqual(Penduduk.objects.count(), 0)

    def test_kirim_ulang_mengganti_pasfoto(self):
        person = Penduduk.objects.create(user=self.user, nama='Retry Foto', nik='9111111111111111',
                                         daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        aplikasi = Pengajuan.objects.create(penduduk=person, status='perlu_perbaikan', catatan='Ganti pasfoto.')
        person.foto.save('pasfoto.jpg', self.jpg_upload(), save=True)
        path_lama = person.foto.path
        self.client.force_login(self.user)
        response = self.client.post(f'/pengajuan/{aplikasi.pk}/kirim-ulang/', {'pasfoto': self.jpg_upload('pengganti.jpg')})
        self.assertRedirects(response, '/dashboard/')
        person.refresh_from_db()
        self.assertIn('pengganti', os.path.basename(person.foto.name))
        self.assertFalse(os.path.exists(path_lama), 'pasfoto lama dibersihkan dari media/')

    def test_halaman_kartu_pemilik_menampilkan_foto(self):
        card = self._warga_dengan_kartu(foto=self.jpg_upload())
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f'/kartu/{card.kode}/'), f'/penduduk/{card.penduduk_id}/pasfoto/')

    def test_halaman_kartu_petugas_menampilkan_foto(self):
        card = self._warga_dengan_kartu(foto=self.jpg_upload())
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(f'/kartu/{card.kode}/'), f'/penduduk/{card.penduduk_id}/pasfoto/')

    def test_halaman_kartu_anonim_tidak_menampilkan_foto(self):
        """Pemindai QR yang belum login tetap melihat kartu, tanpa wajah warga."""
        card = self._warga_dengan_kartu(foto=self.jpg_upload())
        isi = self.client.get(f'/kartu/{card.kode}/').content.decode()
        self.assertNotIn('/pasfoto/', isi)
        self.assertIn('Yafet Wenda', isi, 'nama dan kartu tetap ditampilkan seperti sebelumnya')

    def test_rute_pasfoto_terkunci_pemilik_dan_petugas(self):
        card = self._warga_dengan_kartu(foto=self.jpg_upload())
        url = f'/penduduk/{card.penduduk_id}/pasfoto/'
        self.assertEqual(self.client.get(url).status_code, 302, 'anonim diarahkan ke login')
        orang_lain = User.objects.create_user(username='oranglain@example.com', email='oranglain@example.com', password='password123')
        self.client.force_login(orang_lain)
        self.assertEqual(self.client.get(url).status_code, 404, 'warga lain tidak bisa menebak id')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_rute_pasfoto_warga_tanpa_foto_404(self):
        card = self._warga_dengan_kartu()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/penduduk/{card.penduduk_id}/pasfoto/').status_code, 404)

    def test_halaman_kartu_tanpa_foto_pakai_inisial(self):
        card = self._warga_dengan_kartu()
        self.client.force_login(self.user)
        isi = self.client.get(f'/kartu/{card.kode}/').content.decode()
        self.assertNotIn('/pasfoto/', isi)
        self.assertIn('YW', isi)

    def test_halaman_kartu_memuat_blok_batasan(self):
        card = self._warga_dengan_kartu()
        isi = self.client.get(f'/kartu/{card.kode}/').content.decode()
        self.assertIn('Kartu SIPPER', isi)
        self.assertIn('Batasan & operasional sistem', isi)
        self.assertIn('bukan pengganti dokumen', isi)
        self.assertIn('Dukcapil', isi)
        self.assertIn(card.penduduk.nik[-4:], isi, 'NIK tetap tampil sebagian')
        self.assertNotIn(card.penduduk.nik, isi, 'NIK tidak boleh utuh di halaman kartu')

    def test_unduh_kartu_pdf_tanpa_foto_sukses(self):
        card = self._warga_dengan_kartu()
        self.client.force_login(self.user)
        response = self.client.get(f'/kartu/{card.kode}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_unduh_kartu_pdf_dengan_foto_sukses(self):
        card = self._warga_dengan_kartu(foto=self.jpg_upload())
        self.client.force_login(self.user)
        response = self.client.get(f'/kartu/{card.kode}/download/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_geometri_kartu_ikut_proporsi_id1(self):
        """Kartu harus seukuran KTP/BPJS, bukan blok kotak.

        ID-1 (85,60 × 53,98 mm, rasio ±1,586) adalah ukuran fisik KTP, KK digital,
        dan ATM. PDF memakainya sebagai ukuran gambar kartu supaya hasil cetak
        100% bisa langsung dipotong sebesar kartu asli.
        """
        from .kartu_pdf import KARTU_ID1_MM, KARTU_ID1_PT
        self.assertEqual(KARTU_ID1_MM, (85.6, 53.98))
        self.assertAlmostEqual(KARTU_ID1_PT[0], 242.6457, places=3, msg='lebar kartu = 85,6 mm dalam poin')
        self.assertAlmostEqual(KARTU_ID1_PT[0] / KARTU_ID1_PT[1], 85.6 / 53.98, places=4, msg='rasio wajib ID-1')

    def test_potret_pasfoto_dikemas_jpeg_terbatas(self):
        """PDF kartu tidak boleh membengkak karena satu pasfoto.

        reportlab menempel objek PIL sebagai piksel mentah (~1 MB per foto),
        jadi potret harus diperkecil lalu dikemas ulang jadi JPEG. Kotak foto di
        kartu ID-1 hanya 54x72 poin, sehingga 600 piksel sudah cukup untuk cetak.
        """
        import io
        from PIL import Image
        from .kartu_pdf import potret_pasfoto
        sumber = io.BytesIO()
        Image.new('RGB', (2000, 2000), 'white').save(sumber, format='PNG')
        sumber.seek(0)
        hasil = potret_pasfoto(sumber)
        self.assertIsNotNone(hasil)
        self.assertEqual(hasil.read(2), b'\xff\xd8', 'hasil harus berkas JPEG, bukan objek PIL')
        self.assertLess(len(hasil.getvalue()), 200_000, 'satu pasfoto tidak boleh menambah ~1 MB')
        hasil.seek(0)
        lebar, tinggi = Image.open(hasil).size
        self.assertLessEqual(max(lebar, tinggi), 800, 'resolusi potret harus dibatasi')
        self.assertAlmostEqual(lebar / tinggi, 3 / 4, places=2, msg='potret wajib berasio 3:4')

    def test_baris_teks_memotong_kata_yang_lebih_lebar_dari_kolom(self):
        """Satu kata tanpa spasi tidak boleh menembus tepi kartu PDF.

        Kolom nama di basis data menerima 150 karakter dan tidak mewajibkan
        spasi, jadi pemenggal baris harus memotong kata yang lebih lebar dari
        kolomnya, bukan menggambarnya apa adanya.
        """
        import io
        from reportlab.pdfgen import canvas
        from .kartu_pdf import baris_teks
        dokumen = canvas.Canvas(io.BytesIO())
        kolom = 104.6  # lebar kolom identitas kartu ID-1
        hasil = baris_teks('A' * 150, 'Helvetica-Bold', 12, kolom, dokumen)
        self.assertGreater(len(hasil), 1, 'kata sepanjang 150 karakter harus dipecah')
        for baris in hasil:
            self.assertLessEqual(dokumen.stringWidth(baris, 'Helvetica-Bold', 12), kolom,
                                 f'baris {baris!r} melebar dari kolom')
        self.assertEqual(''.join(hasil), 'A' * 150, 'pemotongan tidak boleh menghapus karakter')

    def test_baris_teks_tetap_menghormati_batas_baris_tanpa_memotong_kata(self):
        """Kata yang muat kolom tetap utuh; hanya barisnya yang dihitung."""
        import io
        from reportlab.pdfgen import canvas
        from .kartu_pdf import baris_teks
        dokumen = canvas.Canvas(io.BytesIO())
        hasil = baris_teks('Sistem Informasi Penduduk Perantauan', 'Helvetica', 5, 60, dokumen)
        self.assertEqual(' '.join(hasil), 'Sistem Informasi Penduduk Perantauan')

    def test_nama_bulan_pada_kartu_bergaya_indonesia(self):
        """PDF memakai formatter Django, bukan strftime yang ikut locale C."""
        from datetime import date
        from .kartu_pdf import tanggal_kartu
        self.assertEqual(tanggal_kartu(date(2027, 10, 9)), '09 Okt 2027')

    def test_gerbang_ukuran_menampung_slot_pasfoto(self):
        """Form pengajuan punya tiga slot unggah; jatah CONTENT_LENGTH ikut jumlah itu."""
        self.assertEqual(len(SEMUA_LAMPILAN), 3)
        middleware = MaxUploadSizeMiddleware(lambda request: HttpResponse(status=200))
        request = RequestFactory().post('/pengajuan/', {'nik': '9121212121212121'})
        request.META['CONTENT_LENGTH'] = str(MAX_UPLOAD_BYTES * len(SEMUA_LAMPILAN))
        self.assertNotEqual(middleware(request).status_code, 413)

    def test_gerbang_ukuran_tetap_memotong_kiriman_berlebih(self):
        middleware = MaxUploadSizeMiddleware(lambda request: HttpResponse(status=200))
        request = RequestFactory().post('/pengajuan/', {'nik': '9131313131313131'})
        request.META['CONTENT_LENGTH'] = str(MAX_UPLOAD_BYTES * len(SEMUA_LAMPILAN) + 4 * 1024 * 1024)
        self.assertEqual(middleware(request).status_code, 413)

    def test_admin_penduduk_menampilkan_pratinjau_pasfoto(self):
        boss = User.objects.create_superuser(username='bosfoto@example.com', email='bosfoto@example.com', password='password123')
        card = self._warga_dengan_kartu(foto=self.jpg_upload())
        self.client.force_login(boss)
        isi = self.client.get(f'/admin/core/penduduk/{card.penduduk_id}/change/').content.decode()
        self.assertIn(f'/penduduk/{card.penduduk_id}/pasfoto/', isi)


class PerbaruiStatusKartuTests(TestCase):
    """Penjadwal menutup kartu yang lewat tempo tanpa menunggu ada yang memindai.

    Halaman validasi sudah menyimpan status 'expired' (lihat
    test_expired_card_is_persisted_as_expired), tetapi itu hanya terjadi untuk
    kartu yang benar-benar dibuka. Baris lain tetap tercatat 'aktif' dan
    menyesatkan setiap pemeriksa yang menyaring kolom status.
    """

    def kartu(self, kode, berlaku_sampai, nik, status='aktif'):
        orang = Penduduk.objects.create(
            nama=f'Warga {kode}', nik=nik, daerah_asal='Sentani',
            kota_tujuan='Surabaya', tujuan='pekerjaan')
        return KartuDigital.objects.create(penduduk=orang, kode=kode,
                                           berlaku_sampai=berlaku_sampai, status=status)

    def status_semua(self):
        return dict(KartuDigital.objects.values_list('kode', 'status'))

    def test_kartu_lewat_tempo_ditutup_meski_tidak_pernah_dipindai(self):
        self.kartu('SPR-LAMA-1', '2020-01-01', '9101010101010101')
        self.kartu('SPR-BARU-1', '2027-01-01', '9101010101010102')
        self.kartu('SPR-MATI-1', '2020-01-01', '9101010101010103', status='nonaktif')
        keluaran = io.StringIO()

        call_command('refresh_card_status', stdout=keluaran)

        self.assertEqual(self.status_semua(),
                         {'SPR-LAMA-1': 'expired', 'SPR-BARU-1': 'aktif', 'SPR-MATI-1': 'nonaktif'},
                         'hanya kartu aktif yang sudah lewat tanggal yang berubah')
        self.assertIn('1 kartu', keluaran.getvalue())

    def test_kering_saja_tidak_menulis_apa_pun(self):
        self.kartu('SPR-KERING-1', '2019-06-06', '9101010101010111')
        keluaran = io.StringIO()

        call_command('refresh_card_status', '--dry-run', stdout=keluaran)

        self.assertEqual(self.status_semua(), {'SPR-KERING-1': 'aktif'})
        self.assertIn('dry-run', keluaran.getvalue())
        self.assertIn('SPR-KERING-1', keluaran.getvalue(), 'dry-run harus menyebutkan kartunya')

    def test_dijalankan_dua_kali_tidak_menemukan_lagi(self):
        self.kartu('SPR-DUA-KALI', '2018-02-02', '9101010101010112')
        keluaran = io.StringIO()

        call_command('refresh_card_status', stdout=keluaran)
        kedua = io.StringIO()
        call_command('refresh_card_status', stdout=kedua)

        self.assertEqual(self.status_semua(), {'SPR-DUA-KALI': 'expired'})
        self.assertIn('0 kartu', kedua.getvalue())
