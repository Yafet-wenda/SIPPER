"""Panel review AI OCR di halaman admin.

Isi modul ini hanya "jendela": datanya tetap baris core_dokumen yang sama
(lihat ai_ocr/models.py). Yang ditambahkan adalah cara kerja sesuai paparan
laporan bagian "Validasi agentik AI" — daftar berkas berdasar skor kecocokan,
tabel perbandingan isian formulir vs hasil OCR, antarmuka koreksi manual, dan
tombol proses ulang — tanpa satu pun jalur yang mengubah status dokumen secara
otomatis.
"""

from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.timezone import localtime

from core.admin_site import EksporCSVMixin, RentangWaktuFilter, sipper_admin
from core.csv_utils import waktu_wib
from core.ai_verifikasi import AMBAT_VALID, JENIS_BERNILAI, baris_perbandingan, nilai_berkas
from core.models import AuditLog
from core.ocr_worker import picu_async

from .models import TinjauanOcr


class ProsesWaktuFilter(RentangWaktuFilter):
    """Sama seperti filter waktu lain: bandingkan datetime, jangan __date.

    Lookup tanggal pada MariaDB XAMPP butuh tabel zoneinfo server yang tidak
    terisi, sehingga CONVERT_TZ menghasilkan NULL (lihat RentangWaktuFilter).
    """

    title = 'Waktu diproses'
    parameter_name = 'diproses'
    lookup = 'ocr_processed_at'


def proses_ulang_ocr(modeladmin, request, queryset):
    """Kirim ulang berkas terpilih ke mesin OCR, di latar belakang.

    Dipakai kalau petugas memperbaiki kualitas foto atau parser baru terpasang:
    hasil lama ditimpa oleh hasil mesin, bukan oleh tebakan kita di sini.
    """
    jumlah = 0
    for berkas in queryset:
        if not berkas.file:
            continue
        picu_async(berkas.pk)
        jumlah += 1
    modeladmin.message_user(
        request,
        f'{jumlah} berkas dikirim ke mesin OCR. Hasilnya muncul beberapa detik '
        f'lagi — muat ulang daftar ini untuk melihat skor terbaru.',
    )
proses_ulang_ocr.short_description = 'Proses ulang OCR berkas terpilih'


def tandai_review_manual(modeladmin, request, queryset):
    """Kemasukkan antrean manual secara massal, tanpa menyentuh skor mesin."""
    pencatat = request.user.get_full_name() or request.user.username
    waktu = localtime().strftime('%d/%m/%Y %H:%M')
    updated = 0
    for berkas in queryset:
        catatan_lama = (berkas.ai_verification_notes or '').strip()
        berkas.ai_prescreen = 'review'
        berkas.ai_verified = False
        berkas.ai_verification_notes = ' '.join(filter(None, [
            f'Ditandai perlu review manual oleh {pencatat} pada {waktu}.',
            catatan_lama,
        ]))
        berkas.save(update_fields=['ai_prescreen', 'ai_verified', 'ai_verification_notes'])
        updated += 1
    AuditLog.objects.create(
        user=request.user,
        aksi='ai_tandai_review',
        deskripsi=f'{updated} berkas ditandai perlu review manual.',
    )
    modeladmin.message_user(request, f'{updated} berkas ditandai perlu review manual petugas.')
tandai_review_manual.short_description = 'Tandai perlu review manual petugas'


