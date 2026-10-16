"""Kolom prapemilahan AI (skor + keputusan ambang 85%) dan isian untuk berkas lama.

Laporan menjanjikan status pre-screened "Valid" / "Perlu Review Manual Petugas",
tetapi sampai migrasi ini hasil OCR hanya disimpan sebagai teks mentah sehingga
petugas tidak bisa menyaring antrean berdasar kecocokan.

Data backfill di bawah menghitung ulang skor dari fields yang sudah tersimpan
(ocr_confidence + extracted_data + data formulir warga) tanpa menjalankan
Tesseract, jadi berkas yang sudah pernah di-OCR sebelum kolom ini ada tetap
muncul di panel review dan tidak perlu diunggah ulang.
"""

from django.db import migrations, models


def isi_prapemilahan(apps, schema_editor):
    from core.ai_verifikasi import nilai_berkas

    Dokumen = apps.get_model('core', 'Dokumen')
    for berkas in Dokumen.objects.select_related('penduduk').iterator():
        if berkas.jenis != 'ktp' or not berkas.ocr_text:
            continue
        hasil = nilai_berkas(
            berkas.penduduk, berkas.extracted_data, berkas.ocr_confidence, berkas.jenis,
        )
        berkas.ai_score = hasil['skor']
        berkas.ai_prescreen = hasil['prescreen']
        berkas.ai_verified = hasil['prescreen'] == 'valid'
        berkas.ai_verification_notes = hasil['catatan']
        berkas.save(update_fields=[
            'ai_score', 'ai_prescreen', 'ai_verified', 'ai_verification_notes',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_penduduk_foto'),
    ]

    operations = [
        migrations.AddField(
            model_name='dokumen',
            name='ai_score',
            field=models.FloatField(blank=True, null=True, verbose_name='skor kecocokan AI'),
        ),
        migrations.AddField(
            model_name='dokumen',
            name='ai_prescreen',
            field=models.CharField(
                choices=[
                    ('valid', 'Valid (prapemilahan AI)'),
                    ('review', 'Perlu review manual petugas'),
                    ('belum_dinilai', 'Belum dinilai AI'),
                ],
                default='belum_dinilai',
                max_length=14,
                verbose_name='hasil prapemilahan AI',
            ),
        ),
        migrations.RunPython(isi_prapemilahan, migrations.RunPython.noop),
    ]
