from django.db import models

from core.models import Dokumen


class TinjauanOcr(Dokumen):
    """Jendela review hasil AI OCR atas berkas yang sama.

    Proxy model: tidak ada tabel baru dan tidak ada duplikasi data — baris yang
    dibuka di sini adalah baris core_dokumen yang sama. Yang membuat hasil OCR
    bisa menjadi blok "AI OCR" tersendiri di halaman utama admin (sejajar dengan
    "Autentikasi dan Otorisasi") justru keberadaan model sendiri ini, karena
    Django mengelompokkan daftar model per aplikasi, bukan per fieldset.
    """

    class Meta:
        proxy = True
        verbose_name = 'Tinjauan berkas'
        verbose_name_plural = 'Tinjauan berkas'
        # Skor tertinggi lebih dulu. Pada DESC, MySQL/MariaDB dan SQLite sama-sama
        # menaruh NULL di belakang, jadi berkas yang belum dinilai mesin tidak
        # ikut memenuhi layar pertama petugas.
        ordering = ('-ai_score', 'id')
