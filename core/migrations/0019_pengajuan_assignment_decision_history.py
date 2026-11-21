import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0018_dokumen_ocr_provider'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='pengajuan',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_applications',
                to=settings.AUTH_USER_MODEL,
                verbose_name='ditugaskan kepada',
            ),
        ),
        migrations.CreateModel(
            name='RiwayatKeputusan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('menunggu', 'Menunggu'), ('disetujui', 'Disetujui'), ('ditolak', 'Ditolak'), ('perlu_perbaikan', 'Perlu perbaikan')], max_length=20, verbose_name='status')),
                ('catatan', models.TextField(blank=True, verbose_name='catatan')),
                ('actor_role', models.CharField(default='petugas', max_length=30, verbose_name='peran pelaku')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='waktu keputusan')),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='decision_history', to=settings.AUTH_USER_MODEL, verbose_name='pelaku')),
                ('pengajuan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='riwayat_keputusan', to='core.pengajuan', verbose_name='pengajuan')),
            ],
            options={
                'verbose_name': 'riwayat keputusan',
                'verbose_name_plural': 'riwayat keputusan',
                'ordering': ('-created_at',),
            },
        ),
    ]
