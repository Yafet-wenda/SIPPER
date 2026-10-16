"""Model proxy TinjauanOcr.

Proxy tidak menambah kolom maupun tabel: operasinya no-op secara SQL. Yang
didaftarkan hanya content type dan izinnya, supaya modul "AI OCR" bisa muncul
sebagai blok tersendiri di halaman utama admin dan petugas dapat diberi izin
meninjau hasil mesin tanpa diberi akses mengubah berkas.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_dokumen_ai_prescreen'),
    ]

    operations = [
        migrations.CreateModel(
            name='TinjauanOcr',
            fields=[],
            options={
                'verbose_name': 'Tinjauan berkas',
                'verbose_name_plural': 'Tinjauan berkas',
                'proxy': True,
                'ordering': ('-ai_score', 'id'),
                'indexes': [],
                'constraints': [],
            },
            bases=('core.dokumen',),
        ),
    ]
