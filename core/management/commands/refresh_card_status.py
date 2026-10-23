"""Tutup kartu digital yang masa berlakunya sudah lewat, tanpa menunggu dipindai.

Halaman validasi (:func:`core.views.validate_card`) sudah mengubah status kartunya
sendiri saat ada yang memindai, jadi warga selalu melihat kebenaran. Yang tertinggal
adalah baris di basis data: kartu tak bersarang tetap tercatat ``aktif`` setelah
tanggalnya lewat, dan setiap pemeriksa yang menyaring ``status`` — ekspor, laporan,
shell admin — ikut tertipu. Perintah ini menutup celah itu lewat jalur terjadwal.

Arahnya sengaja satu arah. Kartu berstatus ``expired`` tidak dihidupkan kembali
hanya karena petugas memajukan ``berlaku_sampai``: nilai status bisa saja ditulis
tangan, dan petugas punya ``nonaktif`` untuk keputusan nyata. Menghidupkan kartu
secara otomatis berarti membatalkan keputusan manusia tanpa jejak.
"""
from django.core.management.base import BaseCommand

from core.models import KartuDigital


class Command(BaseCommand):
    help = 'Menandai kartu yang masih tercatat aktif tetapi sudah lewat tanggal sebagai kedaluwarsa.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Hitung dan daftarkan saja, tidak mengubah basis data.')

    def handle(self, *args, **options):
        tertutup = KartuDigital.lewat_tempo()
        jumlah = tertutup.count()
        if options['dry_run']:
            self.stdout.write(f'{jumlah} kartu akan ditandai kedaluwarsa (dry-run, tidak ada yang diubah).')
            for kartu in tertutup.select_related('penduduk')[:20]:
                self.stdout.write(f'  {kartu.kode} — {kartu.penduduk.nama} — berlaku sampai {kartu.berlaku_sampai}')
            return
        diubah = tertutup.update(status='expired')
        self.stdout.write(self.style.SUCCESS(f'{diubah} kartu ditandai kedaluwarsa.'))
