"""Penyusun laporan PDF verifikasi satu pengajuan untuk petugas SIPPER.

Dokumen ini sengaja memuat data pribadi penuh (NIK utuh, alamat, tanggal lahir,
hasil baca OCR) karena hanya boleh dibuat oleh core.views.pengajuan_report_pdf
yang sudah disaring `is_officer`. Jangan panggil dari rute publik: halaman
validasi kartu /kartu/<kode>/ justru menyamarkan NIK karena siapa pun boleh
membukanya.

Tidak ada panggilan jaringan di sini. reportlab menggambar di server dan
berkasnya dialirkan ke browser petugas lewat HttpResponse yang sama.
"""
from xml.sax.saxutils import escape

from datetime import date, datetime

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HIJAU = colors.HexColor('#1f6b58')
HIJAU_MUDA = colors.HexColor('#e8f3ef')
TUA = colors.HexColor('#18312b')
ABU = colors.HexColor('#64748b')
GARIS = colors.HexColor('#cfd9d5')

# Lebar tetap kolom label/isi supaya semua tabel rata dan enak dibaca.
LEBAR_LABEL = 46 * mm
LEBAR_ISI = 126 * mm

# Nilai OCR bisa panjang (alamat satu paragraf). Dipotong supaya satu berkas
# tetap ringkas; teks mentah lengkap selalu bisa dilihat di halaman detail.
MAKS_PANJANG_NILAI = 320

LABEL_WARGA = [
    ('Nama lengkap', 'nama'),
    ('NIK', 'nik'),
    ('Daerah asal', 'daerah_asal'),
    ('Kota tujuan', 'kota_tujuan'),
    ('Tujuan berpindah', 'tujuan'),
    ('Tanggal mulai', 'tanggal_mulai'),
    ('Perkiraan kembali', 'perkiraan_kembali'),
    ('Nomor telepon', 'nomor_telepon'),
]

LABEL_OCR = {
    'nama': 'Nama',
    'nik': 'NIK',
    'alamat': 'Alamat',
    'tempat_lahir': 'Tempat lahir',
    'tanggal_lahir': 'Tanggal lahir',
    'ttl': 'Tempat / tanggal lahir',
    'jenis_kelamin': 'Jenis kelamin',
    'pekerjaan': 'Pekerjaan',
    'agama': 'Agama',
    'status_perkawinan': 'Status perkawinan',
    'no_kk': 'Nomor KK',
    'nomor_kk': 'Nomor KK',
    'anggota': 'Anggota keluarga',
}

GAYA_JUDUL = ParagraphStyle('judul_seksi', fontName='Helvetica-Bold', fontSize=11.5,
                            leading=15, textColor=TUA, spaceBefore=0, spaceAfter=4)
GAYA_SUB = ParagraphStyle('sub_seksi', fontName='Helvetica-Bold', fontSize=10,
                          leading=13, textColor=HIJAU, spaceBefore=2, spaceAfter=3)
GAYA_ISI = ParagraphStyle('isi', fontName='Helvetica', fontSize=9.5, leading=12.5, textColor=TUA)
GAYA_LABEL = ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5, textColor=ABU)
GAYA_KECIL = ParagraphStyle('kecil', fontName='Helvetica-Oblique', fontSize=8.5, leading=11, textColor=ABU)


_TABEL_ASCII = str.maketrans({
    '—': '-', '–': '-', '…': '...', '“': '"', '”': '"', '‘': "'", '’': "'",
    '•': '*', '→': '>', '·': '-',
})


def _teks(nilai):
    """Nilai apa pun jadi satu baris teks aman untuk Paragraph (di-escape).

    Helvetica bawaan reportlab memakai penyandian WinAnsi (cp1252). Karakter di
    luar itu -- tanda pisah panjang, panah, bullet -- tercetak sebagai kotak
    kosong, padahal hasil OCR dan isian warga bisa memuatnya. Jadi karakter
    semacam itu diganti ke padanan ASCII lebih dulu.
    """
    if nilai is None or nilai == '':
        return '-'
    teks = ' '.join(str(nilai).split())
    teks = teks.translate(_TABEL_ASCII).encode('cp1252', 'replace').decode('cp1252')
    return escape(teks[:MAKS_PANJANG_NILAI] + ('...' if len(teks) > MAKS_PANJANG_NILAI else ''))


