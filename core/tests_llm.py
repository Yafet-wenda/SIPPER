"""Test router dua mesin di /api/chat/: LLM Gemini sebagai utama, chatbot
rule-based sebagai cadangan. Semua jalur jaringan di-mock — suite ini tidak
boleh menyentuh internet dan tidak boleh butuh kunci asli."""
import json
from unittest import mock
from urllib.error import URLError
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
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

        def read(self):
            return self._data

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
            data = json.loads(self.post_chat(riwayat=[{'peran': 'user', 'isi': 'Halo'},
                                                      {'peran': 'model', 'isi': 'Hai juga'}]).content)
        self.assertEqual(data['versi'], 'gemini')
        giliran = tangkapan['muatan']['contents']
        self.assertEqual([item['role'] for item in giliran], ['user', 'model', 'user'])
        self.assertEqual(giliran[0]['parts'][0]['text'], 'Halo')
        sistem = tangkapan['muatan']['systemInstruction']['parts'][0]['text']
        self.assertIn('DATA PENGAJUAN', sistem)
        self.assertIn(str(self.pengajuan.pk), sistem)

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
