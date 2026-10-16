from datetime import timedelta
from datetime import datetime
import io
import json
import mimetypes
import os
import threading
from functools import wraps
from urllib.parse import quote
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import PasswordChangeFormDjango
from django.contrib import messages
from django.db import IntegrityError
from django.http import Http404
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.db import connection
from django.core.cache import cache
from django.utils import formats, timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from . import chatbot, llm, pdf_report
from .csv_utils import sel_aman
from .keputusan import terapkan_status
from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan, Pemutakhiran, UserRole


# OCR menjalankan OpenCV + Tesseract yang berat. Satu unggahan warga bisa
# memicu beberapa berkas sekaligus, dan tanpa batas ini tiap berkas men-spawn
# thread yang semuanya berebut CPU/RAM pada server tunggal. Semaphore membatasi
# pekerjaan OCR sungguhan sampai dua benang; thread lain tetap dibuat tapi
# menunggu di sini. Koneksi DB milik thread ditutup di finally karena thread
# daemon tidak dibersihkan otomatis oleh Django.
_OCR_CONCURRENCY = threading.BoundedSemaphore(2)


def _trigger_ocr_async(dokumen_id):
    """Trigger OCR processing di background thread agar tidak blocking request."""
    from django.db import connection
    try:
        with _OCR_CONCURRENCY:
            from .ocr_processor import process_document
            dokumen = Dokumen.objects.get(pk=dokumen_id)
            result = process_document(dokumen)
            if result['success']:
                AuditLog.objects.create(
                    aksi='ocr_processed',
                    deskripsi=(
                        f'OCR berhasil pada {dokumen.nama} '
                        f'(confidence: {result["confidence"]}%, '
                        f'skor kecocokan: {result["skor"]}%, '
                        f'prapemilahan: {result["prescreen"]})'
                    ),
                )
            elif result.get('skipped'):
                # Bukan kegagalan: berkas jenis ini memang tidak dinilai mesin.
                # Dicatat terpisah supaya log "ocr_failed" tetap berarti rusak.
                AuditLog.objects.create(
                    aksi='ocr_dilewati',
                    deskripsi=f'OCR dilewati pada {dokumen.nama}: {result["error"]}',
                )
    except Exception as e:
        # Log error tapi jangan crash thread utama
        try:
            AuditLog.objects.create(aksi='ocr_failed', deskripsi=f'OCR gagal: {str(e)}')
        except Exception:
            pass  # Jika logging juga gagal, biarkan saja
    finally:
        connection.close()


def is_officer(user):
    return user.is_authenticated and (user.is_staff or UserRole.objects.filter(user=user, role='petugas').exists())


PUBLIC_LIMIT = 60
PUBLIC_WINDOW = 300

# Keputusan yang merugikan warga harus menyertakan alasan. Menolak atau meminta
# perbaikan tanpa catatan membuat warga tidak tahu apa yang harus diperbaiki
# (laporan §6.4), dan tombol kirim ulang hanya terbuka untuk dua status ini.
STATUS_WAJIB_CATATAN = {'ditolak', 'perlu_perbaikan'}


