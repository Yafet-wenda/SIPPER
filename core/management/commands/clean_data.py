"""Management command untuk membersihkan data percobaan."""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Penduduk, Pengajuan, Dokumen, KartuDigital, AuditLog, Pemutakhiran, UserRole


class Command(BaseCommand):
    help = 'Membersihkan data percobaan kecuali admin wendayafet@gmail.com'

    def handle(self, *args, **options):
        admin_email = 'wendayafet@gmail.com'
        
        try:
            admin_user = User.objects.get(email=admin_email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Admin {admin_email} tidak ditemukan!'))
            return
        
        self.stdout.write(f'✓ Admin: {admin_user.username}')
        
        # Hitung sebelum
        stats_before = {
            'users': User.objects.count(),
            'penduduk': Penduduk.objects.count(),
            'pengajuan': Pengajuan.objects.count(),
            'dokumen': Dokumen.objects.count(),
        }
        
        self.stdout.write('\n📊 SEBELUM cleanup:')
        for k, v in stats_before.items():
            self.stdout.write(f'  {k}: {v}')
        
        # Hapus data
        AuditLog.objects.exclude(user=admin_user).delete()
        Pemutakhiran.objects.exclude(penduduk__user=admin_user).delete()
        KartuDigital.objects.exclude(penduduk__user=admin_user).delete()
        Dokumen.objects.exclude(penduduk__user=admin_user).delete()
        Pengajuan.objects.exclude(penduduk__user=admin_user).delete()
        Penduduk.objects.exclude(user=admin_user).delete()
        UserRole.objects.exclude(user=admin_user).delete()
        User.objects.exclude(id=admin_user.id).exclude(is_superuser=True).delete()
        
        # Hitung setelah
        stats_after = {
            'users': User.objects.count(),
            'penduduk': Penduduk.objects.count(),
            'pengajuan': Pengajuan.objects.count(),
            'dokumen': Dokumen.objects.count(),
        }
        
        self.stdout.write('\n📊 SETELAH cleanup:')
        for k, v in stats_after.items():
            self.stdout.write(f'  {k}: {v}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Cleanup selesai!'))
