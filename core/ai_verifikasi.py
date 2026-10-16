"""Prapemilahan AI: membandingkan hasil OCR berkas dengan isian formulir warga.

Laporan SIPPER bagian "Validasi agentik AI" menetapkan dua hal yang harus
dilakukan mesin: mencocokkan teks hasil OCR dari berkas pendukung dengan input
formulir, lalu menandai berkas dengan tingkat kecocokan di atas 85% sebagai
pre-screened "Valid" dan sisanya diberi flag "Perlu Review Manual Petugas".
Modul ini adalah terjemahan langsung kalimat itu menjadi kode.

Modul sengaja berisi fungsi murni: tanpa Tesseract, tanpa ORM, tanpa HTTP.
Dengan begitu ambang dan bobotnya bisa diuji di mesin mana pun, termasuk CI
yang tidak memasang biner Tesseract, dan perbandingan yang dilihat petugas di
layar selalu dihitung dengan rumus yang sama dengan yang dipakai saat berkas
baru masuk.
"""

import re
from difflib import SequenceMatcher

# Ambang dari laporan: "> 85% -> Valid". Nilai tepat 85 tidak dibulatkan ke
# atas. Prapemilahan boleh mengirim berkas ke antrean manual, tetapi tidak
# boleh menyebut "Valid" pada angka yang masih persis di batas.
AMBAT_VALID = 85.0

# Bobot tiap komponen, jumlah = 1,0.
# NIK penanda identitas terkuat: satu-satunya field yang harus persis sama.
# Nama mengikuti (boleh beda urutan/prefix), dan keterbacaan hasil OCR menahan
# berkas yang teksnya rusak parah supaya tidak lolos sebagai "Valid".
BOBOT = {'nik': 0.45, 'nama': 0.30, 'keterbacaan': 0.25}

# Hanya KTP yang punya padanan field di formulir warga. Berkas KK dan lainnya
# tidak dipaksa masuk skor dengan pembanding yang salah: petugas yang
# memeriksanya langsung.
JENIS_BERNILAI = ('ktp',)

# 'belum_dinilai' dipakai untuk berkas yang tidak bisa dinilai mesin (bukan KTP,
# atau berkas yang gagal dibaca) supaya tidak tertafsir sebagai "perlu review"
# maupun "valid".
# Label dibuat pendek karena ia muncul sebagai badge di kolom yang judulnya
# sudah menyebut prapemilahan; kalimat lengkap laporan ("Perlu Review Manual
# Petugas") tetap utuh di catatan verifikasi AI dan di paragraf penjelasan
# changelist.
PRESCREEN = [
    ('valid', 'Valid'),
    ('review', 'Perlu review manual'),
    ('belum_dinilai', 'Belum dinilai'),
]

_LABEL = {
    'nik': 'NIK',
    'nama': 'Nama',
    'keterbacaan': 'Keterbacaan hasil OCR',
}


def _angka(nilai):
    """Hanya digit, supaya '3515 0101...' dan '35150101...' dianggap sama."""
    return re.sub(r'\D', '', str(nilai or ''))


def _huruf(nilai):
    """Huruf kapital saja: 'Yafet  Wenda.' dan 'YAFET WENDA' jadi identik."""
    return re.sub(r'[^A-Z ]', '', str(nilai or '').upper()).strip()


def _mirip(nilai_a, nilai_b):
    """Kesamaan dua teks nama sebagai angka 0..1.

    SequenceMatcher dipakai di atas token yang sudah disortir supaya 'WENDA
    YAFET' tetap dinilai sama dengan 'YAFET WENDA' — OCR sering membalik urutan
    kata pada foto miring.
    """
    a, b = _huruf(nilai_a), _huruf(nilai_b)
    if not a or not b:
        return 0.0
    kata_a = ' '.join(sorted(a.split()))
    kata_b = ' '.join(sorted(b.split()))
    if kata_a == kata_b:
        return 1.0
    return SequenceMatcher(None, kata_a, kata_b).ratio()


