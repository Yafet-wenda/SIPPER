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
        return JsonResponse({
            'pending': Pengajuan.objects.filter(status='menunggu').count(),
            'approved': Pengajuan.objects.filter(status='disetujui').count(),
            'rejected': Pengajuan.objects.filter(status='ditolak').count(),
            'citizens': Penduduk.objects.count(),
            'documents': Dokumen.objects.filter(status='pending').count(),
        })

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'live_stats': self.live_stats_data(),
            'recent_applications': Pengajuan.objects.select_related('penduduk').order_by('-submitted_at')[:8],
            'recent_logs': AuditLog.objects.select_related('user').order_by('-created_at')[:8],
        })
        return super().index(request, extra_context)

    @staticmethod
    def live_stats_data():
        return {
            'pending': Pengajuan.objects.filter(status='menunggu').count(),
            'approved': Pengajuan.objects.filter(status='disetujui').count(),
            'rejected': Pengajuan.objects.filter(status='ditolak').count(),
            'citizens': Penduduk.objects.count(),
            'documents': Dokumen.objects.filter(status='pending').count(),
        }


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


@admin.register(Penduduk, site=sipper_admin)
class PendudukAdmin(admin.ModelAdmin):
    list_display = ('nama', 'nik', 'daerah_asal', 'kota_tujuan', 'tujuan', 'status', 'created_at')
    list_filter = ('status', 'tujuan', 'kota_tujuan', 'created_at')
    search_fields = ('nama', 'nik', 'daerah_asal', 'kota_tujuan', 'user__email')
    date_hierarchy = 'created_at'
    list_per_page = 25
    readonly_fields = ('created_at',)


@admin.register(Pengajuan, site=sipper_admin)
class PengajuanAdmin(admin.ModelAdmin):
    list_display = ('penduduk', 'status', 'submitted_at', 'verified_by', 'verified_at')
    list_filter = ('status', 'submitted_at', 'verified_at')
    search_fields = ('penduduk__nama', 'penduduk__nik', 'catatan')
    autocomplete_fields = ('penduduk', 'verified_by')
    date_hierarchy = 'submitted_at'
    list_per_page = 25
    actions = (approve_selected, reject_selected)
    readonly_fields = ('submitted_at',)


@admin.register(Dokumen, site=sipper_admin)
class DokumenAdmin(admin.ModelAdmin):
    list_display = ('nama', 'penduduk', 'jenis', 'status', 'ukuran', 'uploaded_at', 'file_link')
    list_filter = ('status', 'jenis', 'uploaded_at')
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
    date_hierarchy = 'created_at'
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
    list_filter = ('aksi', 'created_at')
    search_fields = ('user__username', 'aksi', 'deskripsi')
    date_hierarchy = 'created_at'
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