class KoreksiOcrForm(forms.ModelForm):
    """Form koreksi manual: nilai OCR boleh dibetulkan petugas, hasil mesin tidak.

    ``extracted_nama`` dan ``extracted_nik`` adalah salinan dari isi
    ``extracted_data``. Keduanya disimpan di kolom terpisah karena dipakai
    API, laporan PDF, dan asisten; kalau petugas hanya membetulkan salah satu
    tanpa yang lain, panel dan laporan bisa menampilkan angka berbeda. Karena
    itu form ini menyatukan keduanya saat menyimpan.
    """

    extracted_nama = forms.CharField(
        label='Nama hasil OCR', required=False, max_length=150,
        help_text='Betulkan bila OCR salah baca. Skor dihitung ulang setelah disimpan.',
    )

    class Meta:
        model = TinjauanOcr
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.instance.extracted_data or {}
        self.fields['extracted_nama'].initial = data.get('nama', '')

    def save(self, commit=True):
        data = dict(self.instance.extracted_data or {})
        nama = (self.cleaned_data.get('extracted_nama') or '').strip()
        if nama:
            data['nama'] = nama
        else:
            data.pop('nama', None)
        nik = (self.cleaned_data.get('extracted_nik') or '').strip()
        if nik:
            data['nik'] = nik
        else:
            data.pop('nik', None)
        # Dict baru, bukan mutasi in-place: JSONField tidak mendeteksi perubahan
        # pada objek yang sama, jadi nilai hasil koreksi bisa hilang tanpa jejak.
        self.instance.extracted_data = data
        return super().save(commit)


