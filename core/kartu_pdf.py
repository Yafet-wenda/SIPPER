"""Penggambar kartu digital PDF ukuran ID-1.

Isi gambar (foto, QR, teks tersamar) diambil dari objek KartuDigital, sedangkan
hak akses atasnya tetap diputus oleh core.views.download_card — persis pola
core.pdf_report untuk laporan petugas. Dulu seluruh blok penggambaran ini hidup
di dalam view sehingga satu fungsi mengurus izin, geometri, dan tata letak
sekaligus.
"""
import io
import logging

from django.utils import formats

log = logging.getLogger('core.kartu')

# Batasan operasional yang tercetak di kartu, baik versi layar maupun PDF.
# Teksnya dijaga di satu tempat supaya kartu web dan hasil unduhan tidak pernah
# berbeda pernyataan.
KARTU_BATASAN = [
    'SIPPER bukan pengganti dokumen seperti KTP, KK, atau SKPWRI.',
    'SIPPER tidak melakukan integrasi atau sinkronisasi langsung ke database nasional Dukcapil.',
    'Verifikasi dan kartu digital SIPPER hanya berlaku secara internal di dalam ekosistem aplikasi SIPPER.',
]
MERAH_KARTU = '#c8102e'

# Ukuran kartu identitas standar ID-1 — 85,60 × 53,98 mm, dipakai KTP, KK digital,
# BPJS, dan ATM. Poin PDF (72 poin = 1 inci) membuat kartu tercetak 1:1 ketika
# halaman dikeluarkan pada skala 100%, jadi hasil unduhan bisa langsung dipotong
# sebesar kartu asli. Rasio yang sama juga dipakai kartu layar (aspect-ratio di
# templates/card_v2.html) supaya bentuk keduanya tidak pernah berbeda.
POIN_PER_MM = 72 / 25.4
KARTU_ID1_MM = (85.6, 53.98)
KARTU_ID1_PT = (KARTU_ID1_MM[0] * POIN_PER_MM, KARTU_ID1_MM[1] * POIN_PER_MM)


def tanggal_kartu(tanggal):
    """Nama bulan gaya Indonesia untuk kartu PDF.

    strftime di server ini ikut locale C, jadi "%d %B %Y" mencetak
    "09 October 2027" sementara kartu layar sudah "09 Okt 2027". Formatter
    Django mengikuti LANGUAGE_CODE sehingga kedua tampilan selalu sama.
    """
    return formats.date_format(tanggal, 'd M Y')


def nik_samar(nik):
    """NIK berformat 16 digit dengan 12 angka pertama ditutupi."""
    return '*' * max(len(nik) - 4, 0) + nik[-4:]


def _potong_kata(kata, nama_font, ukuran, lebar_maks, document):
    """Iris satu kata yang lebih lebar dari kolomnya jadi beberapa potongan.

    Tanpa ini, nama 150 karakter tanpa spasi (batas kolom di basis data) jadi
    satu baris utuh selebar lebih dari dua halaman A4 dan menembus kartu.
    """
    if not kata or document.stringWidth(kata, nama_font, ukuran) <= lebar_maks:
        return [kata]
    potongan = []
    sisa = kata
    while sisa:
        ambil = 1
        while ambil < len(sisa) and document.stringWidth(sisa[:ambil + 1], nama_font, ukuran) <= lebar_maks:
            ambil += 1
        potongan.append(sisa[:ambil])
        sisa = sisa[ambil:]
    return potongan


def baris_teks(teks, nama_font, ukuran, lebar_maks, document):
    """Pecah kalimat jadi baris yang muat lebar kolom tanpa memotong kata."""
    baris, sekarang = [], ''
    kata_panjang = []
    for kata in teks.split():
        kata_panjang += _potong_kata(kata, nama_font, ukuran, lebar_maks, document)
    for kata in kata_panjang:
        calon = f'{sekarang} {kata}'.strip()
        if not sekarang or document.stringWidth(calon, nama_font, ukuran) <= lebar_maks:
            sekarang = calon
        else:
            baris.append(sekarang)
            sekarang = kata
    if sekarang:
        baris.append(sekarang)
    return baris


