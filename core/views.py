from datetime import timedelta
from datetime import datetime
import mimetypes
import os
from urllib.parse import quote
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import IntegrityError
from django.http import Http404
from django.http import JsonResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db import connection
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.models import User
from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan, Pemutakhiran, UserRole


def is_officer(user):
    return user.is_authenticated and (user.is_staff or UserRole.objects.filter(user=user, role='petugas').exists())


def issue_card(request, person):
    import secrets
    card, _ = KartuDigital.objects.get_or_create(penduduk=person, defaults={'kode': f'SPR-{secrets.token_urlsafe(16)}', 'berlaku_sampai': timezone.now().date() + timedelta(days=365)})
    if not card.qr_code:
        import qrcode
        from django.core.files.base import ContentFile
        from io import BytesIO
        buffer = BytesIO()
        qrcode.make(request.build_absolute_uri(f'/kartu/{card.kode}/')).save(buffer, format='PNG')
        card.qr_code.save(f'{card.kode}.png', ContentFile(buffer.getvalue()), save=True)
    return card


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
    person = get_object_or_404(Penduduk, user=request.user)
    if request.method == 'POST':
        old_data = {'daerah_asal': person.daerah_asal, 'kota_tujuan': person.kota_tujuan, 'tujuan': person.tujuan}
        person.daerah_asal = request.POST.get('origin', '').strip()
        person.kota_tujuan = request.POST.get('destination', '').strip()
        person.tujuan = request.POST.get('purpose', '').strip()
        if not all((person.daerah_asal, person.kota_tujuan, person.tujuan)):
            messages.error(request, 'Semua data pemutakhiran wajib diisi.')
        else:
            person.save(update_fields=['daerah_asal', 'kota_tujuan', 'tujuan'])
            Pemutakhiran.objects.create(penduduk=person, data_lama=old_data, data_baru={'daerah_asal': person.daerah_asal, 'kota_tujuan': person.kota_tujuan, 'tujuan': person.tujuan})
            AuditLog.objects.create(user=request.user, aksi='pemutakhiran', deskripsi=f'Domisili diperbarui ke {person.kota_tujuan}.')
            messages.success(request, 'Data perantauan berhasil diperbarui.')
            return redirect('core:dashboard')
    return render(request, 'update_data.html', {'person': person})


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
        throttle_key = f'login-fail:{request.META.get("REMOTE_ADDR", "unknown")}:{identifier.lower()}'
        if cache.get(throttle_key, 0) >= 5:
            messages.error(request, 'Terlalu banyak percobaan. Coba lagi dalam 15 menit.')
            return render(request, 'login.html')
        account = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        user = authenticate(request, username=account.username if account else identifier, password=request.POST.get('password', ''))
        if user:
            cache.delete(throttle_key)
            login(request, user)
            return redirect('core:officer' if is_officer(user) else 'core:dashboard')
        cache.set(throttle_key, cache.get(throttle_key, 0) + 1, 900)
        messages.error(request, 'Email atau password tidak sesuai.')
    return render(request, 'login.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('core:home')


@login_required(login_url='/login/')
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
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


def application(request):
    if not request.user.is_authenticated:
        return redirect('core:login')
    if request.method == 'POST':
        data = {key: request.POST.get(key, '').strip() for key in ('name', 'nik', 'origin', 'destination', 'purpose', 'phone', 'tanggal_mulai', 'perkiraan_kembali')}
        if len(data['nik']) != 16 or not data['nik'].isdigit():
            messages.error(request, 'NIK harus terdiri dari tepat 16 digit angka.')
        elif data['phone'] and (not data['phone'].isdigit() or not 10 <= len(data['phone']) <= 15):
            messages.error(request, 'Nomor telepon harus 10-15 digit.')
        elif not all(data[key] for key in ('name', 'nik', 'origin', 'destination', 'purpose')):
            messages.error(request, 'Lengkapi seluruh data pengajuan.')
        elif any(data[key] and not _valid_date(data[key]) for key in ('tanggal_mulai', 'perkiraan_kembali')):
            messages.error(request, 'Format tanggal perjalanan tidak valid.')
        elif Penduduk.objects.filter(nik=data['nik']).exists():
            messages.error(request, 'NIK tersebut sudah terdaftar.')
        else:
            try:
                person = Penduduk.objects.create(user=request.user, nama=data['name'], nik=data['nik'], nomor_telepon=data['phone'], tanggal_mulai=_parse_date(data['tanggal_mulai']), perkiraan_kembali=_parse_date(data['perkiraan_kembali']), daerah_asal=data['origin'], kota_tujuan=data['destination'], tujuan=data['purpose'])
                Pengajuan.objects.create(penduduk=person)
                uploaded = request.FILES.get('document')
                if uploaded:
                    if uploaded.size > 5 * 1024 * 1024:
                        person.delete()
                        messages.error(request, 'Ukuran dokumen maksimal 5 MB.')
                        return render(request, 'application_v3.html', {'name': request.user.first_name})
                    if not _valid_upload(uploaded):
                        person.delete()
                        messages.error(request, 'Dokumen harus berformat PDF, JPG, atau PNG.')
                        return render(request, 'application_v3.html', {'name': request.user.first_name})
                    Dokumen.objects.create(penduduk=person, nama=uploaded.name, file=uploaded, ukuran=uploaded.size)
                AuditLog.objects.create(user=request.user, aksi='pengajuan', deskripsi=f'Pengajuan dibuat untuk {person.nama}.')
            except IntegrityError:
                messages.error(request, 'NIK tersebut sudah terdaftar.')
                return render(request, 'application_v3.html', {'name': request.user.first_name})
            messages.success(request, 'Pengajuan tersimpan dan masuk antrean verifikasi.')
            return redirect('core:dashboard')
    return render(request, 'application_v3.html', {'name': request.user.first_name})


@login_required(login_url='/login/')
def resubmit_application(request, pk):
    item = get_object_or_404(Pengajuan.objects.select_related('penduduk'), pk=pk, penduduk__user=request.user)
    if request.method != 'POST':
        return redirect('core:dashboard')
    if item.status not in {'perlu_perbaikan', 'ditolak'}:
        messages.error(request, 'Pengajuan ini belum dapat dikirim ulang.')
    else:
        uploaded = request.FILES.get('document')
        if uploaded and (uploaded.size > 5 * 1024 * 1024 or not _valid_upload(uploaded)):
            messages.error(request, 'Dokumen baru harus PDF, JPG, atau PNG dan maksimal 5 MB.')
            return redirect('core:dashboard')
        item.status = 'menunggu'
        item.catatan = ''
        item.save(update_fields=['status', 'catatan'])
        if uploaded:
            Dokumen.objects.create(penduduk=item.penduduk, nama=uploaded.name, file=uploaded, ukuran=uploaded.size)
        AuditLog.objects.create(user=request.user, aksi='kirim_ulang', deskripsi=f'Pengajuan {item.penduduk.nama} dikirim ulang.')
        messages.success(request, 'Pengajuan berhasil dikirim ulang untuk ditinjau.')
    return redirect('core:dashboard')


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
            writer.writerow([item.penduduk.nama, item.penduduk.nik, item.penduduk.daerah_asal, item.penduduk.kota_tujuan, item.penduduk.tujuan, item.get_status_display(), item.submitted_at.isoformat()])
        return response
    if request.method == 'POST':
        item = get_object_or_404(Pengajuan, pk=request.POST.get('id'))
        requested_status = request.POST.get('status', 'menunggu')
        if requested_status not in dict(Pengajuan.STATUS):
            messages.error(request, 'Status verifikasi tidak valid.')
            return redirect('core:officer')
        item.status = requested_status
        item.verified_by = request.user
        item.verified_at = timezone.now()
        item.save(update_fields=['status', 'verified_by', 'verified_at'])
        if item.status == 'disetujui':
            issue_card(request, item.penduduk)
        AuditLog.objects.create(user=request.user, aksi='verifikasi', deskripsi=f'Status {item.penduduk.nama} menjadi {item.get_status_display()}.')
        messages.success(request, f'Status {item.penduduk.nama} diperbarui.')
    page = Paginator(applications, 10).get_page(request.GET.get('page'))
    return render(request, 'officer.html', {'applications': page, 'query': query, 'selected_status': status, 'page_obj': page})


@user_passes_test(is_officer, login_url='/login/')
def application_detail(request, pk):
    item = get_object_or_404(Pengajuan.objects.select_related('penduduk'), pk=pk)
    if request.method == 'POST':
        status = request.POST.get('status', '')
        note = request.POST.get('catatan', '').strip()
        if status not in dict(Pengajuan.STATUS):
            messages.error(request, 'Status verifikasi tidak valid.')
        else:
            item.status = status
            item.catatan = note
            item.verified_by = request.user
            item.verified_at = timezone.now()
            item.save(update_fields=['status', 'catatan', 'verified_by', 'verified_at'])
            AuditLog.objects.create(user=request.user, aksi='verifikasi', deskripsi=f'Detail pengajuan {item.penduduk.nama} diperbarui.')
            if status == 'disetujui':
                issue_card(request, item.penduduk)
            messages.success(request, 'Detail pengajuan berhasil diperbarui.')
            return redirect('core:application_detail', pk=item.pk)
    return render(request, 'application_detail_v2.html', {'item': item, 'documents': item.penduduk.dokumen.all()})


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


def card_qr(request, code):
    """Gambar QR kartu. Isinya hanya URL validasi yang memang sudah publik di halaman kartu."""
    card = get_object_or_404(KartuDigital, kode=code)
    if not card.qr_code:
        raise Http404('File tidak ditemukan.')
    return _serve_file(card.qr_code)


@login_required(login_url='/login/')
def history(request):
    person = get_object_or_404(Penduduk, user=request.user)
    return render(request, 'history.html', {'updates': person.riwayat_pemutakhiran.all(), 'logs': AuditLog.objects.filter(user=request.user).order_by('-created_at')[:30]})


def scan_card(request):
    return render(request, 'scan_card.html')


@user_passes_test(is_officer, login_url='/login/')
def statistics(request):
    by_status = list(Pengajuan.objects.values('status').annotate(total=Count('id')))
    by_destination = list(Penduduk.objects.values('kota_tujuan').annotate(total=Count('id')).order_by('-total')[:8])
    maximum = max([row['total'] for row in by_destination] or [1])
    return render(request, 'statistics_chart.html', {'by_status': by_status, 'by_destination': by_destination, 'maximum': maximum, 'total': Penduduk.objects.count(), 'approved': Pengajuan.objects.filter(status='disetujui').count()})


def validate_card(request, code):
    card = KartuDigital.objects.select_related('penduduk').filter(kode=code).first()
    if not card:
        raise Http404('Kartu tidak ditemukan')
    if card.status == 'aktif' and card.berlaku_sampai < timezone.now().date():
        card.status = 'expired'
        card.save(update_fields=['status'])
    return render(request, 'card_v2.html', {'card': card, 'valid': card.is_valid()})


def card_lookup(request):
    code = request.GET.get('code', '').strip()
    if not code:
        return redirect('core:home')
    return redirect('core:validate_card', code=code)


def download_card(request, code):
    card = get_object_or_404(KartuDigital.objects.select_related('penduduk'), kode=code)
    if not request.user.is_authenticated or (not is_officer(request.user) and card.penduduk.user_id != request.user.id):
        return redirect('core:login')
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from django.http import HttpResponse
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="kartu-{card.kode}.pdf"'
    document = canvas.Canvas(response, pagesize=A4)
    document.setFillColor(colors.HexColor('#1f6b58'))
    document.roundRect(70, 570, 455, 170, 12, fill=1, stroke=0)
    document.setFillColor(colors.white)
    document.setFont('Helvetica-Bold', 18)
    document.drawString(95, 700, 'SIPPER')
    document.setFont('Helvetica', 9)
    document.drawString(95, 680, 'IDENTITAS PENDUDUK PERANTAUAN')
    document.setFont('Helvetica-Bold', 20)
    document.drawString(95, 635, card.penduduk.nama)
    document.setFont('Helvetica', 10)
    document.drawString(95, 612, f'NIK  {card.penduduk.nik}')
    document.drawString(95, 592, f'Domisili  {card.penduduk.kota_tujuan}')
    document.setFillColor(colors.HexColor('#18312b'))
    document.setFont('Helvetica-Bold', 11)
    document.drawString(95, 530, f'Kode validasi: {card.kode}')
    document.setFont('Helvetica', 10)
    document.drawString(95, 510, f'Berlaku sampai: {card.berlaku_sampai.strftime("%d %B %Y")}')
    if card.qr_code and card.qr_code.path:
        from reportlab.lib.utils import ImageReader
        document.drawImage(ImageReader(card.qr_code.path), 405, 590, width=95, height=95, preserveAspectRatio=True, mask='auto')
    document.drawString(95, 480, 'Kartu digital ini bukan pengganti dokumen kependudukan resmi.')
    document.save()
    return response


def api_pending_count(request):
    if not is_officer(request.user):
        return JsonResponse({'detail': 'Officer access required'}, status=403)
    return JsonResponse({'count': Pengajuan.objects.filter(status='menunggu').count()})


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


def _valid_upload(uploaded):
    name = uploaded.name.lower()
    if not name.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
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


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)
