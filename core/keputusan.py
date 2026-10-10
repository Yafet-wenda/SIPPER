"""Satu jalur untuk setiap keputusan atas pengajuan.

Perubahan status bisa datang dari tiga tempat: halaman antrean petugas,
halaman detail pengajuan, dan aksi massal di admin. Kalau masing-masing
menulis logikanya sendiri, yang terakhir selalu tertinggal — dulu aksi admin
hanya mengganti status sehingga waktu verifikasi kosong, kartu tidak terbit,
warga tidak dikirimi email, dan angka statistik kehilangan jejak. Semua jalur
kini memanggil :func:`terapkan_status`.
"""
import secrets
from datetime import timedelta
from io import BytesIO

import qrcode
from django.core.files.base import ContentFile
from django.utils import timezone

from .emails import notify_status
from .models import AuditLog, KartuDigital


def _buat_qr(request, card):
    """Tulis berkas QR untuk kartu; isinya URL publik /kartu/<kode>/."""
    buffer = BytesIO()
    qrcode.make(request.build_absolute_uri(f'/kartu/{card.kode}/')).save(buffer, format='PNG')
    card.qr_code.save(f'{card.kode}.png', ContentFile(buffer.getvalue()), save=True)
    return card


def terbitkan_kartu(request, person):
    """Buat kartu digital milik warga, lengkap dengan berkas QR-nya.

    Panggilan ini idempoten: warga yang kartunya sudah ada tidak dibuatkan kartu
    kedua, hanya QR-nya dilengkapi bila belum pernah terbentuk.
    """
    card, _ = KartuDigital.objects.get_or_create(
        penduduk=person,
        defaults={'kode': f'SPR-{secrets.token_urlsafe(16)}',
                  'berlaku_sampai': timezone.now().date() + timedelta(days=365)})
    if not card.qr_code:
        _buat_qr(request, card)
    return card


def lengkapi_kartu(request, card):
    """Isi kode bila kosong, simpan kartunya, lalu render QR bila belum ada.

    ``kode`` dan ``qr_code`` sengaja dibiarkan hanya-baca di form: keduanya
    identitas mesin, bukan sesuatu yang diketik petugas. Tanpa pengisian ini
    form tambah kartu tidak pernah bisa disimpan karena kolom wajib itu kosong
    — bug yang membuat halaman admin kehilangan salah satu fungsinya.

    Dipakai oleh :func:`terbitkan_kartu` dan oleh form admin, sehingga kartu
    hasil keduanya identik.
    """
    if not card.kode:
        card.kode = f'SPR-{secrets.token_urlsafe(16)}'
    card.save()
    if not card.qr_code:
        _buat_qr(request, card)
    return card


def beri_tahu_status(person, status, actor):
    """Beri tahu warga lewat email; kegagalan kirim dicatat, bukan dilempar.

    Status di database sudah tersimpan sebelum fungsi ini dipanggil, jadi
    SMTP yang mati tidak boleh membatalkan verifikasi petugas. Yang hilang
    hanyalah pemberitahuannya, dan itu sengaja ditulis ke AuditLog supaya
    terlihat di halaman histori, bukan hilang tanpa jejak.
    """
    try:
        sent, detail = notify_status(person, status)
    except Exception as error:
        # Sengaja lebar: status sudah tersimpan, dan halaman petugas tidak boleh
        # 500 hanya karena email tidak bisa berangkat (alamat salah, DNS, dsb).
        AuditLog.objects.create(user=actor, aksi='notifikasi-gagal',
                                deskripsi=f'Email status {status} untuk {person.nama} gagal: {error}')
        return False
    if sent:
        AuditLog.objects.create(user=actor, aksi='notifikasi',
                                deskripsi=f'Email status {status} dikirim ke {detail}.')
    return sent


def terapkan_status(item, status, actor, request, *, catatan=None, sumber='petugas'):
    """Simpan keputusan petugas atas satu pengajuan, dengan seluruh efeknya.

    Hanya status yang benar-benar berubah yang memicu kartu, email, dan catatan
    audit; mengoreksi catatan petugas tidak boleh mengirim surat kedua ke warga.
    Mengembalikan ``(status_berubah, email_terkirim)`` supaya pemanggil bisa
    merangkai pesannya sendiri.
    """
    berubah = item.status != status
    fields = ['status']
    if catatan is not None and item.catatan != catatan:
        item.catatan = catatan
        fields.append('catatan')
    if berubah:
        item.status = status
        item.verified_by = actor
        item.verified_at = timezone.now()
        fields += ['verified_by', 'verified_at']
    item.save(update_fields=fields)
    if not berubah:
        return False, False
    AuditLog.objects.create(user=actor, aksi='verifikasi',
                            deskripsi=f'Status {item.penduduk.nama} menjadi {item.get_status_display()} '
                                      f'(lewat {sumber}).')
    if status == 'disetujui':
        terbitkan_kartu(request, item.penduduk)
    return True, beri_tahu_status(item.penduduk, status, actor)