def potret_pasfoto(field):
    """Pasfoto siap cetak dengan rasio 3:4, terpotong dari tengah.

    reportlab tidak memotong gambar, jadi foto lanskap akan mendorong isi kartu
    keluar bila digambar apa adanya. Berkas yang rusak atau tidak terbaca
    dikembalikan None supaya kartu tetap terbit dengan blok inisial.
    """
    try:
        from PIL import Image
        with Image.open(field) as gambar:
            gambar = gambar.convert('RGB')  # paksa decode sebelum file ditutup
            lebar, tinggi = gambar.size
            target = 3 / 4
            if lebar / tinggi > target:
                baru = int(tinggi * target)
                kiri = (lebar - baru) // 2
                gambar = gambar.crop((kiri, 0, kiri + baru, tinggi))
            elif lebar / tinggi < target:
                baru = int(lebar / target)
                atas = (tinggi - baru) // 2
                gambar = gambar.crop((0, atas, lebar, atas + baru))
            # Kotak foto di kartu hanya 54x72 poin (19 x 25 mm). Tanpa pembatasan
            # ini, pasfoto 5 MB ikut tertempel utuh ke PDF dan ukuran berkasnya
            # membengkak; 600 piksel sudah lebih dari tajam untuk cetak 300 dpi.
            gambar.thumbnail((600, 800))
            # Dikemas ulang jadi JPEG. Objek PIL RGB dikirim reportlab sebagai
            # data mentah (~1 MB per foto), sedangkan berkas JPEG ditempel apa
            # adanya sehingga PDF kartu tetap ringan.
            buffer = io.BytesIO()
            gambar.save(buffer, format='JPEG', quality=82, optimize=True)
            buffer.seek(0)
            return buffer
    except Exception as galat:
        log.warning('Pasfoto tidak terbaca, kartu memakai inisial: %s', galat)
        return None


