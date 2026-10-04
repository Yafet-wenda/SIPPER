from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.urls import path, reverse
from django.db.models import Count
from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan, Pemutakhiran, UserRole


class SipperAdminSite(admin.AdminSite):
    site_header = 'SIPPER Administration'
    site_title = 'SIPPER Admin'
    index_title = 'Pusat kendali layanan'
    index_template = 'admin/sipper_index_v3.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [path('live-stats/', self.admin_view(self.live_stats), name='live_stats')]
        return custom + urls

    def live_stats(self, request):
        return JsonResponse(self.dashboard_data(request.user))

    @staticmethod
    def dashboard_data(user):
        """Semua angka dashboard, dihitung dari database pada saat dipanggil.

        Agregat boleh dilihat semua petugas, tetapi nama warga dan isi log audit
        hanya diberikan kepada pengguna yang punya izin lihat modelnya — sama
        seperti halaman depan admin yang hanya menampilkan model terizinkan.
        """
        from datetime import timedelta

        from django.utils import timezone

        boleh_pengajuan = user.has_perm('core.view_pengajuan')
        boleh_audit = user.has_perm('core.view_auditlog')
        today = timezone.localdate()
        # Pengelompokan per hari dilakukan di Python, bukan lewat lookup __date.
        # Lookup tanggal pada MySQL/MariaDB memakai CONVERT_TZ yang butuh tabel
        # zona waktu server; di MariaDB XAMPP mesin ini tabel itu tidak terisi,
        # jadi hasilnya senyap bernilai NULL (angka hari tampak 0).
        awal_jendela = timezone.localtime().replace(
            hour=0, minute=0, second=0, microsecond=0) - timedelta(days=13)
        deret = {
            (today - timedelta(days=offset)).isoformat(): {'masuk': 0, 'selesai': 0}
            for offset in range(13, -1, -1)
        }
        for row in (Pengajuan.objects.filter(submitted_at__gte=awal_jendela)
                    .values_list('submitted_at', flat=True)):
            kunci = timezone.localtime(row).date().isoformat()
            if kunci in deret:
                deret[kunci]['masuk'] += 1
        for row in (Pengajuan.objects.filter(verified_at__isnull=False,
                                             verified_at__gte=awal_jendela)
                    .values_list('verified_at', flat=True)):
            kunci = timezone.localtime(row).date().isoformat()
            if kunci in deret:
                deret[kunci]['selesai'] += 1
        deret_hari = [
            {'tanggal': tanggal, **isi} for tanggal, isi in sorted(deret.items())
        ]
        masuk_hari_ini = deret[today.isoformat()]['masuk']

        status = dict(
            Pengajuan.objects.values_list('status').annotate(n=Count('pk'))
        )
        kartu_berlaku = KartuDigital.objects.filter(status='aktif', berlaku_sampai__gte=today).count()
        queue = (
            Pengajuan.objects.filter(status__in=['menunggu', 'perlu_perbaikan'])
            .select_related('penduduk').order_by('submitted_at')[:8]
            if boleh_pengajuan else []
        )
        logs = (
            AuditLog.objects.select_related('user').order_by('-created_at')[:12]
            if boleh_audit else []
        )

        # Rata-rata durasi verifikasi diambil dari 200 berkas terakhir yang sudah
        # selesai supaya biayanya tetap terbatas, bukan seluruh tabel.
        selesai_list = (
            Pengajuan.objects.filter(status='disetujui', verified_at__isnull=False)
            .order_by('-verified_at').values_list('submitted_at', 'verified_at')[:200]
        )
        rerata_jam = None
        if selesai_list:
            jam = [(b - a).total_seconds() / 3600 for a, b in selesai_list if b and a and b >= a]
            if jam:
                rerata_jam = round(sum(jam) / len(jam), 1)

        return {
            'server_time': timezone.localtime().isoformat(),
            'deret_hari': deret_hari,
            'hari_ini': masuk_hari_ini,
            'status': {
                'menunggu': status.get('menunggu', 0),
                'disetujui': status.get('disetujui', 0),
                'ditolak': status.get('ditolak', 0),
                'perlu_perbaikan': status.get('perlu_perbaikan', 0),
            },
            'total_pengajuan': sum(status.values()),
            'warga': Penduduk.objects.count(),
            'dokumen_pending': Dokumen.objects.filter(status='pending').count(),
            'dokumen_total': Dokumen.objects.count(),
            'kartu_berlaku': kartu_berlaku,
            'kartu_habis': KartuDigital.objects.count() - kartu_berlaku,
            'rerata_jam': rerata_jam,
            'antrean': [
                {
                    'pk': p.pk,
                    'nama': p.penduduk.nama,
                    'kota': p.penduduk.kota_tujuan,
                    'status': p.status,
                    'submitted_at': p.submitted_at.isoformat(),
                }
                for p in queue
            ],
            'aktivitas': [
                {
                    'aksi': log.aksi,
                    'deskripsi': log.deskripsi,
                    'user': (log.user.get_full_name() or log.user.username) if log.user else '-',
                    'created_at': log.created_at.isoformat(),
                }
                for log in logs
            ],
        }

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['live_stats'] = self.dashboard_data(request.user)
        return super().index(request, extra_context)



