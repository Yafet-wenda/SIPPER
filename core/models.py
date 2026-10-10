from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Penduduk(models.Model):
    STATUS = [('aktif', 'Aktif'), ('pindah', 'Pindah'), ('nonaktif', 'Nonaktif')]
    TUJUAN = [
        ('pendidikan', 'Pendidikan'),
        ('pekerjaan', 'Pekerjaan'),
        ('usaha', 'Pengembangan usaha'),
        ('keluarga', 'Kepentingan keluarga'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='penduduk', verbose_name='akun pengguna')
    nama = models.CharField(max_length=150, verbose_name='nama')
    nik = models.CharField(max_length=16, unique=True, validators=[RegexValidator(r'^\d{16}$', 'NIK harus 16 digit angka.')], verbose_name='NIK')
    daerah_asal = models.CharField(max_length=100, verbose_name='daerah asal')
    kota_tujuan = models.CharField(max_length=100, verbose_name='kota tujuan')
    tujuan = models.CharField(max_length=50, choices=TUJUAN, verbose_name='tujuan berpindah')
    nomor_telepon = models.CharField(max_length=15, blank=True, validators=[RegexValidator(r'^\d{10,15}$', 'Nomor telepon harus 10-15 digit.')], verbose_name='nomor telepon')
    tanggal_mulai = models.DateField(null=True, blank=True, verbose_name='tanggal mulai')
    perkiraan_kembali = models.DateField(null=True, blank=True, verbose_name='perkiraan kembali')
    status = models.CharField(max_length=20, choices=STATUS, default='aktif', verbose_name='status')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='terdaftar pada')

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name = 'penduduk'
        verbose_name_plural = 'penduduk'


class Pengajuan(models.Model):
    STATUS = [('menunggu', 'Menunggu'), ('disetujui', 'Disetujui'), ('ditolak', 'Ditolak'), ('perlu_perbaikan', 'Perlu perbaikan')]
    penduduk = models.OneToOneField(Penduduk, on_delete=models.CASCADE, related_name='pengajuan', verbose_name='penduduk')
    status = models.CharField(max_length=20, choices=STATUS, default='menunggu', verbose_name='status')
    catatan = models.TextField(blank=True, verbose_name='catatan petugas')
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name='dikirim pada')
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_applications', verbose_name='diverifikasi oleh')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='diverifikasi pada')

    def __str__(self):
        return f'{self.penduduk.nama} - {self.get_status_display()}'

    class Meta:
        verbose_name = 'pengajuan'
        verbose_name_plural = 'pengajuan'


class KartuDigital(models.Model):
    STATUS = [('aktif', 'Aktif'), ('expired', 'Kedaluwarsa'), ('nonaktif', 'Nonaktif')]
    penduduk = models.OneToOneField(Penduduk, on_delete=models.CASCADE, related_name='kartu', verbose_name='penduduk')
    kode = models.CharField(max_length=32, unique=True, verbose_name='kode kartu')
    berlaku_sampai = models.DateField(verbose_name='berlaku sampai')
    status = models.CharField(max_length=20, choices=STATUS, default='aktif', verbose_name='status')
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, verbose_name='QR code')

    def is_valid(self):
        return self.status == 'aktif' and self.berlaku_sampai >= timezone.now().date()

    class Meta:
        verbose_name = 'kartu digital'
        verbose_name_plural = 'kartu digital'


class Dokumen(models.Model):
    STATUS = [('pending', 'Menunggu'), ('valid', 'Valid'), ('invalid', 'Tidak valid')]
    JENIS = [('ktp', 'KTP'), ('kk', 'Kartu Keluarga'), ('surat_tugas', 'Surat Tugas'), ('lainnya', 'Lainnya')]
    penduduk = models.ForeignKey(Penduduk, on_delete=models.CASCADE, related_name='dokumen', verbose_name='penduduk')
    nama = models.CharField(max_length=100, verbose_name='nama berkas')
    jenis = models.CharField(max_length=30, choices=JENIS, default='lainnya', verbose_name='jenis dokumen')
    file = models.FileField(upload_to='dokumen/%Y/%m/', validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])], verbose_name='berkas')
    ukuran = models.PositiveIntegerField(default=0, verbose_name='ukuran')
    status = models.CharField(max_length=20, choices=STATUS, default='pending', verbose_name='status')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='diunggah pada')
    
    # Field untuk hasil OCR dan verifikasi AI
    ocr_text = models.TextField(blank=True, null=True, verbose_name='teks hasil OCR')
    ocr_confidence = models.FloatField(null=True, blank=True, verbose_name='confidence OCR')
    extracted_nik = models.CharField(max_length=16, blank=True, null=True, verbose_name='NIK dari OCR')
    extracted_data = models.JSONField(default=dict, blank=True, verbose_name='data terstruktur dari OCR')
    ai_verified = models.BooleanField(default=False, verbose_name='diverifikasi AI')
    ai_verification_notes = models.TextField(blank=True, verbose_name='catatan verifikasi AI')
    ocr_processed_at = models.DateTimeField(null=True, blank=True, verbose_name='diproses OCR pada')

    class Meta:
        verbose_name = 'dokumen'
        verbose_name_plural = 'dokumen'


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='pelaku')
    aksi = models.CharField(max_length=100, verbose_name='aksi')
    deskripsi = models.TextField(verbose_name='deskripsi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='waktu')

    class Meta:
        verbose_name = 'log audit'
        verbose_name_plural = 'log audit'


class Pemutakhiran(models.Model):
    penduduk = models.ForeignKey(Penduduk, on_delete=models.CASCADE, related_name='riwayat_pemutakhiran', verbose_name='penduduk')
    data_lama = models.JSONField(default=dict, verbose_name='data lama')
    data_baru = models.JSONField(default=dict, verbose_name='data baru')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='waktu')

    class Meta:
        verbose_name = 'riwayat pemutakhiran'
        verbose_name_plural = 'riwayat pemutakhiran'


class UserRole(models.Model):
    ROLE_CHOICES = [('masyarakat', 'Masyarakat'), ('petugas', 'Petugas Pemerintah')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='role_profile', verbose_name='pengguna')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='masyarakat', verbose_name='peran')

    class Meta:
        verbose_name = 'peran pengguna'
        verbose_name_plural = 'peran pengguna'

    def is_officer(self):
        return self.role == 'petugas' or self.user.is_staff