def _tanggal(nilai):
    """Tanggal/waktu → teks. DateField dan DateTimeField ditangani terpisah:
    date tidak punya utcoffset, jadi timezone.is_aware() akan error padanya."""
    if not nilai:
        return '-'
    if isinstance(nilai, datetime):
        if timezone.is_aware(nilai):
            nilai = timezone.localtime(nilai)
        return nilai.strftime('%d/%m/%Y %H:%M')
    if isinstance(nilai, date):
        return nilai.strftime('%d/%m/%Y')
    return escape(str(nilai))


def _label_ocr(kunci):
    """Nama field OCR dalam bentuk manusia. Sengaja tidak di-escape di sini:
    _tabel_baris sudah melewatkan kolom label lewat _teks, dan escape ganda akan
    membuat '&' tampil sebagai '&amp;' di berkas."""
    return LABEL_OCR.get(kunci, kunci.replace('_', ' ').title())


def _tabel_baris(baris):
    """Satu tabel label/isi; isinya Paragraph agar nilai panjang ikut melipat."""
    data = [[Paragraph(_teks(label), GAYA_LABEL), Paragraph(nilai, GAYA_ISI)] for label, nilai in baris]
    tabel = Table(data, colWidths=[LEBAR_LABEL, LEBAR_ISI], hAlign='LEFT')
    tabel.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, GARIS),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tabel


def _seksi(judul):
    return [Paragraph(_teks(judul), GAYA_JUDUL),
            Table([['']], colWidths=[LEBAR_LABEL + LEBAR_ISI], rowHeights=[1.2],
                  style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), HIJAU)],
                                   hAlign='LEFT')),
            Spacer(1, 4)]


def _isi_warga(item):
    """Isian warga saat mendaftar — bukan hasil OCR."""
    warga = item.penduduk
    baris = []
    for label, kunci in LABEL_WARGA:
        nilai = getattr(warga, kunci)
        if kunci in ('tanggal_mulai', 'perkiraan_kembali'):
            baris.append((label, _tanggal(nilai)))
        else:
            baris.append((label, _teks(nilai)))
    return _tabel_baris(baris)


def _status_pengajuan(item):
    baris = [
        ('Status', _teks(item.get_status_display())),
        ('Dikirim', _tanggal(item.submitted_at)),
        ('Diverifikasi', _tanggal(item.verified_at)),
        ('Oleh', _teks(getattr(item.verified_by, 'username', None))),
        ('Catatan petugas', _teks(item.catatan) if item.catatan else '(kosong)'),
    ]
    return _tabel_baris(baris)


def _kartu(item):
    kartu = getattr(item.penduduk, 'kartu', None)
    if kartu is None:
        return _tabel_baris([('Kartu digital', 'Belum terbit (pengajuan belum disetujui).')])
    baris = [
        ('Kode validasi', _teks(kartu.kode)),
        ('Berlaku sampai', _tanggal(kartu.berlaku_sampai)),
        ('Status kartu', _teks(kartu.status)),
        ('Keterangan', 'Masih valid.' if kartu.is_valid() else 'Sudah tidak valid (kedaluwarsa atau dinonaktifkan).'),
    ]
    return _tabel_baris(baris)


def _bagian_dokumen(item):
    """Satu blok per berkas: meta petugas + data terstruktur hasil OCR."""
    blok = []
    dokumen = item.penduduk.dokumen.order_by('jenis', 'id')
    if not dokumen:
        return [Paragraph('Belum ada berkas yang diunggah warga.', GAYA_ISI)]
    for nomor, berkas in enumerate(dokumen, start=1):
        blok.append(Paragraph(f"{nomor}. {escape(berkas.get_jenis_display())} - {escape(berkas.nama)}", GAYA_SUB))
        cocok = 'Ya, sama dengan NIK terdaftar.' if (berkas.extracted_nik and berkas.extracted_nik == item.penduduk.nik) else (
            'Tidak, NIK hasil baca berbeda.' if berkas.extracted_nik else 'NIK tidak terbaca.')
        meta = [
            ('Berkas', _teks(f"{berkas.nama} ({berkas.ukuran // 1024 if berkas.ukuran else 0} KB)")),
            ('Status penilaian petugas', _teks(berkas.get_status_display())),
            ('Diunggah', _tanggal(berkas.uploaded_at)),
            ('Confidence OCR', f"{berkas.ocr_confidence:.1f}%" if berkas.ocr_confidence is not None else 'belum diproses'),
            ('NIK hasil baca', _teks(berkas.extracted_nik)),
            ('Cocok dengan NIK warga', cocok),
            ('Terverifikasi otomatis', 'Ya' if berkas.ai_verified else 'Tidak'),
            ('Catatan verifikasi', _teks(berkas.ai_verification_notes) if berkas.ai_verification_notes else '(kosong)'),
        ]
        blok.append(_tabel_baris(meta))
        terstruktur = berkas.extracted_data or {}
        if isinstance(terstruktur, dict):
            baris_ocr = [(f'- {_label_ocr(kunci)}', _teks(nilai)) for kunci, nilai in terstruktur.items()]
        else:
            # extracted_data adalah JSONField: parser saat ini selalu menyimpan
            # dict, tapi list/nilai lain tidak boleh membuat laporan gagal 500.
            baris_ocr = [('- Data', _teks(terstruktur))]
        if baris_ocr:
            blok.append(Spacer(1, 3))
            blok.append(Paragraph('Data terstruktur hasil OCR', GAYA_LABEL))
            blok.append(Spacer(1, 2))
            blok.append(_tabel_baris(baris_ocr))
        else:
            blok.append(Spacer(1, 2))
            blok.append(Paragraph('Tidak ada data terstruktur untuk berkas ini '
                                  '(belum di-OCR, atau jenisnya di luar KTP/KK).', GAYA_KECIL))
        blok.append(Spacer(1, 7))
    return blok


