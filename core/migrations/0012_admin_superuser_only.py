"""Cabut akses lama: petugas tidak lagi memakai is_staff maupun grup izin.

Petugas dikenali lewat core.models.UserRole (role='petugas'), bukan lewat
is_staff atau grup auth. Migrasi ini menurunkan is_staff pada akun non-superuser
yang tersisa dan menghapus grup warisan 'Petugas SIPPER' agar tidak ada jalan
masuk ganda. Pada basis data baru tidak ada pengguna saat migrasi ini berjalan,
jadi operasinya berupa no-op.
"""
from django.db import migrations


def cabut_staf_dan_hapus_grup(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Group = apps.get_model('auth', 'Group')
    User.objects.filter(is_staff=True, is_superuser=False).update(is_staff=False)
    Group.objects.filter(name='Petugas SIPPER').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0011_alter_kartudigital_status_alter_penduduk_status'),
    ]

    operations = [
        migrations.RunPython(cabut_staf_dan_hapus_grup, migrations.RunPython.noop),
    ]
