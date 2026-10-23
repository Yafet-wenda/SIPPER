"""Pekerja OCR di luar jalur request.

Dulu fungsi ini tinggal di core/views.py sehingga core.admin_site harus mengimpor
views untuk memicu proses ulang dari aksi admin. Dipindah ke sini supaya
"bagaimana OCR dijalankan" punya satu rumah, terpisah dari "siapa boleh
memanggil halaman apa".
"""
import logging
import threading

from django.db import connection

log = logging.getLogger('core.ocr')

# OCR menjalankan OpenCV + Tesseract yang berat. Satu unggahan warga bisa
# memicu beberapa berkas sekaligus, dan tanpa batas ini tiap berkas men-spawn
# thread yang semuanya berebut CPU/RAM pada server tunggal. Semaphore membatasi
# pekerjaan OCR sungguhan sampai dua benang; thread lain tetap dibuat tapi
# menunggu di sini.
OCR_CONCURRENCY = threading.BoundedSemaphore(2)


def jalankan_ocr(dokumen_id):
    """Baca satu berkas dengan OCR lalu simpan hasilnya, aman dipanggil dari thread.

    Tujuan fungsi ini dijalankan sebagai benang latar, jadi tidak ada nilai
    dikembalikan: kegagalan dicatat dan koneksi DB milik benang sendiri ditutup
    di finally karena thread daemon tidak dibersihkan otomatis oleh Django.
    """
    from .models import AuditLog, Dokumen
    try:
        with OCR_CONCURRENCY:
            from .ocr_processor import process_document
            dokumen = Dokumen.objects.filter(pk=dokumen_id).first()
            if dokumen is None:
                # Berknya sudah dihapus sebelum benang ini sempat jalan —
                # keadaan normal saat petugas menyortir cepat, bukan kerusakan,
                # jadi tidak perlu dicatat sebagai galat.
                log.info('OCR dilewati: dokumen %s sudah tidak ada', dokumen_id)
                return
            hasil = process_document(dokumen)
            if hasil['success']:
                AuditLog.objects.create(
                    aksi='ocr_processed',
                    deskripsi=(
                        f'OCR berhasil pada {dokumen.nama} '
                        f'(confidence: {hasil["confidence"]}%, '
                        f'skor kecocokan: {hasil["skor"]}%, '
                        f'prapemilahan: {hasil["prescreen"]})'
                    ),
                )
            elif hasil.get('skipped'):
                # Bukan kegagalan: berkas jenis ini memang tidak dinilai mesin.
                # Dicatat terpisah supaya log "ocr_failed" tetap berarti rusak.
                AuditLog.objects.create(
                    aksi='ocr_dilewati',
                    deskripsi=f'OCR dilewati pada {dokumen.nama}: {hasil["error"]}',
                )
            else:
                log.warning('OCR gagal membaca dokumen %s: %s', dokumen_id, hasil.get('error'))
    except Exception as galat:
        # Dicatat ke log proses DAN ke log audit: petugas membaca yang terakhir,
        # pengelola mesin membaca yang pertama. Kegagalan pencatatan tidak boleh
        # membatalkan pekerjaan yang sudah selesai.
        log.exception('OCR dokumen %s berhenti karena galat tak terduga', dokumen_id)
        try:
            AuditLog.objects.create(aksi='ocr_failed', deskripsi=f'OCR gagal: {galat}')
        except Exception:
            log.exception('AuditLog ocr_failed juga gagal ditulis untuk dokumen %s', dokumen_id)
    finally:
        connection.close()


def picu_async(dokumen_id):
    """Lemparkan OCR ke benang latar supaya request pemanggil tidak ikut menunggu."""
    threading.Thread(target=jalankan_ocr, args=(dokumen_id,), daemon=True).start()
