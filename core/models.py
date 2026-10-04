from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Penduduk(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='penduduk')
    nama = models.CharField(max_length=150)
    nik = models.CharField(max_length=16, unique=True, validators=[RegexValidator(r'^\d{16}$', 'NIK harus 16 digit angka.')])
    daerah_asal = models.CharField(max_length=100)
    kota_tujuan = models.CharField(max_length=100)
    tujuan = models.CharField(max_length=50)
    nomor_telepon = models.CharField(max_length=15, blank=True, validators=[RegexValidator(r'^\d{10,15}$', 'Nomor telepon harus 10-15 digit.')])
    tanggal_mulai = models.DateField(null=True, blank=True)
    perkiraan_kembali = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='aktif')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nama


class Pengajuan(models.Model):
    STATUS = [('menunggu', 'Menunggu'), ('disetujui', 'Disetujui'), ('ditolak', 'Ditolak'), ('perlu_perbaikan', 'Perlu perbaikan')]
    penduduk = models.OneToOneField(Penduduk, on_delete=models.CASCADE, related_name='pengajuan')
    status = models.CharField(max_length=20, choices=STATUS, default='menunggu')
    catatan = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_applications')
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.penduduk.nama} - {self.get_status_display()}'


class KartuDigital(models.Model):
    penduduk = models.OneToOneField(Penduduk, on_delete=models.CASCADE, related_name='kartu')
    kode = models.CharField(max_length=32, unique=True)
    berlaku_sampai = models.DateField()
    status = models.CharField(max_length=20, default='aktif')
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)

    def is_valid(self):
        return self.status == 'aktif' and self.berlaku_sampai >= timezone.now().date()


class Dokumen(models.Model):
    STATUS = [('pending', 'Menunggu'), ('valid', 'Valid'), ('invalid', 'Tidak valid')]
    penduduk = models.ForeignKey(Penduduk, on_delete=models.CASCADE, related_name='dokumen')
    nama = models.CharField(max_length=100)
    jenis = models.CharField(max_length=30, default='lainnya')
    file = models.FileField(upload_to='dokumen/%Y/%m/', validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])])
    ukuran = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    aksi = models.CharField(max_length=100)
    deskripsi = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Pemutakhiran(models.Model):
    penduduk = models.ForeignKey(Penduduk, on_delete=models.CASCADE, related_name='riwayat_pemutakhiran')
    data_lama = models.JSONField(default=dict)
    data_baru = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class UserRole(models.Model):
    ROLE_CHOICES = [('masyarakat', 'Masyarakat'), ('petugas', 'Petugas Pemerintah')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='masyarakat')

    def is_officer(self):
        return self.role == 'petugas' or self.user.is_staff