sipper_admin = SipperAdminSite(name='sipper_admin')


def approve_selected(modeladmin, request, queryset):
    updated = queryset.update(status='disetujui', verified_by=request.user)
    modeladmin.message_user(request, f'{updated} pengajuan disetujui.')
approve_selected.short_description = 'Setujui pengajuan terpilih'


def reject_selected(modeladmin, request, queryset):
    updated = queryset.update(status='ditolak', verified_by=request.user)
    modeladmin.message_user(request, f'{updated} pengajuan ditolak.')
reject_selected.short_description = 'Tolak pengajuan terpilih'


def mark_documents_valid(modeladmin, request, queryset):
    updated = queryset.update(status='valid')
    modeladmin.message_user(request, f'{updated} dokumen ditandai valid.')
mark_documents_valid.short_description = 'Tandai dokumen valid'


class RentangWaktuFilter(admin.SimpleListFilter):
    """Menyaring kolom waktu memakai rentang datetime, bukan lookup __date/__year.

    Lookup tanggal pada MySQL/MariaDB diterjemahkan menjadi CONVERT_TZ yang
    membutuhkan tabel zoneinfo di server. MariaDB XAMPP mesin ini tidak punya
    tabel itu (terukur: CONVERT_TZ(..., 'UTC', 'Asia/Jakarta') = NULL), sehingga
    filter tanggal bawaan Django membuat halaman changelist gagal. Perbandingan
    datetime biasa tidak menyentuh CONVERT_TZ dan batas harinya tetap dihitung
    dalam zona waktu lokal.
    """

    title = 'Waktu'
    parameter_name = ''
    lookup = ''
    OPSI = (
        ('hari-ini', 'Hari ini', 0),
        ('7-hari', '7 hari terakhir', 7),
        ('30-hari', '30 hari terakhir', 30),
        ('90-hari', '90 hari terakhir', 90),
    )

    def awal(self, nilai):
        from django.utils import timezone

        tengah_hari = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        for kunci, _, mundur in self.OPSI:
            if kunci == nilai:
                return tengah_hari - timedelta(days=mundur)
        return None

    def lookups(self, request, model_admin):
        return [(kunci, label) for kunci, label, _ in self.OPSI]

    def choices(self, changelist):
        yield {
            'selected': self.value() is None,
            'query_string': changelist.get_query_string(remove=[self.parameter_name]),
            'display': 'Semua',
        }
        for kunci, label, _ in self.OPSI:
            yield {
                'selected': self.value() == kunci,
                'query_string': changelist.get_query_string({self.parameter_name: kunci}),
                'display': label,
            }

    def queryset(self, request, queryset):
        batas = self.awal(self.value())
        if batas is None:
            return queryset
        return queryset.filter(**{f'{self.lookup}__gte': batas})


class PengajuanMasukFilter(RentangWaktuFilter):
    title = 'Waktu pengajuan'
    parameter_name = 'masuk'
    lookup = 'submitted_at'


class DokumenMasukFilter(RentangWaktuFilter):
    title = 'Waktu unggah'
    parameter_name = 'unggah'
    lookup = 'uploaded_at'