def bangun(card, response):
    """Gambar satu kartu ke objek respons PDF, halaman A4 skala cetak 100%."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    merah = colors.HexColor(MERAH_KARTU)
    tua = colors.HexColor('#17392b')
    redup = colors.HexColor('#5b6f66')
    document = canvas.Canvas(response, pagesize=A4)
    lebar_halaman, tinggi_halaman = A4

    # Isi blok batasan diukur lebih dulu karena tinggi bingkainya mengikuti
    # jumlah baris. Blok ini dicetak di bawah kartu, bukan di dalamnya: tiga
    # kalimat keteraturan tidak muat di kartu 54 mm dengan huruf yang masih
    # terbaca, persis seperti KTP asli yang juga tidak memuatnya.
    lebar_teks = 475
    baris_batasan = []
    for nomor, teks in enumerate(KARTU_BATASAN, start=1):
        baris_batasan += baris_teks(f'{nomor}. {teks}', 'Helvetica', 7.5, lebar_teks - 30, document)

    # ---- Kartu ukuran asli (ID-1) ----
    k_lebar, k_tinggi = KARTU_ID1_PT
    x0 = (lebar_halaman - k_lebar) / 2
    y_atas = tinggi_halaman - 88
    x1 = x0 + k_lebar
    y_bawah = y_atas - k_tinggi
    dalam = 7           # margin isi di dalam kartu
    head = 26           # pita judul merah
    pita = 22           # pita masa berlaku + kode validasi
    f_lebar, f_tinggi = 54, 72            # kotak foto 3:4, sebangun dengan kartu layar
    qr_sisi = 54
    atas_badan = y_atas - head - 7
    bawah_pita = y_bawah + dalam
    x_identitas = x0 + dalam + f_lebar + 8
    lebar_identitas = (x1 - dalam - qr_sisi - 8) - x_identitas

    # Bingkai kartu.
    document.setFillColor(colors.white)
    document.setStrokeColor(colors.HexColor('#d7dcd3'))
    document.setLineWidth(.8)
    document.roundRect(x0, y_bawah, k_lebar, k_tinggi, 5, fill=1, stroke=1)

    # Header merah. reportlab tidak bisa membulatkan dua sudut saja, jadi sudut
    # bawah ditutup persegi panjang yang warnanya sama.
    document.setFillColor(merah)
    document.roundRect(x0, y_atas - head, k_lebar, head, 5, fill=1, stroke=0)
    document.rect(x0, y_atas - head, k_lebar, head / 2, fill=1, stroke=0)
    document.setFillColor(colors.white)
    document.setFont('Helvetica-Bold', 11)
    document.drawString(x0 + dalam, y_atas - 12, 'Kartu SIPPER')
    document.setFont('Helvetica', 5.2)
    document.drawString(x0 + dalam, y_atas - 19.5, 'Sistem Informasi Penduduk Perantauan')
    document.setFont('Helvetica-Bold', 5.6)
    document.drawRightString(x1 - dalam, y_atas - 12, 'TERVERIFIKASI' if card.is_valid() else 'TIDAK AKTIF')

    # Pasfoto di kiri, blok inisial bila warga belum mengunggah foto.
    document.setFillColor(colors.HexColor('#eef0df'))
    document.roundRect(x0 + dalam, atas_badan - f_tinggi, f_lebar, f_tinggi, 3, fill=1, stroke=0)
    potret = potret_pasfoto(card.penduduk.foto) if card.penduduk.foto else None
    if potret is not None:
        try:
            document.drawImage(ImageReader(potret), x0 + dalam, atas_badan - f_tinggi,
                               width=f_lebar, height=f_tinggi, preserveAspectRatio=True, mask='auto')
        except Exception as galat:
            log.warning('Foto gagal ditempel ke kartu %s, dipakai inisial: %s', card.kode, galat)
            potret = None
    if potret is None:
        # Sama seperti kartu layar: blok merah muda mengisi kotak foto, bukan
        # lingkaran mengambang di tengahnya.
        document.setFillColor(colors.HexColor('#f6d9dc'))
        document.roundRect(x0 + dalam, atas_badan - f_tinggi, f_lebar, f_tinggi, 3, fill=1, stroke=0)
        document.setFillColor(merah)
        document.setFont('Helvetica-Bold', 20)
        document.drawCentredString(x0 + dalam + f_lebar / 2, atas_badan - f_tinggi / 2 - 5.5,
                                   card.penduduk.inisial or '?')

    # QR di kanan atas, sejajar dengan kepala kolom identitas.
    if card.qr_code and card.qr_code.path:
        document.drawImage(ImageReader(card.qr_code.path), x1 - dalam - qr_sisi,
                           atas_badan - qr_sisi, width=qr_sisi, height=qr_sisi,
                           preserveAspectRatio=True, mask='auto')

    # Identitas: nama, NIK tersamar, domisili. NIK tidak dicetak utuh, sama
    # seperti kartu di layar, karena berkas PDF bisa menyebar lewat ponsel.
    # Semua nilai dipecah per baris selebar kolomnya supaya nama atau kota tujuan
    # yang panjang tidak menimpa QR di sebelah kanan.
    y_teks = atas_badan
    document.setFont('Helvetica-Bold', 12)
    document.setFillColor(tua)
    for baris in baris_teks(card.penduduk.nama, 'Helvetica-Bold', 12, lebar_identitas, document)[:2]:
        y_teks -= 14
        document.drawString(x_identitas, y_teks, baris)
    for label, nilai in (('NIK', nik_samar(card.penduduk.nik)),
                         ('DOMISILI TUJUAN', card.penduduk.kota_tujuan)):
        y_teks -= 13
        document.setFont('Helvetica', 4.8)
        document.setFillColor(redup)
        document.drawString(x_identitas, y_teks, label)
        document.setFont('Helvetica-Bold', 8.5)
        document.setFillColor(tua)
        for baris in baris_teks(nilai, 'Helvetica-Bold', 8.5, lebar_identitas, document)[:2]:
            y_teks -= 10
            document.drawString(x_identitas, y_teks, baris)

    # Petunjuk kecil di bawah kolom identitas; QR adalah satu-satunya jalan
    # memeriksa status kartu setelah berkas PDF dicetak dan difotokopi.
    document.setFont('Helvetica', 4.6)
    document.setFillColor(redup)
    document.drawString(x0 + dalam, bawah_pita + pita + 7,
                        'Pindai QR untuk memeriksa status kartu ini.')

    # Pita masa berlaku + kode validasi di dasar kartu.
    document.setFillColor(colors.HexColor('#f4f6f2'))
    document.roundRect(x0 + dalam, bawah_pita, k_lebar - 2 * dalam, pita, 3, fill=1, stroke=0)
    for x, label, nilai, ukuran in ((x0 + dalam + 5, 'BERLAKU SAMPAI', tanggal_kartu(card.berlaku_sampai), 8),
                                     (x0 + 118, 'KODE VALIDASI', card.kode, 6.6)):
        document.setFont('Helvetica', 4.4)
        document.setFillColor(redup)
        document.drawString(x, bawah_pita + pita - 7, label)
        document.setFont('Helvetica-Bold', ukuran)
        document.setFillColor(tua)
        document.drawString(x, bawah_pita + 4, nilai)

    # ---- Keterangan di luar kartu, tetap pada ukuran baca normal ----
    y_petunjuk = y_bawah - 20
    document.setFont('Helvetica-Oblique', 7.5)
    document.setFillColor(redup)
    document.drawString(60, y_petunjuk,
                        'Format kartu mengikuti standar ID-1 (85,60 × 53,98 mm). '
                        'Cetak pada skala 100% lalu potong mengikuti bingkai.')

    atas_batasan = y_petunjuk - 14
    bawah_batasan = atas_batasan - (34 + len(baris_batasan) * 10)
    document.setFillColor(colors.white)
    document.setStrokeColor(colors.HexColor('#e3e7e0'))
    document.roundRect(60, bawah_batasan, lebar_teks, atas_batasan - bawah_batasan, 8, fill=1, stroke=1)
    document.setFont('Helvetica-Bold', 9)
    document.setFillColor(merah)
    document.drawString(75, atas_batasan - 20, 'Batasan & operasional sistem')
    document.setFont('Helvetica', 7.5)
    document.setFillColor(colors.HexColor('#3f4a44'))
    tinggi_teks = atas_batasan - 36
    for baris in baris_batasan:
        document.drawString(75, tinggi_teks, baris)
        tinggi_teks -= 10
    document.setFont('Helvetica', 7)
    document.setFillColor(redup)
    document.drawString(60, bawah_batasan - 15, 'Kartu dibuat otomatis oleh SIPPER. Status dapat diperiksa ulang dengan memindai QR.')
    document.save()
