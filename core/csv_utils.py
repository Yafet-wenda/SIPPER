"""Penulisan nilai ke CSV: jam dalam WIB dan sel aman untuk spreadsheet."""
from datetime import date, datetime

from django.utils import timezone

RUMUS_CSV = ('=', '+', '-', '@', '\t', '\r')
FORMAT_WIB = '%Y-%m-%d %H:%M:%S WIB'


def waktu_wib(nilai):
    """Waktu → teks jam WIB, karena CSV dibaca manusia, bukan mesin.

    Kolom DateTimeField menyimpan UTC, sehingga `isoformat()` menampilkan angka
    tujuh jam lebih awal daripada jam dinding petugas yang membuka laporan.
    Tanggal murni (mis. berlaku_sampai kartu) tidak punya zona, jadi tetap
    ditulis YYYY-MM-DD.
    """
    if isinstance(nilai, datetime):
        if timezone.is_naive(nilai):
            nilai = timezone.make_aware(nilai, timezone.get_current_timezone())
        return timezone.localtime(nilai).strftime(FORMAT_WIB)
    if isinstance(nilai, date):
        return nilai.isoformat()
    return '' if nilai is None else str(nilai)


def sel_aman(nilai):
    """Netralisasi sel yang bisa dibaca aplikasi spreadsheet sebagai rumus.

    Petugas membuka laporan CSV di Excel atau Sheets. Isian yang diketik warga
    (nama kota, alasan, catatan) dan diawali '=' / '+' / '@' akan dieksekusi
    sebagai formula, bukan ditampilkan sebagai teks, sehingga pengajuan bisa
    dipakai untuk menyerang mesin petugas. Apostrof di depan menghentikan
    parsing rumus dan tetap terbaca manusia.
    """
    teks = '' if nilai is None else str(nilai)
    return "'" + teks if teks[:1] in RUMUS_CSV else teks
