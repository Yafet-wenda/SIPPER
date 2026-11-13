"""Test router dua mesin di /api/chat/: LLM Gemini sebagai utama, chatbot
rule-based sebagai cadangan. Semua jalur jaringan di-mock — suite ini tidak
boleh menyentuh internet dan tidak boleh butuh kunci asli."""
import base64
import json
import os
import tempfile
from unittest import mock
from urllib.error import URLError
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from . import llm
from .models import AuditLog, Penduduk, Pengajuan


class AsistenLlmTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(username='officer@llm.test', password='password123', is_staff=True)
        person = Penduduk.objects.create(
            user=User.objects.create_user(username='warga@llm.test', password='password123'),
            nama='LLM Citizen', nik='9111111111111111', daerah_asal='Jayapura',
            kota_tujuan='Surabaya', tujuan='pekerjaan')
        self.pengajuan = Pengajuan.objects.create(penduduk=person)

    class ResponsPalsu:
        def __init__(self, payload):
            self._data = json.dumps(payload).encode('utf-8')

        def read(self, size=-1):
            return self._data if size < 0 else self._data[:size]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    @staticmethod
    def balasan_gemini(teks='Halo dari Gemini.'):
        return {'candidates': [{'content': {'parts': [{'text': teks}]}}]}

    def post_chat(self, **muatan):
        muatan.setdefault('pesan', 'Buatkan ringkasan pengajuan ini')
        muatan.setdefault('pengajuan_id', self.pengajuan.pk)
        self.client.force_login(self.staff)
        return self.client.post('/api/chat/', data=json.dumps(muatan), content_type='application/json')

    def test_kunci_kosong_tidak_menyentuh_jaringan(self):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': ''}), \
             mock.patch.object(llm._urllib_request, 'urlopen') as fake:
            respons = self.post_chat()
        data = json.loads(respons.content)
        self.assertEqual(respons.status_code, 200)
        self.assertEqual(data['versi'], 'aturan-lokal-1')
        self.assertIn('Ringkasan pengajuan', data['jawaban'])
        fake.assert_not_called()

    def test_gemini_dipakai_saat_kunci_terisi(self):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'}), \
             mock.patch.object(llm._urllib_request, 'urlopen',
                               return_value=self.ResponsPalsu(self.balasan_gemini())) as fake:
            data = json.loads(self.post_chat().content)
        self.assertEqual(data['versi'], 'gemini')
        self.assertEqual(data['kategori'], 'llm')
        self.assertEqual(data['jawaban'], 'Halo dari Gemini.')
        self.assertTrue(data['saran'], 'saran kontekstual tetap datang dari mesin aturan')
        fake.assert_called_once()
        url = fake.call_args[0][0].full_url
        self.assertIn('generativelanguage.googleapis.com', url)
        self.assertNotIn('kunci-uji-palsu', url, 'kunci hanya lewat header, bukan URL')

    def test_konteks_gemini_hanya_memuat_metadata_allowlist(self):
        konteks = {
            'pengajuan_id': 123,
            'status_kode': 'menunggu',
            'catatan': 'CATATAN-RAHASIA',
            'penduduk': {
                'nama': 'NAMA-RAHASIA',
                'nik': '9111111111111111',
                'nomor_telepon': '081234567890',
                'kota_tujuan': 'KOTA-RAHASIA',
            },
            'dokumen': [{
                'id': 456,
                'nama': 'BERKAS-RAHASIA',
                'jenis': 'ktp',
                'status': 'valid',
                'confidence': 92.4,
                'extracted_nik': '9222222222222222',
                'extracted_data': {
                    'nama': 'OCR-NAMA-RAHASIA',
                    'alamat': 'OCR-ALAMAT-RAHASIA',
                    'nik': '9222222222222222',
                },
                'ai_score': 87.5,
                'ai_prescreen': 'valid',
                'ai_verification_notes': 'CATATAN-OCR-RAHASIA',
                'diproses': True,
            }],
            'kartu': {'kode': 'KODE-KARTU-RAHASIA', 'status': 'aktif', 'valid': True},
        }

        aman = llm.samarkan_konteks(konteks)
        serial = json.dumps(aman, ensure_ascii=False)

        for rahasia in ('NAMA-RAHASIA', '9111111111111111', '081234567890',
                        'KOTA-RAHASIA', 'OCR-NAMA-RAHASIA', 'OCR-ALAMAT-RAHASIA',
                        'CATATAN-RAHASIA', 'BERKAS-RAHASIA', 'KODE-KARTU-RAHASIA'):
            self.assertNotIn(rahasia, serial)
        self.assertEqual(aman['status_pengajuan'], 'menunggu')
        self.assertEqual(aman['dokumen'][0]['confidence'], 92.4)
        self.assertEqual(aman['dokumen'][0]['ai_score'], 87.5)
        self.assertEqual(aman['dokumen'][0]['jumlah_field_ocr'], 3)
        self.assertEqual(konteks['penduduk']['nama'], 'NAMA-RAHASIA',
                         'sanitasi tidak boleh mengubah konteks lokal')

    def test_email_dan_nomor_panjang_disamarkan_dari_teks_chat(self):
        teks = llm.samarkan_teks(
            'Hubungi warga@example.test; NIK 9111111111111111; telepon 081234567890')
        self.assertNotIn('warga@example.test', teks)
        self.assertNotIn('9111111111111111', teks)
        self.assertNotIn('081234567890', teks)
        self.assertEqual(teks.count('[nomor disamarkan]'), 2)

    def test_gemini_ocr_mengirim_berkas_dan_memvalidasi_hasil_terstruktur(self):
        hasil_api = {'text': 'NIK 9101010101010101 NAMA ANI', 'fields': {
            'nik': '9101010101010101', 'nama': 'Ani Lestari', 'alamat': 'Jl. Contoh',
            'field_tak_diizinkan': 'jangan disimpan',
        }}
        with tempfile.TemporaryDirectory() as direktori:
            path = os.path.join(direktori, 'uji.png')
            with open(path, 'wb') as file:
                file.write(b'\x89PNG\r\n\x1a\ngambar-uji')
            with override_settings(GEMINI_OCR_ENABLED=True), mock.patch.dict(
                'os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'},
            ), mock.patch.object(
                llm._urllib_request, 'urlopen',
                return_value=self.ResponsPalsu(self.balasan_gemini(json.dumps(hasil_api))),
            ) as fake:
                hasil = llm.baca_dokumen_gemini(path, 'ktp', disetujui=True)

        request = fake.call_args.args[0]
        payload = json.loads(request.data.decode('utf-8'))
        lampiran = payload['contents'][0]['parts'][1]['inline_data']
        self.assertEqual(lampiran['mime_type'], 'image/png')
        self.assertEqual(base64.b64decode(lampiran['data']), b'\x89PNG\r\n\x1a\ngambar-uji')
        self.assertEqual(request.get_header('X-goog-api-key'), 'kunci-uji-palsu')
        self.assertNotIn('kunci-uji-palsu', request.full_url)
        self.assertEqual(hasil['fields'], {
            'nik': '9101010101010101', 'nama': 'Ani Lestari', 'alamat': 'Jl. Contoh',
        })

    def test_gemini_ocr_tidak_dijalankan_kecuali_diaktifkan(self):
        with override_settings(GEMINI_OCR_ENABLED=False), mock.patch.dict(
            'os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'},
        ), mock.patch.object(llm._urllib_request, 'urlopen') as fake:
            with self.assertRaises(llm.LlmTidakTersedia):
                llm.baca_dokumen_gemini('tidak-ada.png', 'ktp', disetujui=True)
        fake.assert_not_called()

    def test_gemini_ocr_menolak_pengiriman_tanpa_persetujuan(self):
        with override_settings(GEMINI_OCR_ENABLED=True), mock.patch.dict(
            'os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'},
        ), mock.patch.object(llm, '_baca_lampiran_ocr') as baca_lampiran:
            with self.assertRaises(llm.LlmTidakTersedia):
                llm.baca_dokumen_gemini('tidak-ada.png', 'ktp')
        baca_lampiran.assert_not_called()

    def test_gemini_gagal_fallback_ke_aturan_dan_dicatat(self):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'}), \
             mock.patch.object(llm._urllib_request, 'urlopen', side_effect=URLError('tidak ada jaringan')):
            data = json.loads(self.post_chat().content)
        self.assertEqual(data['versi'], 'aturan-lokal-1')
        self.assertIn('Ringkasan pengajuan', data['jawaban'])
        log = AuditLog.objects.filter(aksi='chat_llm_gagal').first()
        self.assertIsNotNone(log, 'kegagalan LLM harus meninggalkan jejak audit')
        self.assertEqual(log.user, self.staff)

    def test_balasan_tidak_sah_dianggap_kegagalan_llm(self):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'}), \
             mock.patch.object(llm._urllib_request, 'urlopen',
                               return_value=self.ResponsPalsu({'candidates': []})):
            data = json.loads(self.post_chat().content)
        self.assertEqual(data['versi'], 'aturan-lokal-1')
        self.assertEqual(AuditLog.objects.filter(aksi='chat_llm_gagal').count(), 1)

    def test_riwayat_diteruskan_ke_gemini(self):
        tangkapan = {}

        def catat(permintaan, *args, **kwargs):
            tangkapan['muatan'] = json.loads(permintaan.data.decode('utf-8'))
            return self.ResponsPalsu(self.balasan_gemini())

        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'kunci-uji-palsu'}), \
             mock.patch.object(llm._urllib_request, 'urlopen', side_effect=catat):
            data = json.loads(self.post_chat(
                pesan='Kontak warga@example.test, NIK 9111111111111111',
                riwayat=[{'peran': 'user', 'isi': 'NIK 9222222222222222'},
                                                      {'peran': 'model', 'isi': 'Hai juga'}]).content)
        self.assertEqual(data['versi'], 'gemini')
        giliran = tangkapan['muatan']['contents']
        self.assertEqual([item['role'] for item in giliran], ['user', 'model', 'user'])
        self.assertNotIn('9222222222222222', giliran[0]['parts'][0]['text'])
        self.assertIn('[nomor disamarkan]', giliran[0]['parts'][0]['text'])
        self.assertIn('[email disamarkan]', giliran[-1]['parts'][0]['text'])
        self.assertNotIn('9111111111111111', giliran[-1]['parts'][0]['text'])
        sistem = tangkapan['muatan']['systemInstruction']['parts'][0]['text']
        self.assertIn('DATA PENGAJUAN', sistem)
        self.assertNotIn('LLM Citizen', sistem)
        self.assertNotIn('9111111111111111', sistem)

    def test_riwayat_tidak_valid_ditolak_400(self):
        contoh_contoh = [
            [{'peran': 'sistem', 'isi': 'coba suntik'}],
            [{'peran': 'user', 'isi': 'x' * 501}],
            'bukan list',
            [{'peran': 'user', 'isi': 'halo'} for _ in range(13)],
        ]
        for riwayat in contoh_contoh:
            self.client.force_login(self.staff)
            respons = self.client.post('/api/chat/', data=json.dumps({
                'pesan': 'Halo', 'pengajuan_id': self.pengajuan.pk, 'riwayat': riwayat}),
                content_type='application/json')
            self.assertEqual(respons.status_code, 400)

    def test_warga_biasa_tidak_bisa_memakai_api_chat(self):
        warga = User.objects.create_user(username='plain@llm.test', password='password123')
        self.client.force_login(warga)
        respons = self.client.post('/api/chat/', data=json.dumps({
            'pesan': 'Halo', 'pengajuan_id': self.pengajuan.pk}), content_type='application/json')
        self.assertEqual(respons.status_code, 403)

    def test_riwayat_valid_menjadi_gerbang_llm(self):
        self.assertFalse(llm.riwayat_valid([{'peran': 'user', 'isi': 'x' * 501}]))
        self.assertFalse(llm.riwayat_valid([{'peran': 'tool', 'isi': 'halo'}]))
        self.assertTrue(llm.riwayat_valid([{'peran': 'user', 'isi': 'halo'}]))
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            with self.assertRaises(llm.LlmTidakTersedia):
                llm.jawab_llm('Halo', {})
