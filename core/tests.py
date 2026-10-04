import shutil
import tempfile
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from io import BytesIO
from PIL import Image
from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan, UserRole

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
        self.assertTrue(self.client.get(f'/kartu/{KartuDigital.objects.first().kode}/').status_code, 200)

    def test_staff_can_search_and_review_application_detail(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen Detail', nik='9202020202020202', daerah_asal='Jayapura', kota_tujuan='Malang', tujuan='pendidikan')
        application = Pengajuan.objects.create(penduduk=person)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get('/petugas/?q=Citizen%20Detail'), 'Citizen Detail')
        response = self.client.post(f'/petugas/pengajuan/{application.pk}/', {'status': 'perlu_perbaikan', 'catatan': 'Mohon unggah dokumen yang lebih jelas.'})
        self.assertRedirects(response, f'/petugas/pengajuan/{application.pk}/')
        application.refresh_from_db()
        self.assertEqual(application.catatan, 'Mohon unggah dokumen yang lebih jelas.')

    def post_document(self, uploaded):
        data = {'name': 'Citizen', 'nik': '9101010101010101', 'origin': 'Jayapura',
                'destination': 'Surabaya', 'purpose': 'pekerjaan', 'document': uploaded}
        return self.client.post('/pengajuan/', data)

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
        response = self.client.post('/login/', data=b'x' * (9 * 1024 * 1024), content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 413)

    def test_citizen_can_update_destination(self):
        person = Penduduk.objects.create(user=self.user, nama='Citizen', nik='9303030303030303', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.client.force_login(self.user)
        response = self.client.post('/pemutakhiran/', {'origin': 'Jayapura', 'destination': 'Bandung', 'purpose': 'pendidikan'})
        self.assertRedirects(response, '/dashboard/')
        person.refresh_from_db()
        self.assertEqual(person.kota_tujuan, 'Bandung')

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

    def test_resubmit_accepts_new_document_and_history_is_visible(self):
        person = Penduduk.objects.create(user=self.user, nama='History Citizen', nik='9707070707070707', daerah_asal='Jayapura', kota_tujuan='Surabaya', tujuan='pekerjaan')
        application = Pengajuan.objects.create(penduduk=person, status='ditolak')
        self.client.force_login(self.user)
        response = self.client.post(f'/pengajuan/{application.pk}/kirim-ulang/', {'document': self.png_upload('new.png')})
        self.assertRedirects(response, '/dashboard/')
        self.assertEqual(Dokumen.objects.count(), 1)
        self.assertEqual(self.client.get('/histori/').status_code, 200)

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
        self.client.post('/petugas/', {'id': application.pk, 'status': 'ditolak'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'ditolak')
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(AuditLog.objects.filter(aksi='verifikasi').exists())
