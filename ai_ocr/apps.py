from django.apps import AppConfig


class AiOcrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_ocr'
    # Nama blok di halaman utama admin. Django mengelompokkan model per aplikasi,
    # jadi supaya "AI OCR" muncul sebagai modul tersendiri — sejajar dengan
    # "Inti layanan" dan "Autentikasi dan Otorisasi" — prapemilahan punya
    # aplikasinya sendiri, bukan menumpang label di aplikasi core.
    verbose_name = 'AI OCR'