@admin.register(TinjauanOcr, site=sipper_admin)
class TinjauanOcrAdmin(EksporCSVMixin, admin.ModelAdmin):
    form = KoreksiOcrForm
    change_list_template = 'admin/ai_ocr_changelist.html'
    # Kolom "Berkas" sengaja tidak ada di daftar: tautan bukanya sudah ada di
    # fieldset pertama form review, dan satu kolom itu yang membuat tabel
    # selebar layar sehingga antrean harus digeser ke samping.
    list_display = (
        'warga', 'nik_warga', 'jenis', 'skor_badge', 'prescreen_badge',
        'confidence', 'diproses_pada',
    )
    list_filter = ('ai_prescreen', 'jenis', ProsesWaktuFilter)
    search_fields = ('penduduk__nama', 'penduduk__nik', 'extracted_nik', 'nama')
    list_select_related = ('penduduk',)
    list_per_page = 25
    actions = (proses_ulang_ocr, tandai_review_manual)
    # Berkas masuk lewat unggahan warga atau form Dokumen, bukan dari panel ini;
    # dan menghapus lewat proxy akan menghapus baris dokumen yang sebenarnya.
    # Keduanya sengaja ditutup di sini.
    csv_columns = (
        ('Warga', lambda o: o.penduduk.nama),
        ('NIK formulir', lambda o: o.penduduk.nik),
        ('Jenis berkas', lambda o: o.get_jenis_display()),
        ('Skor kecocokan', lambda o: '' if o.ai_score is None else str(o.ai_score)),
        ('Prapemilahan', lambda o: o.get_ai_prescreen_display()),
        ('Confidence OCR', lambda o: '' if o.ocr_confidence is None else str(o.ocr_confidence)),
        ('NIK dari OCR', lambda o: o.extracted_nik or ''),
        ('Diproses pada (WIB)', lambda o: waktu_wib(o.ocr_processed_at)),
        ('Catatan', lambda o: o.ai_verification_notes or ''),
    )

    def get_fieldsets(self, request, obj=None):
        identitas = (None, {
            'fields': ('penduduk', 'nama', 'jenis', 'file_link', 'status'),
            'description': 'Berkas dan keputusan status dokumen dikelola di modul Dokumen / jalur petugas.',
        })
        perbandingan = ('Perbandingan isian formulir dengan hasil OCR', {
            'fields': ('tabel_perbandingan',),
            'description': (
                f'Skor kecocokan = NIK (45%) + Nama (30%) + keterbacaan OCR (25%). '
                f'Di atas {AMBAT_VALID:.0f}% berkas ditandai Valid; di bawah itu Perlu review manual.'
            ),
        })
        koreksi = ('Koreksi manual hasil OCR', {
            'fields': ('extracted_nik', 'extracted_nama', 'ai_verification_notes'),
            'description': (
                'Hanya bagian ini yang boleh diketik tangan. Menyimpan akan menghitung '
                'ulang skor dan hasil prapemilahan dari nilai yang baru.'
            ),
        })
        mesin = ('Keluaran mesin (hanya baca)', {
            # Sengaja tidak di-collapse: petugas membuka panel ini justru untuk
            # melihat isi berkas yang dibaca mesin. Kalau teksnya disembunyikan
            # di balik tautan "Tampilkan:", layar pertama terlihat kosong.
            'description': 'Teks mentah di bawah adalah hasil baca Tesseract atas berkas, dasar dari skor di atas.',
            'fields': ('teks_ocr', 'ocr_confidence', 'ai_score', 'ai_prescreen',
                       'ai_verified', 'ocr_processed_at'),
        })
        return (identitas, perbandingan, koreksi, mesin)

    readonly_fields = (
        'penduduk', 'nama', 'jenis', 'file_link', 'status',
        'teks_ocr', 'ocr_text', 'ocr_confidence', 'ai_score', 'ai_prescreen', 'ai_verified',
        'ocr_processed_at', 'tabel_perbandingan',
        # extracted_data tidak muncul di fieldset mana pun. Kalau dibiarkan ikut
        # form, Djangoanggap petugas mengosongkannya dan seluruh hasil bacaan
        # mesin (alamat, TTL, nomor KK) terhapus saat tombol simpan ditekan.
        'extracted_data',
    )

    def changelist_view(self, request, extra_context=None):
        """Ambang dikirim ke template, tidak ditulis ulang di HTML."""
        return super().changelist_view(request, {
            **(extra_context or {}),
            'ai_ambang': AMBAT_VALID,
        })

    @admin.display(description='Warga')
    def warga(self, obj):
        return obj.penduduk.nama

    @admin.display(description='NIK formulir', ordering='penduduk__nik')
    def nik_warga(self, obj):
        return obj.penduduk.nik

    @admin.display(description='Skor', ordering='ai_score')
    def skor_badge(self, obj):
        """Angka skor diwarnai menurut ambang laporan, bukan menurut selera."""
        if obj.ai_score is None:
            # Tanda pisau saja: kolom Prapemilahan sudah menulis "Belum dinilai",
            # mengulang frasa yang sama membuat tabel melebar tanpa informasi.
            return format_html('<span class="sip-ai sip-ai--kosong">—</span>')
        kelas = 'lolos' if obj.ai_score > AMBAT_VALID else 'rendah'
        return format_html('<span class="sip-ai sip-ai--{}">{}</span>', kelas, f'{obj.ai_score:.1f}%')

    @admin.display(description='Prapemilahan', ordering='ai_prescreen')
    def prescreen_badge(self, obj):
        return format_html(
            '<span class="sip-status sip-status--{}">{}</span>',
            obj.ai_prescreen, obj.get_ai_prescreen_display(),
        )

    @admin.display(description='Confidence', ordering='ocr_confidence')
    def confidence(self, obj):
        return '-' if obj.ocr_confidence is None else f'{obj.ocr_confidence:.1f}%'

    @admin.display(description='Diproses', ordering='ocr_processed_at')
    def diproses_pada(self, obj):
        """Tanpa tahun: antrean review berisi berkas harian, dan kolom penuh
        tahun membuat tabel harus digeser ke samping di layar 1440px."""
        return localtime(obj.ocr_processed_at).strftime('%d/%m %H:%M') if obj.ocr_processed_at else 'belum'

    @admin.display(description='Berkas')
    def berkas_link(self, obj):
        if not obj.file:
            return '-'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Buka</a>',
            reverse('core:document_file', args=[obj.pk]),
        )

    @admin.display(description='Buka berkas')
    def file_link(self, obj):
        return self.berkas_link(obj)

    @admin.display(description='Teks hasil OCR')
    def teks_ocr(self, obj):
        """Isi berkas yang benar-benar dibaca mesin, apa adanya.

        Teksnya datang dari hasil OCR atas unggahan warga, jadi ditulis lewat
        ``format_html`` (ter-escape) dan dibungkus kotak yang bisa digulir —
        bukan disisipkan sebagai HTML mentah.
        """
        if not obj or not obj.ocr_text:
            return (
                'Belum ada teks. Berkas ini belum diproses mesin, atau jenisnya '
                'tidak bisa dibaca OCR (mis. PDF). Centang berkas di daftar lalu '
                'pakai aksi "Proses ulang OCR" untuk mencoba lagi.'
            )
        return format_html('<div class="sip-ai-teks">{}</div>', obj.ocr_text)

    @admin.display(description='Perbandingan')
    def tabel_perbandingan(self, obj):
        """Tabel alasan skor, dihitung ulang dari data tersimpan.

        Tidak membaca kolom skor saja: petugas harus bisa melihat field mana
        yang membuat berkas turun di bawah ambang. Nilai berasal dari teks OCR
        atas berkas unggahan warga, jadi tiap sel lewat format_html (escape).
        """
        if not obj or not obj.pk:
            return 'Nilai pembanding muncul setelah berkas disimpan.'
        if obj.jenis not in JENIS_BERNILAI:
            return format_html(
                'Berkas berjenis {} tidak dipasangkan dengan isian formulir karena '
                'formulir warga tidak punya field padanannya (mis. nomor KK). '
                'Periksa isinya langsung; status prapemilahan sengaja dibiarkan '
                '"Belum dinilai" alih-alih dipaksa memberi skor.',
                obj.get_jenis_display(),
            )
        baris = baris_perbandingan(obj.penduduk, obj.extracted_data, obj.ocr_confidence)
        rows = format_html_join(
            '\n',
            (
                '<tr><th>{}</th><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'
            ),
            ((b['label'], b['formulir'], b['ocr'], f"{b['kecocokan'] * 100:.0f}%", b['keterangan'])
             for b in baris),
        )
        skor = 'belum dinilai' if obj.ai_score is None else f'{obj.ai_score:.1f}%'
        return format_html(
            '<div class="sip-ai-gulung"><table class="sip-ai-tabel"><thead><tr><th>Komponen</th>'
            '<th>Isian formulir</th><th>Hasil OCR</th><th>Kecocokan</th>'
            '<th>Keterangan</th></tr></thead><tbody>{}</tbody>'
            '<tfoot><tr><th colspan="3">Skor kecocokan</th>'
            '<td colspan="2"><strong>{}</strong> — ambang Valid {}%</td></tr></tfoot></table></div>',
            rows, skor, f'{AMBAT_VALID:.0f}',
        )

    def save_model(self, request, obj, form, change):
        """Setiap koreksi manual dihitung ulang oleh rumus mesin yang sama.

        Skor tidak dibiarkan sebagai teks yang tadi ditulis OCR: begitu petugas
        membetulkan NIK/nama, prapemilahan harus ikut bergerak. Catatan sistem
        hanya ditimpa bila petugas tidak menulis catatannya sendiri.
        """
        hasil = nilai_berkas(obj.penduduk, obj.extracted_data, obj.ocr_confidence, obj.jenis)
        obj.ai_score = hasil['skor']
        obj.ai_prescreen = hasil['prescreen']
        obj.ai_verified = hasil['prescreen'] == 'valid'
        dikoreksi_tangan = bool({'extracted_nik', 'extracted_nama'} & set(form.changed_data))
        if dikoreksi_tangan and 'ai_verification_notes' not in form.changed_data:
            obj.ai_verification_notes = hasil['catatan']
        super().save_model(request, obj, form, change)
        if dikoreksi_tangan:
            pencatat = request.user.get_full_name() or request.user.username
            AuditLog.objects.create(
                user=request.user,
                aksi='ai_koreksi_manual',
                deskripsi=(
                    f'Hasil OCR {obj.nama} ({obj.penduduk.nama}) dikoreksi oleh {pencatat}; '
                    f'skor {obj.ai_score}% -> {obj.get_ai_prescreen_display()}.'
                ),
            )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