def _client_ip(request):
    """Alamat IP pemanggil, terkoreksi untuk topologi Apache -> Waitress di mesin ini.

    Waitress selalu melihat REMOTE_ADDR = 127.0.0.1 karena Apache yang menghubungkan
    diri, jadi tanpa X-Forwarded-For semua pengunjung berbagi satu pencacah. Apache
    menambahkan IP klien sungguhan di AKHIR daftar, dan nilai itulah yang dipercaya;
    bagian depan masih bisa dipalsukan klien, jadi tidak dipakai.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[-1].strip() or 'anon'
    return request.META.get('REMOTE_ADDR', 'anon')


def throttle_public(view=None, *, limit=PUBLIC_LIMIT, window=PUBLIC_WINDOW, json_error=False):
    """Batas kasar permintaan per alamat IP untuk endpoint yang bisa dibuka tanpa login.

    LocMemCache bersifat per proses, jadi ini pengaman dari penyalahgunaan sederhana
    (enumerasi kode kartu, spam API), bukan kuota ketat. Setiap hit menyegarkan
    masa berlaku pencacah, sehingga jendela waktu bergeser selama IP terus meminta.
    """
    def decorate(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            key = f'publik:{func.__name__}:{_client_ip(request)}'
            if cache.get(key, 0) >= limit:
                if json_error:
                    response = JsonResponse({'detail': 'Terlalu banyak permintaan.'}, status=429)
                else:
                    response = HttpResponse('Terlalu banyak permintaan. Coba lagi beberapa menit lagi.', status=429)
                response['Retry-After'] = window
                return response
            cache.set(key, cache.get(key, 0) + 1, window)
            return func(request, *args, **kwargs)
        return wrapper
    if view is None:
        return decorate
    return decorate(view)


def landing_counts():
    """Angka nyata dari database untuk pill statistik di landing page."""
    return {
        'warga': Penduduk.objects.count(),
        'disetujui': Pengajuan.objects.filter(status='disetujui').count(),
    }


def home(request):
    counts = landing_counts()
    return render(request, 'landing.html', {
        'stat_warga': counts['warga'],
        'stat_disetujui': counts['disetujui'],
    })


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    applications = Pengajuan.objects.select_related('penduduk').order_by('-submitted_at')
    if not request.user.is_staff:
        applications = applications.filter(penduduk__user=request.user)
    person = Penduduk.objects.filter(user=request.user).prefetch_related('dokumen').select_related('pengajuan', 'kartu').first()
    context = {'latest': applications[:5], 'total': applications.count(), 'pending': applications.filter(status='menunggu').count(), 'approved': applications.filter(status='disetujui').count(), 'person': person, 'card': getattr(person, 'kartu', None) if person else None}
    return render(request, 'dashboard.html' if is_officer(request.user) else 'citizen_dashboard_v4.html', context)


@login_required(login_url='/login/')
def update_data(request):
    # Penduduk.user adalah ForeignKey, jadi akun lama bisa punya lebih dari satu
    # baris penduduk. Ambil baris pertama (konsisten dengan dashboard) supaya
    # halaman ini tidak 500 karena MultipleObjectsReturned pada data ganda warisan.
    person = Penduduk.objects.filter(user=request.user).order_by('id').first()
    if person is None:
        raise Http404('Data perantauan belum ditemukan.')
    if request.method == 'POST':
        old_data = {'daerah_asal': person.daerah_asal, 'kota_tujuan': person.kota_tujuan, 'tujuan': person.tujuan}
        person.daerah_asal = request.POST.get('origin', '').strip()
        person.kota_tujuan = request.POST.get('destination', '').strip()
        person.tujuan = request.POST.get('purpose', '').strip()
        if not all((person.daerah_asal, person.kota_tujuan, person.tujuan)):
            messages.error(request, 'Semua data pemutakhiran wajib diisi.')
        elif person.tujuan not in dict(Penduduk.TUJUAN):
            messages.error(request, 'Tujuan merantau tidak dikenali.')
        else:
            person.save(update_fields=['daerah_asal', 'kota_tujuan', 'tujuan'])
            Pemutakhiran.objects.create(penduduk=person, data_lama=old_data, data_baru={'daerah_asal': person.daerah_asal, 'kota_tujuan': person.kota_tujuan, 'tujuan': person.tujuan})
            AuditLog.objects.create(user=request.user, aksi='pemutakhiran', deskripsi=f'Domisili diperbarui ke {person.kota_tujuan}.')
            messages.success(request, 'Data perantauan berhasil diperbarui.')
            return redirect('core:dashboard')
    return render(request, 'update_data.html', {'person': person, 'tujuan_pilihan': Penduduk.TUJUAN})


def register(request):
    if request.method == 'POST':
        name, email = request.POST.get('name', '').strip(), request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        if name and email and len(password) >= 8 and not User.objects.filter(username=email).exists():
            user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
            UserRole.objects.create(user=user, role='masyarakat')
            login(request, user)
            AuditLog.objects.create(user=user, aksi='registrasi', deskripsi='Akun masyarakat dibuat.')
            messages.success(request, 'Akun berhasil dibuat. Lengkapi data perantauan Anda.')
            return redirect('core:application')
        messages.error(request, 'Nama, email unik, dan password minimal 8 karakter wajib diisi.')
    return render(request, 'register_v2.html')


def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('email', '').strip()
        # IP klien sungguhan, bukan REMOTE_ADDR: di belakang Apache semua
        # pengunjung tampak berasal dari 127.0.0.1, jadinya satu penyerang bisa
        # menghabiskan jatah 5 percobaan akun siapa pun dari mana pun.
        throttle_key = f'login-fail:{_client_ip(request)}:{identifier.lower()}'
        if cache.get(throttle_key, 0) >= 5:
            messages.error(request, 'Terlalu banyak percobaan. Coba lagi dalam 15 menit.')
            return render(request, 'login.html')
        account = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        user = authenticate(request, username=account.username if account else identifier, password=request.POST.get('password', ''))
        if user:
            cache.delete(throttle_key)
            login(request, user)
            # Kembalikan ke halaman yang tadinya dituju (parameter next dibuat
            # oleh login_required), tapi hanya bila tujuannya masih di host ini;
            # jangan sampai next dipakai untuk open redirect ke situs lain.
            target = request.POST.get('next') or request.GET.get('next')
            if not target or not url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
                target = 'core:officer' if is_officer(user) else 'core:dashboard'
            return redirect(target)
        cache.set(throttle_key, cache.get(throttle_key, 0) + 1, 900)
        messages.error(request, 'Email atau password tidak sesuai.')
    return render(request, 'login.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('core:home')


@login_required(login_url='/login/')
def change_password(request):
    form = PasswordChangeFormDjango(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        AuditLog.objects.create(user=user, aksi='password', deskripsi='Password akun diperbarui.')
        messages.success(request, 'Password berhasil diperbarui.')
        return redirect('core:dashboard')
    return render(request, 'change_password.html', {'form': form})


@login_required(login_url='/login/')
def profile(request):
    return render(request, 'profile.html', {'profile_user': request.user, 'role': 'Petugas' if is_officer(request.user) else 'Masyarakat'})


LAMPILAN_UPLOAD = [('ktp', 'KTP'), ('kk', 'Kartu Keluarga')]
# Pasfoto ikut di form yang sama, tetapi aturannya berbeda: hanya gambar (tanpa
# PDF) dan tidak wajib. Kartu warga tanpa pasfoto tetap terbit, dengan inisial
# nama sebagai pengganti fotonya. Karena itu pasfoto masuk SEMUA_LAMPILAN (untuk
# pemeriksaan berkas dan jatah ukuran permintaan) tapi tidak LAMPILAN_UPLOAD
# (daftar berkas yang harus ada).
LAMPILAN_PILIHAN = [('pasfoto', 'Pasfoto')]
SEMUA_LAMPILAN = LAMPILAN_UPLOAD + LAMPILAN_PILIHAN
GAMBAR_SAJA = frozenset(field for field, _ in LAMPILAN_PILIHAN)


def _validate_lampiran(request, files):
    """Return label lampiran yang ditolak; kosong berarti semua berkas sah.

    Pemeriksaan dilakukan sebelum data warga ditulis ke database, jadi pengajuan
    yang ditolak tidak meninggalkan baris yatim yang harus dihapus manual.
    """
    for field, label in SEMUA_LAMPILAN:
        uploaded = files.get(field)
        if not uploaded:
            continue
        hanya_gambar = field in GAMBAR_SAJA
        if uploaded.size > MAX_UPLOAD_BYTES:
            messages.error(request, f'Ukuran {label.lower()} maksimal 5 MB.')
            return label
        if not _valid_upload(uploaded, hanya_gambar=hanya_gambar):
            format_sah = 'JPG atau PNG' if hanya_gambar else 'PDF, JPG, atau PNG'
            messages.error(request, f'{label} harus berformat {format_sah}.')
            return label
    return None


@login_required(login_url='/login/')
def application(request):
    if request.method == 'POST':
        data = {key: request.POST.get(key, '').strip() for key in ('name', 'nik', 'origin', 'destination', 'purpose', 'phone', 'tanggal_mulai', 'perkiraan_kembali')}
        files = {field: request.FILES.get(field) for field, _ in SEMUA_LAMPILAN}
        kurang = [label for field, label in LAMPILAN_UPLOAD if not files[field]]
        rejected = _validate_lampiran(request, files)
        if len(data['nik']) != 16 or not data['nik'].isdigit():
            messages.error(request, 'NIK harus terdiri dari tepat 16 digit angka.')
        elif data['phone'] and (not data['phone'].isdigit() or not 10 <= len(data['phone']) <= 15):
            messages.error(request, 'Nomor telepon harus 10-15 digit.')
        elif not all(data[key] for key in ('name', 'nik', 'origin', 'destination', 'purpose')):
            messages.error(request, 'Lengkapi seluruh data pengajuan.')
        elif data['purpose'] not in dict(Penduduk.TUJUAN):
            messages.error(request, 'Tujuan merantau tidak dikenali.')
        elif any(data[key] and not _valid_date(data[key]) for key in ('tanggal_mulai', 'perkiraan_kembali')):
            messages.error(request, 'Format tanggal perjalanan tidak valid.')
        elif kurang:
            messages.error(request, f'Lampirkan foto {", ".join(kurang)} (PDF, JPG, atau PNG, maksimal 5 MB).')
        elif rejected:
            pass
        elif Penduduk.objects.filter(user=request.user).exists():
            messages.error(request, 'Akun ini sudah memiliki data perantauan. Gunakan menu Pemutakhiran untuk memperbarui domisili, atau kirim ulang dari Ringkasan bila pengajuan perlu perbaikan.')
        elif Penduduk.objects.filter(nik=data['nik']).exists():
            messages.error(request, 'NIK tersebut sudah terdaftar.')
        else:
            try:
                person = Penduduk.objects.create(user=request.user, nama=data['name'], nik=data['nik'], nomor_telepon=data['phone'], tanggal_mulai=_parse_date(data['tanggal_mulai']), perkiraan_kembali=_parse_date(data['perkiraan_kembali']), daerah_asal=data['origin'], kota_tujuan=data['destination'], tujuan=data['purpose'], foto=files['pasfoto'])
                Pengajuan.objects.create(penduduk=person)
                for field, _ in LAMPILAN_UPLOAD:
                    uploaded = files[field]
                    doc = Dokumen.objects.create(penduduk=person, jenis=field, nama=os.path.basename(uploaded.name), file=uploaded, ukuran=uploaded.size)
                    # Trigger OCR processing di background
                    threading.Thread(target=_trigger_ocr_async, args=(doc.id,), daemon=True).start()
                jumlah_lampiran = len(LAMPILAN_UPLOAD) + (1 if files['pasfoto'] else 0)
                AuditLog.objects.create(user=request.user, aksi='pengajuan', deskripsi=f'Pengajuan dibuat untuk {person.nama} dengan {jumlah_lampiran} lampiran.')
            except IntegrityError:
                messages.error(request, 'NIK tersebut sudah terdaftar.')
                return render(request, 'application_v3.html', {'name': request.user.first_name, 'tujuan_pilihan': Penduduk.TUJUAN})
            messages.success(request, 'Pengajuan tersimpan dan masuk antrean verifikasi.')
            return redirect('core:dashboard')
    return render(request, 'application_v3.html', {'name': request.user.first_name, 'tujuan_pilihan': Penduduk.TUJUAN})


@login_required(login_url='/login/')
def resubmit_application(request, pk):
    item = get_object_or_404(Pengajuan.objects.select_related('penduduk'), pk=pk, penduduk__user=request.user)
    if request.method != 'POST':
        return redirect('core:dashboard')
    if item.status not in {'perlu_perbaikan', 'ditolak'}:
        messages.error(request, 'Pengajuan ini belum dapat dikirim ulang.')
    else:
        files = {field: request.FILES.get(field) for field, _ in SEMUA_LAMPILAN}
        if _validate_lampiran(request, files):
            return redirect('core:dashboard')
        item.status = 'menunggu'
        item.catatan = ''
        item.save(update_fields=['status', 'catatan'])
        for field, label in LAMPILAN_UPLOAD:
            uploaded = files[field]
            if not uploaded:
                continue
            existing = item.penduduk.dokumen.filter(jenis=field).first()
            if existing:
                nama_lama = existing.file.name
                existing.nama = os.path.basename(uploaded.name)
                existing.ukuran = uploaded.size
                existing.status = 'pending'
                existing.file = uploaded
                existing.save(update_fields=['nama', 'ukuran', 'status', 'file'])
                # Trigger OCR ulang untuk dokumen yang diganti
                threading.Thread(target=_trigger_ocr_async, args=(existing.id,), daemon=True).start()
                # Penggantian FileField tidak menghapus berkas lama, jadi
                # dibersihkan sendiri supaya folder media tidak menumpuk scan
                # warga yang sudah tidak dipakai.
                default_storage.delete(nama_lama)
            else:
                doc = Dokumen.objects.create(penduduk=item.penduduk, jenis=field, nama=os.path.basename(uploaded.name), file=uploaded, ukuran=uploaded.size)
                threading.Thread(target=_trigger_ocr_async, args=(doc.id,), daemon=True).start()
        if files['pasfoto']:
            nama_lama = item.penduduk.foto.name
            item.penduduk.foto = files['pasfoto']
            item.penduduk.save(update_fields=['foto'])
            # Sama seperti dokumen: berkas foto lama dihapus sendiri supaya
            # media/ tidak menumpuk pasfoto yang sudah diganti warga.
            if nama_lama:
                default_storage.delete(nama_lama)
        AuditLog.objects.create(user=request.user, aksi='kirim_ulang', deskripsi=f'Pengajuan {item.penduduk.nama} dikirim ulang.')
        messages.success(request, 'Pengajuan berhasil dikirim ulang untuk ditinjau.')
    return redirect('core:dashboard')


def annotate_jenis_dokumen(page):
    """Tempelkan himpunan jenis lampiran yang sudah ada ke tiap baris antrean.

    Petugas harus bisa melihat dari daftar apakah KTP dan KK sudah terkirim
    tanpa membuka satu per satu. Satu query untuk seluruh halaman, bukan per
    baris.
    """
    items = list(page) if page else []
    punya = {}
    for penduduk_id, jenis in Dokumen.objects.filter(penduduk_id__in=[a.penduduk_id for a in items]).values_list('penduduk_id', 'jenis'):
        punya.setdefault(penduduk_id, set()).add(jenis)
    for item in items:
        item.jenis_ada = punya.get(item.penduduk_id, set())
    return page


@user_passes_test(is_officer, login_url='/login/')
def officer(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    applications = Pengajuan.objects.select_related('penduduk').order_by('-submitted_at')
    if query:
        applications = applications.filter(penduduk__nama__icontains=query) | applications.filter(penduduk__nik__icontains=query)
    if status in {'menunggu', 'disetujui', 'ditolak', 'perlu_perbaikan'}:
        applications = applications.filter(status=status)
    if request.GET.get('export') == 'csv':
        import csv
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="laporan-pengajuan.csv"'
        writer = csv.writer(response)
        writer.writerow(['Nama', 'NIK', 'Asal', 'Tujuan', 'Alasan', 'Status', 'Dikirim'])
        for item in applications:
            writer.writerow([sel_aman(item.penduduk.nama), item.penduduk.nik, sel_aman(item.penduduk.daerah_asal),
                             sel_aman(item.penduduk.kota_tujuan), sel_aman(item.penduduk.tujuan),
                             item.get_status_display(), item.submitted_at.isoformat()])
        return response
    if request.method == 'POST':
        item = get_object_or_404(Pengajuan, pk=request.POST.get('id'))
        requested_status = request.POST.get('status', 'menunggu')
        catatan = request.POST.get('catatan', '').strip()
        if requested_status not in dict(Pengajuan.STATUS):
            messages.error(request, 'Status verifikasi tidak valid.')
        elif requested_status in STATUS_WAJIB_CATATAN and not catatan:
            # Menolak/minta perbaikan tanpa alasan membuat warga menebak-nebak
            # dan mengirim ulang berkas yang sama. Laporan §6.4 mewajibkan
            # catatan, maka keputusan negatif dikunci di sisi server.
            messages.error(request, 'Tolak atau minta perbaikan wajib disertai catatan untuk warga.')
        else:
            berubah, email_terkirim = terapkan_status(
                item, requested_status, request.user, request,
                catatan=catatan or None, sumber='antrean petugas')
            if not berubah:
                messages.info(request, f'Status {item.penduduk.nama} sudah {item.get_status_display()}, tidak ada yang berubah.')
            elif email_terkirim:
                messages.success(request, f'Status {item.penduduk.nama} diperbarui dan warga diberitahu.')
            else:
                messages.warning(request, f'Status {item.penduduk.nama} diperbarui, tapi email pemberitahuan tidak terkirim.')
    page = Paginator(applications, 10).get_page(request.GET.get('page'))
    annotate_jenis_dokumen(page)
    return render(request, 'officer.html', {'applications': page, 'query': query, 'selected_status': status, 'page_obj': page})


@user_passes_test(is_officer, login_url='/login/')
def application_detail(request, pk):
    item = get_object_or_404(Pengajuan.objects.select_related('penduduk'), pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status', '')
        note = request.POST.get('catatan', '').strip()
        if status not in dict(Pengajuan.STATUS):
            messages.error(request, 'Status verifikasi tidak valid.')
        elif status in STATUS_WAJIB_CATATAN and not note:
            messages.error(request, 'Tolak atau minta perbaikan wajib disertai catatan untuk warga.')
        else:
            berubah, _ = terapkan_status(item, status, request.user, request, catatan=note,
                                         sumber='detail pengajuan')
            messages.success(request, 'Detail pengajuan berhasil diperbarui.' if berubah
                             else 'Catatan disimpan; status tidak berubah sehingga warga tidak dikirimi surat lagi.')
            return redirect('core:application_detail', pk=item.pk)
    documents = list(item.penduduk.dokumen.all())
    for document in documents:
        # Hanya gambar yang boleh ditanam sebagai <img>; PDF ditautkan saja agar
        # petugas tidak membuka banyak tab PDF saat meninjau.
        document.dapat_dipratinjau = document.file.name.lower().endswith(('.jpg', '.jpeg', '.png'))
    # Panel OCR menampilkan dokumen KTP lebih dulu (auto-verifikasi mencocokkan
    # NIK KTP); jika tidak ada KTP, pakai dokumen pertama. Sebelumnya panel ini
    # memakai ID dokumen yang ditulis tetap di template, sehingga selalu salah
    # atau gagal memuat begitu ID tersebut tidak ada.
    ocr_document = next((d for d in documents if d.jenis == 'ktp'), documents[0] if documents else None)
    return render(request, 'application_detail_v2.html', {
        'item': item,
        'documents': documents,
        'ocr_document': ocr_document,
        # Batas panjang pesan dan saran awal chatbot diambil dari modulnya agar
        # tidak ada angka yang ditulis dua kali (template vs backend).
        'CHAT_MAX_PANJANG': chatbot.MAX_PANJANG_PESAN,
        'CHAT_SARAN_AWAL': chatbot.SAPAAN,
    })


@user_passes_test(is_officer, login_url='/login/')
def document_review(request, pk):
    document = get_object_or_404(Dokumen, pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Dokumen.STATUS):
            document.status = status
            document.save(update_fields=['status'])
            AuditLog.objects.create(user=request.user, aksi='dokumen', deskripsi=f'Dokumen {document.nama} ditandai {document.get_status_display()}.')
            messages.success(request, 'Status dokumen diperbarui.')
    return redirect('core:application_detail', pk=document.penduduk.pengajuan.pk)


def _serve_file(field):
    """
    Sajikan file tersimpan tanpa Alias publik.

    FileResponse (streaming) sengaja dihindari: penundaan penutupan koneksi di
    akhir respons membatalkan transaksi MariaDB yang masih terbuka, sehingga
    query berikutnya gagal. File di sini berukuran scan/PDF sehingga dibaca penuh.
    """
    try:
        with field.open('rb') as handle:
            payload = handle.read()
    except (FileNotFoundError, OSError):
        raise Http404('File tidak ditemukan.')
    content_type, _ = mimetypes.guess_type(field.name)
    if content_type not in {'application/pdf', 'image/jpeg', 'image/png'}:
        content_type = 'application/octet-stream'
    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = "inline; filename*=UTF-8''" + quote(os.path.basename(field.name))
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Frame-Options'] = 'DENY'
    response['Cache-Control'] = 'no-store'
    return response


@login_required(login_url='/login/')
def document_file(request, pk):
    """File dokumen warga hanya dibuka oleh pemiliknya atau petugas."""
    document = get_object_or_404(Dokumen, pk=pk)
    if not is_officer(request.user) and document.penduduk.user_id != request.user.id:
        raise Http404('File tidak ditemukan.')
    AuditLog.objects.create(user=request.user, aksi='dokumen', deskripsi=f'Dokumen {document.nama} dibuka.')
    return _serve_file(document.file)


@login_required(login_url='/login/')
def penduduk_foto(request, pk):
    """Pasfoto warga, hanya untuk pemilik akunnya dan petugas.

    Kartu digital bisa dibuka publik lewat tautan QR, jadi wajah warga tidak
    boleh diambil hanya dengan menebak URL. Template kartu sudah tidak
    menyisipkan <img> untuk pengunjung anonim; ini lapis keduanya, dan warga
    lain yang menebak id tetap mendapat 404 alih-alih 403 supaya keberadaan
    id tidak bisa dipetakan dari luar.
    """
    person = get_object_or_404(Penduduk, pk=pk)
    if not is_officer(request.user) and person.user_id != request.user.id:
        raise Http404('File tidak ditemukan.')
    if not person.foto:
        raise Http404('File tidak ditemukan.')
    return _serve_file(person.foto)


@throttle_public(limit=120)
def card_qr(request, code):
    """Gambar QR kartu. Isinya hanya URL validasi yang memang sudah publik di halaman kartu."""
    card = get_object_or_404(KartuDigital, kode=code)
    if not card.qr_code:
        raise Http404('File tidak ditemukan.')
    return _serve_file(card.qr_code)


@login_required(login_url='/login/')
def history(request):
    # Alasan sama dengan update_data: baris penduduk ganda warisan tidak boleh
    # membuat halaman histori 500. Pakai baris pertama yang sama dengan dashboard.
    person = Penduduk.objects.filter(user=request.user).order_by('id').first()
    if person is None:
        raise Http404('Data perantauan belum ditemukan.')
    return render(request, 'history.html', {'updates': person.riwayat_pemutakhiran.all(), 'logs': AuditLog.objects.filter(user=request.user).order_by('-created_at')[:30]})


@throttle_public
def scan_card(request):
    return render(request, 'scan_card.html')


@user_passes_test(is_officer, login_url='/login/')
def statistics(request):
    label_status = dict(Pengajuan.STATUS)
    by_status = [{'label': label_status.get(row['status'], row['status']), 'total': row['total']}
                 for row in Pengajuan.objects.values('status').annotate(total=Count('id'))]
    by_destination = list(Penduduk.objects.values('kota_tujuan').annotate(total=Count('id')).order_by('-total')[:8])
    maximum = max([row['total'] for row in by_destination] or [1])
    status_maksimum = max([row['total'] for row in by_status] or [1])
    return render(request, 'statistics_chart.html', {'by_status': by_status, 'by_destination': by_destination, 'maximum': maximum, 'status_maksimum': status_maksimum, 'total': Penduduk.objects.count(), 'approved': Pengajuan.objects.filter(status='disetujui').count()})


@throttle_public
def validate_card(request, code):
    card = KartuDigital.objects.select_related('penduduk').filter(kode=code).first()
    if not card:
        raise Http404('Kartu tidak ditemukan')
    if card.status == 'aktif' and card.berlaku_sampai < timezone.now().date():
        card.status = 'expired'
        card.save(update_fields=['status'])
    # Tautan "data lengkap" hanya disiapkan bila yang memindai petugas yang sudah
    # login. Pengunjung anonim tetap melihat halaman validasi publik seperti
    # semula: NIK tersamar, tanpa jalan masuk ke data kependudukan penuh.
    pengajuan_id = None
    if is_officer(request.user):
        pengajuan_id = Pengajuan.objects.filter(penduduk=card.penduduk).values_list('id', flat=True).first()
    # Pasfoto hanya dikirim ke template bila yang membuka kartu berhak melihat
    # wajahnya (pemilik atau petugas). Pengunjung anonim tetap melihat kartu
    # lengkap dengan NIK tersamar, tanpa foto.
    boleh_lihat_foto = is_officer(request.user) or (request.user.is_authenticated and card.penduduk.user_id == request.user.id)
    return render(request, 'card_v2.html', {'card': card, 'valid': card.is_valid(), 'pengajuan_id': pengajuan_id, 'boleh_lihat_foto': boleh_lihat_foto, 'batasan': KARTU_BATASAN})


@throttle_public
def card_lookup(request):
    code = request.GET.get('code', '').strip()
    if not code:
        return redirect('core:home')
    return redirect('core:validate_card', code=code)


# Batasan operasional yang tercetak di kartu, baik versi layar maupun PDF.
# Teksnya dijaga di satu tempat supaya kartu web dan hasil unduhan tidak pernah
# berbeda pernyataan.
KARTU_BATASAN = [
    'SIPPER bukan pengganti dokumen seperti KTP, KK, atau SKPWRI.',
    'SIPPER tidak melakukan integrasi atau sinkronisasi langsung ke database nasional Dukcapil.',
    'Verifikasi dan kartu digital SIPPER hanya berlaku secara internal di dalam ekosistem aplikasi SIPPER.',
]
MERAH_KARTU = '#c8102e'

# Ukuran kartu identitas standar ID-1 — 85,60 × 53,98 mm, dipakai KTP, KK digital,
# BPJS, dan ATM. Poin PDF (72 poin = 1 inci) membuat kartu tercetak 1:1 ketika
# halaman dikeluarkan pada skala 100%, jadi hasil unduhan bisa langsung dipotong
# sebesar kartu asli. Rasio yang sama juga dipakai kartu layar (aspect-ratio di
# templates/card_v2.html) supaya bentuk keduanya tidak pernah berbeda.
POIN_PER_MM = 72 / 25.4
KARTU_ID1_MM = (85.6, 53.98)
KARTU_ID1_PT = (KARTU_ID1_MM[0] * POIN_PER_MM, KARTU_ID1_MM[1] * POIN_PER_MM)


def _tanggal_kartu(tanggal):
    """Nama bulan gaya Indonesia untuk kartu PDF.

    strftime di server ini ikut locale C, jadi "%d %B %Y" mencetak
    "09 October 2027" sementara kartu layar sudah "09 Okt 2027". Formatter
    Django mengikuti LANGUAGE_CODE sehingga kedua tampilan selalu sama.
    """
    return formats.date_format(tanggal, 'd M Y')


def _nik_samar(nik):
    """NIK berformat 16 digit dengan 12 angka pertama ditutupi."""
    return '*' * max(len(nik) - 4, 0) + nik[-4:]


def _potong_kata(kata, nama_font, ukuran, lebar_maks, document):
    """Iris satu kata yang lebih lebar dari kolomnya jadi beberapa potongan.

    Tanpa ini, nama 150 karakter tanpa spasi (batas kolom di basis data) jadi
    satu baris utuh selebar lebih dari dua halaman A4 dan menembus kartu.
    """
    if not kata or document.stringWidth(kata, nama_font, ukuran) <= lebar_maks:
        return [kata]
    potongan = []
    sisa = kata
    while sisa:
        ambil = 1
        while ambil < len(sisa) and document.stringWidth(sisa[:ambil + 1], nama_font, ukuran) <= lebar_maks:
            ambil += 1
        potongan.append(sisa[:ambil])
        sisa = sisa[ambil:]
    return potongan


def _baris_teks(teks, nama_font, ukuran, lebar_maks, document):
    """Pecah kalimat jadi baris yang muat lebar kolom tanpa memotong kata."""
    baris, sekarang = [], ''
    kata_panjang = []
    for kata in teks.split():
        kata_panjang += _potong_kata(kata, nama_font, ukuran, lebar_maks, document)
    for kata in kata_panjang:
        calon = f'{sekarang} {kata}'.strip()
        if not sekarang or document.stringWidth(calon, nama_font, ukuran) <= lebar_maks:
            sekarang = calon
        else:
            baris.append(sekarang)
            sekarang = kata
    if sekarang:
        baris.append(sekarang)
    return baris


def _potret_pasfoto(field):
    """Pasfoto siap cetak dengan rasio 3:4, terpotong dari tengah.

    reportlab tidak memotong gambar, jadi foto lanskap akan mendorong isi kartu
    keluar bila digambar apa adanya. Berkas yang rusak atau tidak terbaca
    dikembalikan None supaya kartu tetap terbit dengan blok inisial.
    """
    try:
        from PIL import Image
        with Image.open(field) as gambar:
            gambar = gambar.convert('RGB')  # paksa decode sebelum file ditutup
            lebar, tinggi = gambar.size
            target = 3 / 4
            if lebar / tinggi > target:
                baru = int(tinggi * target)
                kiri = (lebar - baru) // 2
                gambar = gambar.crop((kiri, 0, kiri + baru, tinggi))
            elif lebar / tinggi < target:
                baru = int(lebar / target)
                atas = (tinggi - baru) // 2
                gambar = gambar.crop((0, atas, lebar, atas + baru))
            # Kotak foto di kartu hanya 54x72 poin (19 x 25 mm). Tanpa pembatasan
            # ini, pasfoto 5 MB ikut tertempel utuh ke PDF dan ukuran berkasnya
            # membengkak; 600 piksel sudah lebih dari tajam untuk cetak 300 dpi.
            gambar.thumbnail((600, 800))
            # Dikemas ulang jadi JPEG. Objek PIL RGB dikirim reportlab sebagai
            # data mentah (~1 MB per foto), sedangkan berkas JPEG ditempel apa
            # adanya sehingga PDF kartu tetap ringan.
            buffer = io.BytesIO()
            gambar.save(buffer, format='JPEG', quality=82, optimize=True)
            buffer.seek(0)
            return buffer
    except Exception:
        return None


@throttle_public(limit=20)
def download_card(request, code):
    card = get_object_or_404(KartuDigital.objects.select_related('penduduk'), kode=code)
    if not request.user.is_authenticated or (not is_officer(request.user) and card.penduduk.user_id != request.user.id):
        return redirect('core:login')
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from django.http import HttpResponse
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="kartu-{card.kode}.pdf"'
    merah = colors.HexColor(MERAH_KARTU)
    tua = colors.HexColor('#17392b')
    redup = colors.HexColor('#5b6f66')
    document = canvas.Canvas(response, pagesize=A4)
    lebar_halaman, tinggi_halaman = A4

    # Isi blok batasan diukur lebih dulu karena tinggi bingkainya mengikuti
    # jumlah baris. Blok ini dicetak di bawah kartu, bukan di dalamnya: tiga
    # kalimat keteraturan tidak muat di kartu 54 mm dengan huruf yang masih
    # terbaca, persis seperti KTP asli yang juga tidak memuatnya.
    lebar_teks = 475
    baris_batasan = []
    for nomor, teks in enumerate(KARTU_BATASAN, start=1):
        baris_batasan += _baris_teks(f'{nomor}. {teks}', 'Helvetica', 7.5, lebar_teks - 30, document)

    # ---- Kartu ukuran asli (ID-1) ----
    k_lebar, k_tinggi = KARTU_ID1_PT
    x0 = (lebar_halaman - k_lebar) / 2
    y_atas = tinggi_halaman - 88
    x1 = x0 + k_lebar
    y_bawah = y_atas - k_tinggi
    dalam = 7           # margin isi di dalam kartu
    head = 26           # pita judul merah
    pita = 22           # pita masa berlaku + kode validasi
    f_lebar, f_tinggi = 54, 72            # kotak foto 3:4, sebangun dengan kartu layar
    qr_sisi = 54
    atas_badan = y_atas - head - 7
    bawah_pita = y_bawah + dalam
    x_identitas = x0 + dalam + f_lebar + 8
    lebar_identitas = (x1 - dalam - qr_sisi - 8) - x_identitas

    # Bingkai kartu.
    document.setFillColor(colors.white)
    document.setStrokeColor(colors.HexColor('#d7dcd3'))
    document.setLineWidth(.8)
    document.roundRect(x0, y_bawah, k_lebar, k_tinggi, 5, fill=1, stroke=1)

    # Header merah. reportlab tidak bisa membulatkan dua sudut saja, jadi sudut
    # bawah ditutup persegi panjang yang warnanya sama.
    document.setFillColor(merah)
    document.roundRect(x0, y_atas - head, k_lebar, head, 5, fill=1, stroke=0)
    document.rect(x0, y_atas - head, k_lebar, head / 2, fill=1, stroke=0)
    document.setFillColor(colors.white)
    document.setFont('Helvetica-Bold', 11)
    document.drawString(x0 + dalam, y_atas - 12, 'Kartu SIPPER')
    document.setFont('Helvetica', 5.2)
    document.drawString(x0 + dalam, y_atas - 19.5, 'Sistem Informasi Penduduk Perantauan')
    document.setFont('Helvetica-Bold', 5.6)
    document.drawRightString(x1 - dalam, y_atas - 12, 'TERVERIFIKASI' if card.is_valid() else 'TIDAK AKTIF')

    # Pasfoto di kiri, blok inisial bila warga belum mengunggah foto.
    document.setFillColor(colors.HexColor('#eef0df'))
    document.roundRect(x0 + dalam, atas_badan - f_tinggi, f_lebar, f_tinggi, 3, fill=1, stroke=0)
    potret = _potret_pasfoto(card.penduduk.foto) if card.penduduk.foto else None
    if potret is not None:
        try:
            document.drawImage(ImageReader(potret), x0 + dalam, atas_badan - f_tinggi,
                               width=f_lebar, height=f_tinggi, preserveAspectRatio=True, mask='auto')
        except Exception:
            potret = None
    if potret is None:
        # Sama seperti kartu layar: blok merah muda mengisi kotak foto, bukan
        # lingkaran mengambang di tengahnya.
        document.setFillColor(colors.HexColor('#f6d9dc'))
        document.roundRect(x0 + dalam, atas_badan - f_tinggi, f_lebar, f_tinggi, 3, fill=1, stroke=0)
        document.setFillColor(merah)
        document.setFont('Helvetica-Bold', 20)
        document.drawCentredString(x0 + dalam + f_lebar / 2, atas_badan - f_tinggi / 2 - 5.5,
                                   card.penduduk.inisial or '?')

    # QR di kanan atas, sejajar dengan kepala kolom identitas.
    if card.qr_code and card.qr_code.path:
        document.drawImage(ImageReader(card.qr_code.path), x1 - dalam - qr_sisi,
                           atas_badan - qr_sisi, width=qr_sisi, height=qr_sisi,
                           preserveAspectRatio=True, mask='auto')

    # Identitas: nama, NIK tersamar, domisili. NIK tidak dicetak utuh, sama
    # seperti kartu di layar, karena berkas PDF bisa menyebar lewat ponsel.
    # Semua nilai dipecah per baris selebar kolomnya supaya nama atau kota tujuan
    # yang panjang tidak menimpa QR di sebelah kanan.
    y_teks = atas_badan
    document.setFont('Helvetica-Bold', 12)
    document.setFillColor(tua)
    for baris in _baris_teks(card.penduduk.nama, 'Helvetica-Bold', 12, lebar_identitas, document)[:2]:
        y_teks -= 14
        document.drawString(x_identitas, y_teks, baris)
    for label, nilai in (('NIK', _nik_samar(card.penduduk.nik)),
                         ('DOMISILI TUJUAN', card.penduduk.kota_tujuan)):
        y_teks -= 13
        document.setFont('Helvetica', 4.8)
        document.setFillColor(redup)
        document.drawString(x_identitas, y_teks, label)
        document.setFont('Helvetica-Bold', 8.5)
        document.setFillColor(tua)
        for baris in _baris_teks(nilai, 'Helvetica-Bold', 8.5, lebar_identitas, document)[:2]:
            y_teks -= 10
            document.drawString(x_identitas, y_teks, baris)

    # Petunjuk kecil di bawah kolom identitas; QR adalah satu-satunya jalan
    # memeriksa status kartu setelah berkas PDF dicetak dan difotokopi.
    document.setFont('Helvetica', 4.6)
    document.setFillColor(redup)
    document.drawString(x0 + dalam, bawah_pita + pita + 7,
                        'Pindai QR untuk memeriksa status kartu ini.')

    # Pita masa berlaku + kode validasi di dasar kartu.
    document.setFillColor(colors.HexColor('#f4f6f2'))
    document.roundRect(x0 + dalam, bawah_pita, k_lebar - 2 * dalam, pita, 3, fill=1, stroke=0)
    for x, label, nilai, ukuran in ((x0 + dalam + 5, 'BERLAKU SAMPAI', _tanggal_kartu(card.berlaku_sampai), 8),
                                     (x0 + 118, 'KODE VALIDASI', card.kode, 6.6)):
        document.setFont('Helvetica', 4.4)
        document.setFillColor(redup)
        document.drawString(x, bawah_pita + pita - 7, label)
        document.setFont('Helvetica-Bold', ukuran)
        document.setFillColor(tua)
        document.drawString(x, bawah_pita + 4, nilai)

    # ---- Keterangan di luar kartu, tetap pada ukuran baca normal ----
    y_petunjuk = y_bawah - 20
    document.setFont('Helvetica-Oblique', 7.5)
    document.setFillColor(redup)
    document.drawString(60, y_petunjuk,
                        'Format kartu mengikuti standar ID-1 (85,60 × 53,98 mm). '
                        'Cetak pada skala 100% lalu potong mengikuti bingkai.')

    atas_batasan = y_petunjuk - 14
    bawah_batasan = atas_batasan - (34 + len(baris_batasan) * 10)
    document.setFillColor(colors.white)
    document.setStrokeColor(colors.HexColor('#e3e7e0'))
    document.roundRect(60, bawah_batasan, lebar_teks, atas_batasan - bawah_batasan, 8, fill=1, stroke=1)
    document.setFont('Helvetica-Bold', 9)
    document.setFillColor(merah)
    document.drawString(75, atas_batasan - 20, 'Batasan & operasional sistem')
    document.setFont('Helvetica', 7.5)
    document.setFillColor(colors.HexColor('#3f4a44'))
    tinggi_teks = atas_batasan - 36
    for baris in baris_batasan:
        document.drawString(75, tinggi_teks, baris)
        tinggi_teks -= 10
    document.setFont('Helvetica', 7)
    document.setFillColor(redup)
    document.drawString(60, bawah_batasan - 15, 'Kartu dibuat otomatis oleh SIPPER. Status dapat diperiksa ulang dengan memindai QR.')
    document.save()
    return response


@user_passes_test(is_officer, login_url='/login/')
def pengajuan_report_pdf(request, pk):
    """Laporan PDF berisi data lengkap satu pengajuan, khusus petugas.

    Ini jalur keluar satu-satunya untuk data kependudukan penuh dalam bentuk
    berkas. Pintunya tiga: harus login, harus petugas (is_officer), dan setiap
    unduhan dicatat ke AuditLog sehingga penggunaan data pribadi bisa ditrace.
    Warga biasa maupun pengunjung anonim yang menebak URL ini dilempar ke
    /login/ oleh user_passes_test, bukan diberi tahu datanya ada.
    """
    item = get_object_or_404(Pengajuan.objects.select_related('penduduk', 'verified_by'), pk=pk)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="laporan-verifikasi-{item.pk}.pdf"'
    # Laporan ini memuat NIK, alamat, dan data OCR warga: jangan pernah boleh
    # tersimpan di cache browser/perantara yang bisa dipakai bersama.
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    pdf_report.bangun(item, request.user, response)
    AuditLog.objects.create(user=request.user, aksi='cetak_laporan',
                            deskripsi=f'Laporan PDF verifikasi pengajuan {item.pk} diunduh.')
    return response


def api_pending_count(request):
    if not is_officer(request.user):
        return JsonResponse({'detail': 'Officer access required'}, status=403)
    return JsonResponse({'count': Pengajuan.objects.filter(status='menunggu').count()})


@throttle_public(limit=120, json_error=True)
def api_landing_stats(request):
    """Statistik publik landing page: hanya agregat, tanpa data pribadi."""
    return JsonResponse(landing_counts(), headers={'Cache-Control': 'no-store'})


def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        return JsonResponse({'status': 'unhealthy', 'database': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'ok'})


def api_status(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)
    person = Penduduk.objects.filter(user=request.user).select_related('pengajuan').first()
    return JsonResponse({'status': person.pengajuan.status if person else None})


@throttle_public(limit=30, json_error=True)
def api_validate_nik(request):
    nik = request.GET.get('nik', '')
    response = {'valid': len(nik) == 16 and nik.isdigit()}
    if request.user.is_authenticated:
        response['registered'] = Penduduk.objects.filter(nik=nik).exists()
    return JsonResponse(response)


def _valid_date(value):
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return False
    return True


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Batas resolusi untuk foto KTP/KK. Berkas di bawah 5 MB tetap bisa mengurai ke
# ratusan megapiksel (decompression bomb) dan menghabiskan memori saat OCR, jadi
# dimensi total dibatasi di sini; 40 MP jauh di atas kebutuhan dokumen pindai.
MAX_IMAGE_PIXELS = 40_000_000


def _valid_upload(uploaded, max_bytes=MAX_UPLOAD_BYTES, *, hanya_gambar=False):
    """Ukuran + ekstensi + isi file harus cocok, dan ClamAV harus bersih.

    Batas ukuran sengaja ada di sini juga (bukan hanya di pemanggil) supaya
    jalur unggah baru tidak lupa memeriksanya. `hanya_gambar` dipakai pasfoto:
    PDF adalah dokumen yang sah untuk KTP/KK, tapi bukan foto. Saat
    CLAMAV_ENABLED aktif tapi server ClamAV tidak bisa dihubungi, hasilya
    ditolak (fail closed) - lebih baik unggahan gagal daripada lolos tanpa
    pemindaian.
    """
    if uploaded.size > max_bytes:
        return False
    name = os.path.basename(uploaded.name or '').lower()
    if hanya_gambar:
        if not name.endswith(('.jpg', '.jpeg', '.png')):
            return False
    elif not name.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
        return False
    uploaded.seek(0)
    header = uploaded.read(8)
    uploaded.seek(0)
    if name.endswith('.pdf'):
        valid = header.startswith(b'%PDF-')
    else:
        valid = False
        try:
            from PIL import Image
            image = Image.open(uploaded)
            image.verify()
            valid = image.format in {'JPEG', 'PNG'}
            if valid:
                # verify() tidak men-decode penuh, jadi buka ulang untuk membaca
                # dimensi dan menolak bomb yang lolos dari batas ukuran byte.
                uploaded.seek(0)
                image = Image.open(uploaded)
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    valid = False
        except Exception:
            valid = False
    if not valid:
        return False
    from django.conf import settings
    if settings.CLAMAV_ENABLED:
        try:
            import clamd
            uploaded.seek(0)
            result = clamd.ClamdNetworkSocket(settings.CLAMAV_HOST, settings.CLAMAV_PORT).instream(uploaded)
            uploaded.seek(0)
            return not result or all(value[0] == 'OK' for value in result.values())
        except Exception:
            return False
    return True


def _parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date() if value else None


@login_required(login_url='/login/')
@user_passes_test(is_officer, login_url='/login/')
def api_ocr_result(request, pk):
    """API endpoint untuk mengambil hasil OCR dari dokumen."""
    dokumen = get_object_or_404(Dokumen, pk=pk)
    
    # Cek permission: hanya petugas atau pemilik yang bisa melihat
    if not is_officer(request.user) and dokumen.penduduk.user != request.user:
        return JsonResponse({'error': 'Akses ditolak'}, status=403)
    
    result = {
        'id': dokumen.id,
        'nama': dokumen.nama,
        'jenis': dokumen.jenis,
        'status': dokumen.status,
        'ocr_text': dokumen.ocr_text or '',
        'ocr_confidence': dokumen.ocr_confidence,
        'extracted_nik': dokumen.extracted_nik,
        'extracted_data': dokumen.extracted_data,
        'ai_verified': dokumen.ai_verified,
        'ai_score': dokumen.ai_score,
        'ai_prescreen': dokumen.ai_prescreen,
        'ai_prescreen_label': dokumen.get_ai_prescreen_display(),
        'ai_verification_notes': dokumen.ai_verification_notes,
        'processed_at': dokumen.ocr_processed_at.isoformat() if dokumen.ocr_processed_at else None,
    }
    
    return JsonResponse(result)


@login_required(login_url='/login/')
@user_passes_test(is_officer, login_url='/login/')
def api_trigger_ocr(request, pk):
    """API endpoint untuk trigger OCR manual pada dokumen."""
    dokumen = get_object_or_404(Dokumen, pk=pk)
    
    # Cek permission
    if not is_officer(request.user):
        return JsonResponse({'error': 'Akses ditolak'}, status=403)
    
    # Trigger OCR di background thread
    threading.Thread(target=_trigger_ocr_async, args=(dokumen.id,), daemon=True).start()
    
    return JsonResponse({
        'status': 'processing',
        'message': 'OCR sedang diproses. Hasil akan tersedia dalam beberapa detik.',
    })


def _format_waktu(nilai):
    """Tanggal/waktu jadi teks singkat, atau '' bila kosong.

    Diformat di sini supaya core.chatbot tetap fungsi murni yang tidak mengenal
    ORM maupun zona waktu.
    """
    if not nilai:
        return ''
    if isinstance(nilai, datetime):
        if timezone.is_aware(nilai):
            nilai = timezone.localtime(nilai)
        return nilai.strftime('%d/%m/%Y %H:%M')
    return nilai.strftime('%d/%m/%Y')


def _konteks_pengajuan(item):
    """Susun satu Pengajuan menjadi konteks datar untuk mesin penjawab."""
    warga = item.penduduk
    dokumen = []
    for berkas in warga.dokumen.all():
        dokumen.append({
            'id': berkas.id,
            'nama': berkas.nama,
            'jenis': berkas.jenis,
            'jenis_label': berkas.get_jenis_display(),
            'status_label': berkas.get_status_display(),
            'confidence': berkas.ocr_confidence,
            'extracted_nik': berkas.extracted_nik,
            'extracted_data': berkas.extracted_data or {},
            'ai_verified': berkas.ai_verified,
            'ai_score': berkas.ai_score,
            'ai_prescreen': berkas.ai_prescreen,
            'ai_verification_notes': berkas.ai_verification_notes,
            # ocr_text terisi hanya setelah proses berjalan, jadi ini penanda
            # "sudah pernah di-OCR" tanpa perlu kolom tambahan.
            'diproses': bool(berkas.ocr_text),
        })
    jenis_ada = {berkas['jenis'] for berkas in dokumen}
    kartu = KartuDigital.objects.filter(penduduk=warga).first()
    return {
        'pengajuan_id': item.pk,
        'status_kode': item.status,
        'status': item.get_status_display(),
        'catatan': item.catatan or '',
        'dikirim': _format_waktu(item.submitted_at),
        'diverifikasi': _format_waktu(item.verified_at),
        'penduduk': {
            'nama': warga.nama,
            'nik': warga.nik,
            'daerah_asal': warga.daerah_asal,
            'kota_tujuan': warga.kota_tujuan,
            'tujuan': warga.tujuan,
            'tanggal_mulai': _format_waktu(warga.tanggal_mulai),
            'perkiraan_kembali': _format_waktu(warga.perkiraan_kembali),
            'nomor_telepon': warga.nomor_telepon or '',
        },
        'dokumen': dokumen,
        'ktp': next((berkas for berkas in dokumen if berkas['jenis'] == 'ktp'), None),
        'kk': next((berkas for berkas in dokumen if berkas['jenis'] == 'kk'), None),
        'kartu': {
            'kode': kartu.kode,
            'berlaku_sampai': _format_waktu(kartu.berlaku_sampai),
            'status': kartu.status,
            'valid': kartu.is_valid(),
        } if kartu else None,
        'lengkap': {'ktp', 'kk'}.issubset(jenis_ada),
    }


@require_POST
@throttle_public(limit=30, window=60, json_error=True)
def api_chat(request):
    """Jawaban Asisten Verifikasi Dokumen dengan dua mesin.

    Mesin utama adalah LLM Gemini (core.llm) bila GEMINI_API_KEY terisi di
    .env; setiap kegagalan — HTTP error, timeout, balasan tak sah — dicatat
    ke AuditLog dan dijawab oleh mesin cadangan rule-based core.chatbot yang
    jalan 100% lokal. Dengan kunci kosong perilakunya persis seperti sebelum
    LLM dipasang. Endpoint khusus petugas, dibatasi 30 permintaan per menit
    per IP, dan hanya menerima POST ber-CSRF (middleware CSRF global yang
    menegakkannya, jadi jangan pernah diberi csrf_exempt).
    """
    if not is_officer(request.user):
        return JsonResponse({'error': 'Akses ditolak'}, status=403)

    try:
        muatan = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        muatan = request.POST
    if not isinstance(muatan, dict):
        muatan = {}

    pesan = str(muatan.get('pesan') or '').strip()
    if not pesan:
        return JsonResponse({'error': 'Pesan tidak boleh kosong.'}, status=400)
    if len(pesan) > chatbot.MAX_PANJANG_PESAN:
        return JsonResponse({'error': f'Pesan terlalu panjang, maksimal {chatbot.MAX_PANJANG_PESAN} karakter.'}, status=400)

    riwayat = muatan.get('riwayat')
    if riwayat is not None and not llm.riwayat_valid(riwayat):
        return JsonResponse({'error': 'riwayat tidak valid.'}, status=400)

    try:
        pengajuan_id = int(muatan.get('pengajuan_id'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'pengajuan_id tidak valid.'}, status=400)

    item = Pengajuan.objects.select_related('penduduk').filter(pk=pengajuan_id).first()
    if item is None:
        return JsonResponse({'error': 'Pengajuan tidak ditemukan.'}, status=404)

    konteks = _konteks_pengajuan(item)
    # Mesin aturan selalu dihitung: saat LLM menjawab, sarannya tetap dari
    # sini supaya chip tindak lanjut tetap kontekstual dan deterministik.
    hasil = chatbot.jawab(pesan, konteks)
    hasil['versi'] = 'aturan-lokal-1'
    if llm.tersedia():
        try:
            hasil['jawaban'] = llm.jawab_llm(pesan, konteks, riwayat or [])
            hasil['kategori'] = 'llm'
            hasil['versi'] = 'gemini'
        except llm.LlmTidakTersedia as galat:
            AuditLog.objects.create(
                user=request.user,
                aksi='chat_llm_gagal',
                deskripsi=f'Gemini gagal pada pengajuan {pengajuan_id}, dipakai cadangan aturan: {galat}',
            )
    return JsonResponse(hasil)


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)