def bangun(item, petugas, response):
    """Isi `response` dengan PDF laporan; petugas dipakai di kaki dokumen.

    Kompresi halaman dimatikan (pageCompression=0) supaya berkas hasil unduhan
    bisa diperiksa isinya secara teks — berguna saat pengujian, dan ukuran satu
    laporan tetap kecil.
    """
    waktu = timezone.localtime()
    dokumen = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=27 * mm, bottomMargin=20 * mm,
        title=f'Laporan Verifikasi Pengajuan #{item.pk}',
        author='SIPPER',
        pageCompression=0,
    )

    def kepala(canv, doc):
        tinggi = 18 * mm
        canv.saveState()
        canv.setFillColor(HIJAU)
        canv.rect(0, doc.pagesize[1] - tinggi, doc.pagesize[0], tinggi, fill=1, stroke=0)
        canv.setFillColor(colors.white)
        canv.setFont('Helvetica-Bold', 14)
        canv.drawString(18 * mm, doc.pagesize[1] - 8 * mm, 'SIPPER')
        canv.setFont('Helvetica', 8.5)
        canv.drawString(18 * mm, doc.pagesize[1] - 12.5 * mm, 'Sistem Informasi Penduduk Perantauan | Laporan Verifikasi Petugas')
        canv.setFont('Helvetica-Bold', 10)
        canv.drawRightString(doc.pagesize[0] - 18 * mm, doc.pagesize[1] - 8 * mm, f'Pengajuan #{item.pk}')
        canv.setFont('Helvetica', 8.5)
        canv.drawRightString(doc.pagesize[0] - 18 * mm, doc.pagesize[1] - 12.5 * mm, waktu.strftime('Dicetak %d/%m/%Y %H:%M'))
        canv.restoreState()

    def kaki(canv, doc):
        canv.saveState()
        canv.setStrokeColor(GARIS)
        canv.setLineWidth(0.5)
        canv.line(18 * mm, 14 * mm, doc.pagesize[0] - 18 * mm, 14 * mm)
        canv.setFont('Helvetica', 7.8)
        canv.setFillColor(ABU)
        canv.drawString(18 * mm, 10.5 * mm,
                        f'Dicetak oleh: {petugas.username} - Dokumen internal, memuat data pribadi warga.')
        canv.drawRightString(doc.pagesize[0] - 18 * mm, 10.5 * mm, f'Halaman {doc.page}')
        canv.restoreState()

    alur = []
    alur += _seksi('Identitas warga (isian pendaftaran)')
    alur.append(_isi_warga(item))
    alur.append(Spacer(1, 10))
    alur += _seksi('Status pengajuan')
    alur.append(_status_pengajuan(item))
    alur.append(Spacer(1, 10))
    alur += _seksi('Dokumen pendukung dan hasil baca OCR')
    alur += _bagian_dokumen(item)
    alur += _seksi('Kartu digital')
    alur.append(_kartu(item))
    alur.append(Spacer(1, 10))
    alur.append(Paragraph('Perbandingan di atas memakai data yang diinput warga dan teks yang dibaca '
                          'Tesseract. Nilai hasil OCR dapat salah baca, sehingga keputusan akhir tetap '
                          'menjadi tanggung jawab petugas.', GAYA_KECIL))

    dokumen.build(alur, onFirstPage=kepala, onLaterPages=kepala)
