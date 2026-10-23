"""Aturan berkas unggahan: slot pada formulir dan pemeriksaan isinya.

Modul ini sengaja tidak mengenal request maupun messages. View yang menyusun
pesan untuk warga; di sini hanya ada angka batas dan pemeriksa berkas, sehingga
core.middleware bisa menghitung jatah ukuran permintaan tanpa mengimpor views.py.
"""
import logging
import os

log = logging.getLogger('core.unggah')

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Batas resolusi untuk foto KTP/KK. Berkas di bawah 5 MB tetap bisa mengurai ke
# ratusan megapiksel (decompression bomb) dan menghabiskan memori saat OCR, jadi
# dimensi total dibatasi di sini; 40 MP jauh di atas kebutuhan dokumen pindai.
MAX_IMAGE_PIXELS = 40_000_000

# Lampiran yang wajib ada pada formulir pengajuan.
LAMPILAN_UPLOAD = [('ktp', 'KTP'), ('kk', 'Kartu Keluarga')]
# Pasfoto ikut di form yang sama, tetapi aturannya berbeda: hanya gambar (tanpa
# PDF) dan tidak wajib. Kartu warga tanpa pasfoto tetap terbit, dengan inisial
# nama sebagai pengganti fotonya. Karena itu pasfoto masuk SEMUA_LAMPILAN (untuk
# pemeriksaan berkas dan jatah ukuran permintaan) tapi tidak LAMPILAN_UPLOAD
# (daftar berkas yang harus ada).
LAMPILAN_PILIHAN = [('pasfoto', 'Pasfoto')]
SEMUA_LAMPILAN = LAMPILAN_UPLOAD + LAMPILAN_PILIHAN
GAMBAR_SAJA = frozenset(field for field, _ in LAMPILAN_PILIHAN)

EXTENSI_DOKUMEN = ('.pdf', '.jpg', '.jpeg', '.png')
EXTENSI_GAMBAR = ('.jpg', '.jpeg', '.png')


def valid_upload(uploaded, max_bytes=MAX_UPLOAD_BYTES, *, hanya_gambar=False):
    """Ukuran + ekstensi + isi file harus cocok, dan ClamAV harus bersih.

    Batas ukuran sengaja ada di sini juga (bukan hanya di pemanggil) supaya
    jalur unggah baru tidak lupa memeriksanya. `hanya_gambar` dipakai pasfoto:
    PDF adalah dokumen yang sah untuk KTP/KK, tapi bukan foto. Saat
    CLAMAV_ENABLED aktif tapi server ClamAV tidak bisa dihubungi, hasilnya
    ditolak (fail closed) - lebih baik unggahan gagal daripada lolos tanpa
    pemindaian.
    """
    if uploaded.size > max_bytes:
        return False
    name = os.path.basename(uploaded.name or '').lower()
    if hanya_gambar:
        if not name.endswith(EXTENSI_GAMBAR):
            return False
    elif not name.endswith(EXTENSI_DOKUMEN):
        return False
    uploaded.seek(0)
    header = uploaded.read(8)
    uploaded.seek(0)
    if name.endswith('.pdf'):
        valid = header.startswith(b'%PDF-')
    else:
        valid = False
        try:
            from PIL import Image
            image = Image.open(uploaded)
            image.verify()
            valid = image.format in {'JPEG', 'PNG'}
            if valid:
                # verify() tidak men-decode penuh, jadi buka ulang untuk membaca
                # dimensi dan menolak bomb yang lolos dari batas ukuran byte.
                uploaded.seek(0)
                image = Image.open(uploaded)
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    valid = False
        except Exception:
            # Sengaja lebar: bagi pemeriksa berkas, segala cara gagal baca
            # (file rusak, bukan gambar, bomb, EOF di tengah header) hasilnya
            # sama-sama "tidak boleh masuk". Menutup hanya tipe tertentu justru
            # membiarkan galat tak terduga lolos sebagai unggahan sah.
            valid = False
    if not valid:
        return False
    return bersih_clamav(uploaded)


def bersih_clamav(uploaded):
    """Pemindaian ClamAV; nonaktif = selalu boleh, aktif tapi mati = ditolak.

    Socket diberi batas waktu 10 detik. Tanpa itu, ClamAV yang tidak menjawab
    membuat permintaan unggahan menggantung sampai server web menyerah dan
    warga hanya melihat halaman yang membeku.
    """
    from django.conf import settings
    if not settings.CLAMAV_ENABLED:
        return True
    try:
        import clamd
        uploaded.seek(0)
        klien = clamd.ClamdNetworkSocket(settings.CLAMAV_HOST, settings.CLAMAV_PORT, timeout=10)
        hasil = klien.instream(uploaded)
        uploaded.seek(0)
        return not hasil or all(nilai[0] == 'OK' for nilai in hasil.values())
    except Exception as galat:
        # Fail closed: tanpa pemindaian yang benar-benar berhasil, berkas tidak
        # masuk. Petugas masih bisa tahu penyebabnya dari log proses.
        log.warning('ClamAV tidak bisa dihubungi, unggahan ditolak: %s', galat)
        return False
