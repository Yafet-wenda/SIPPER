"""Pemberitahuan email ke warga saat status pengajuannya berubah."""
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

PESAN_STATUS = {
    'disetujui': 'Pengajuan Anda disetujui dan kartu digital sudah dapat dibuka dari dasbor.',
    'ditolak': 'Pengajuan Anda ditolak. Periksa catatan petugas pada dasbor untuk berkas yang kurang.',
    'perlu_perbaikan': 'Pengajuan Anda perlu perbaikan. Lengkapi catatannya lalu kirim ulang dari dasbor.',
    'menunggu': 'Pengajuan Anda tercatat dan sedang menunggu verifikasi petugas.',
}


def notify_status(person, status):
    """Kirim satu email ke warga pemilik data ini.

    Mengembalikan (terkirim, alasan). Panggilan ini sengaja tidak menangkap
    error sendiri: SMTP yang mati harus terlihat di log, dan penanganannya ada
    di pemanggil supaya status di database tetap tersimpan.
    """
    if not getattr(person, 'user', None) or not person.user.email:
        return False, 'Warga tidak memiliki email untuk diberitahu.'
    body = PESAN_STATUS.get(status)
    if not body:
        return False, 'Status ini tidak perlu diberitahukan.'
    send_mail(
        subject='SIPPER: status pengajuan Anda diperbarui',
        message=f'{person.nama}, {body}\n\nDikirim pada {timezone.localtime():%d %m %Y %H:%M} WIB',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[person.user.email],
        fail_silently=False,
    )
    return True, person.user.email