def baris_perbandingan(penduduk, data_ocr, confidence):
    """Susun baris tabel "isian formulir vs hasil OCR" untuk ditampilkan.

    Tiap baris membawa nilai formulir, nilai OCR, kecocokan 0..1, dan bobotnya,
    sehingga layar review bisa menunjukkan alasan sebuah skor, bukan hanya
    hasilnya.
    """
    data_ocr = data_ocr or {}
    angka_ocr = _angka(data_ocr.get('nik'))
    angka_form = _angka(getattr(penduduk, 'nik', ''))
    cocok_nik = bool(angka_ocr) and angka_ocr == angka_form

    mirip_nama = _mirip(getattr(penduduk, 'nama', ''), data_ocr.get('nama'))
    keterbacaan = max(0.0, min(float(confidence or 0), 100.0)) / 100.0

    return [
        {
            'field': 'nik',
            'label': _LABEL['nik'],
            'formulir': angka_form or '-',
            'ocr': angka_ocr or '-',
            'kecocokan': 1.0 if cocok_nik else 0.0,
            'bobot': BOBOT['nik'],
            'keterangan': 'persis' if cocok_nik else ('tidak terbaca OCR' if not angka_ocr else 'berbeda'),
        },
        {
            'field': 'nama',
            'label': _LABEL['nama'],
            'formulir': _huruf(getattr(penduduk, 'nama', '')) or '-',
            'ocr': _huruf(data_ocr.get('nama')) or '-',
            'kecocokan': mirip_nama,
            'bobot': BOBOT['nama'],
            'keterangan': f'{mirip_nama * 100:.0f}% mirip' if data_ocr.get('nama') else 'tidak terbaca OCR',
        },
        {
            'field': 'keterbacaan',
            'label': _LABEL['keterbacaan'],
            'formulir': '-',
            'ocr': f'{keterbacaan * 100:.1f}%',
            'kecocokan': keterbacaan,
            'bobot': BOBOT['keterbacaan'],
            'keterangan': 'confidence Tesseract atas teks yang terbaca',
        },
    ]


def hitung_skor(baris):
    """Skor 0..100 dari bobot x kecocokan tiap baris."""
    return round(sum(b['kecocokan'] * b['bobot'] for b in baris) * 100, 1)


def ringkasan_teks(baris):
    """Satu baris teks alasan, dipakai untuk catatan verifikasi AI."""
    return '; '.join(f"{b['label']}: {b['keterangan']}" for b in baris)


def nilai_berkas(penduduk, data_ocr, confidence, jenis):
    """Satu-satunya pintu penilaian: kembalikan skor, prescreen, dan catatan.

    Dipakai core/ocr_processor.py saat berkas baru masuk dan oleh panel review
    admin saat petugas mengoreksi nilai OCR, supaya keduanya tidak pernah
    menghasilkan angka yang berbeda.
    """
    if jenis not in JENIS_BERNILAI:
        return {
            'skor': None,
            'prescreen': 'belum_dinilai',
            'catatan': (
                'Berkas non-KTP tidak dipasangkan dengan isian formulir karena '
                'tidak ada padanan field-nya; periksa manual oleh petugas.'
            ),
            'baris': [],
        }

    baris = baris_perbandingan(penduduk, data_ocr, confidence)
    skor = hitung_skor(baris)
    prescreen = 'valid' if skor > AMBAT_VALID else 'review'
    keputusan = 'Valid' if prescreen == 'valid' else 'Perlu review manual petugas'
    catatan = (
        f'Kecocokan {skor}% terhadap isian formulir (ambang {AMBAT_VALID:.0f}%) '
        f'-> {keputusan}. {ringkasan_teks(baris)}'
    )
    return {'skor': skor, 'prescreen': prescreen, 'catatan': catatan, 'baris': baris}
