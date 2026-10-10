"""Penulisan nilai ke CSV supaya tidak dibaca spreadsheet sebagai rumus."""

RUMUS_CSV = ('=', '+', '-', '@', '\t', '\r')


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