class AuditWaktuFilter(RentangWaktuFilter):
    title = 'Waktu aktivitas'
    parameter_name = 'waktu'
    lookup = 'created_at'


class PendudukWaktuFilter(RentangWaktuFilter):
    title = 'Waktu terdaftar'
    parameter_name = 'daftar'
    lookup = 'created_at'


@admin.register(Penduduk, site=sipper_admin)
class PendudukAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nik', 'daerah_asal', 'kota_tujuan', 'tujuan', 'status', 'created_at')
    list_filter = ('status', 'tujuan', 'kota_tujuan', PendudukWaktuFilter)
    search_fields = ('nama', 'nik', 'daerah_asal', 'kota_tujuan', 'user__email')
    list_per_page = 25
    readonly_fields = ('created_at',)


@admin.register(Pengajuan, site=sipper_admin)
class PengajuanAdmin(admin.ModelAdmin):
    list_display = ('penduduk', 'status_badge', 'submitted_at', 'verified_by', 'verified_at')
    list_filter = ('status', 'penduduk__kota_tujuan', PengajuanMasukFilter)
    search_fields = ('penduduk__nama', 'penduduk__nik', 'catatan')
    autocomplete_fields = ('penduduk', 'verified_by')
    list_per_page = 25
    actions = (approve_selected, reject_selected)
    readonly_fields = ('submitted_at',)

    @admin.display(description='Status', ordering='status', boolean=False)
    def status_badge(self, obj):
        return format_html('<span class="sip-status sip-status--{}">{}</span>', obj.status, obj.get_status_display())


@admin.register(Dokumen, site=sipper_admin)
class DokumenAdmin(admin.ModelAdmin):
    list_display = ('nama', 'penduduk', 'jenis', 'status', 'ukuran', 'uploaded_at', 'file_link')
    list_filter = ('status', 'jenis', DokumenMasukFilter)
    search_fields = ('nama', 'penduduk__nama', 'penduduk__nik')
    list_per_page = 25
    actions = (mark_documents_valid,)
    readonly_fields = ('uploaded_at', 'ukuran', 'file_link')

    @admin.display(description='File')
    def file_link(self, obj):
        if not obj.file:
            return '-'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Buka</a>',
            reverse('core:document_file', args=[obj.pk]),
        )


@admin.register(KartuDigital, site=sipper_admin)
class KartuDigitalAdmin(admin.ModelAdmin):
    list_display = ('penduduk', 'kode', 'status', 'berlaku_sampai', 'is_current')
    list_filter = ('status', 'berlaku_sampai')
    search_fields = ('kode', 'penduduk__nama', 'penduduk__nik')
    readonly_fields = ('kode', 'qr_code')

    @admin.display(boolean=True, description='Valid saat ini')
    def is_current(self, obj):
        return obj.is_valid()


@admin.register(Pemutakhiran, site=sipper_admin)
class PemutakhiranAdmin(admin.ModelAdmin):
    list_display = ('penduduk', 'created_at', 'old_destination', 'new_destination')
    search_fields = ('penduduk__nama', 'penduduk__nik')
    readonly_fields = ('penduduk', 'data_lama', 'data_baru', 'created_at')

    @admin.display(description='Tujuan lama')
    def old_destination(self, obj):
        return obj.data_lama.get('kota_tujuan', '-')

    @admin.display(description='Tujuan baru')
    def new_destination(self, obj):
        return obj.data_baru.get('kota_tujuan', '-')


@admin.register(AuditLog, site=sipper_admin)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'aksi', 'deskripsi')
    list_filter = ('aksi', AuditWaktuFilter)
    search_fields = ('user__username', 'aksi', 'deskripsi')
    readonly_fields = ('user', 'aksi', 'deskripsi', 'created_at')


@admin.register(UserRole, site=sipper_admin)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_officer')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email', 'user__first_name')

    @admin.display(boolean=True, description='Akses petugas')
    def is_officer(self, obj):
        return obj.is_officer()


sipper_admin.register(User)
sipper_admin.unregister(User)
sipper_admin.register(User, UserAdmin)
sipper_admin.register(Group, GroupAdmin)
