"""Seluruh halaman dan endpoint JSON SIPPER.

Aturan rumahnya: view hanya memutuskan SIAPA yang boleh dan APA yang dibalas.
Cara menghitung hal lain punya modulnya sendiri - hak akses petugas di
core.akses, pembatas IP di core.throttle, aturan berkas di core.uploads,
OCR di core.ocr_worker, kartu PDF di core.kartu_pdf, laporan PDF di
core.pdf_report, dan keputusan status di core.keputusan.
"""
from datetime import datetime
import json
import mimetypes
import os
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
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from . import chatbot, kartu_pdf, llm, pdf_report
from .akses import is_officer
from .csv_utils import sel_aman, waktu_wib
from .keputusan import terapkan_status
from .models import AuditLog, Dokumen, KartuDigital, Penduduk, Pengajuan, Pemutakhiran, UserRole
from .ocr_worker import picu_async
from .throttle import client_ip, throttle_public
from .uploads import (GAMBAR_SAJA, LAMPILAN_UPLOAD, MAX_UPLOAD_BYTES,
                      SEMUA_LAMPILAN, valid_upload)


# Keputusan yang merugikan warga harus menyertakan alasan. Menolak atau meminta
# perbaikan tanpa catatan membuat warga tidak tahu apa yang harus diperbaiki
# (laporan §6.4), dan tombol kirim ulang hanya terbuka untuk dua status ini.
STATUS_WAJIB_CATATAN = {'ditolak', 'perlu_perbaikan'}
STATUS_BISA_KIRIM_ULANG = {'perlu_perbaikan', 'ditolak'}


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
    # is_officer, bukan is_staff: petugas bisa diangkat lewat UserRole
    # (promote_officer) tanpa pernah jadi staf admin. Dengan is_staff, akun
    # semacam ini melihat seluruh pengajuan warga di dasbornya sendiri.
    if not is_officer(request.user):
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
        throttle_key = f'login-fail:{client_ip(request)}:{identifier.lower()}'
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
            messages.error(request, f'Ukuran {label.lower()} maksimal {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
            return label
        if not valid_upload(uploaded, hanya_gambar=hanya_gambar):
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
                    picu_async(doc.id)
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
    if item.status not in STATUS_BISA_KIRIM_ULANG:
        messages.error(request, 'Pengajuan ini belum dapat dikirim ulang.')
    else:
        files = {field: request.FILES.get(field) for field, _ in SEMUA_LAMPILAN}
        if _validate_lampiran(request, files):
            return redirect('core:dashboard')
        # Sengaja tidak lewat terapkan_status: fungsi itu mencatat siapa petugas
        # yang memverifikasi dan mengirim surat keputusan, sedangkan di sini yang
        # bergerak warga yang melengkapi berkasnya sendiri.
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
                picu_async(existing.id)
                # Penggantian FileField tidak menghapus berkas lama, jadi
                # dibersihkan sendiri supaya folder media tidak menumpuk scan
                # warga yang sudah tidak dipakai.
                default_storage.delete(nama_lama)
            else:
                doc = Dokumen.objects.create(penduduk=item.penduduk, jenis=field, nama=os.path.basename(uploaded.name), file=uploaded, ukuran=uploaded.size)
                picu_async(doc.id)
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
        writer.writerow(['Nama', 'NIK', 'Asal', 'Tujuan', 'Alasan', 'Status', 'Dikirim (WIB)'])
        for item in applications:
            writer.writerow([sel_aman(item.penduduk.nama), item.penduduk.nik, sel_aman(item.penduduk.daerah_asal),
                             sel_aman(item.penduduk.kota_tujuan), sel_aman(item.penduduk.tujuan),
                             item.get_status_display(), waktu_wib(item.submitted_at)])
        return response
    if request.method == 'POST':
        # Kolom id datang dari tombol form. Nilai yang bukan angka membuat
        # get_object_or_404 melempar ValueError, bukan 404, sehingga petugas
        # melihat halaman galat alih-alih pesan yang bisa dibaca.
        try:
            id_diminta = int(request.POST.get('id', ''))
        except (TypeError, ValueError):
            id_diminta = None
        item = Pengajuan.objects.filter(pk=id_diminta).first() if id_diminta else None
        requested_status = request.POST.get('status', 'menunggu')
        catatan = request.POST.get('catatan', '').strip()
        if item is None:
            messages.error(request, 'Pengajuan yang akan diputuskan tidak ditemukan.')
        elif requested_status not in dict(Pengajuan.STATUS):
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
    # Satu perintah UPDATE untuk dua keperluan: memeriksa dan menyimpan. Nilai di
    # objek ikut diselaraskan supaya template melihat kartu yang sudah kedaluwarsa,
    # bukan salinan lama dari awal permintaan.
    if KartuDigital.lewat_tempo().filter(pk=card.pk).update(status='expired'):
        card.status = 'expired'
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
    return render(request, 'card_v2.html', {'card': card, 'valid': card.is_valid(), 'pengajuan_id': pengajuan_id, 'boleh_lihat_foto': boleh_lihat_foto, 'batasan': kartu_pdf.KARTU_BATASAN})


@throttle_public
def card_lookup(request):
    code = request.GET.get('code', '').strip()
    if not code:
        return redirect('core:home')
    return redirect('core:validate_card', code=code)


@throttle_public(limit=20)
def download_card(request, code):
    """Unduh kartu PDF milik sendiri (atau kartu warga yang sedang dipegang).

    Halaman kartu menampilkan kartunya di browser; berkasnya hanya dibuat untuk
    akun yang berhak, dan penggambarannya ada di core.kartu_pdf.
    """
    card = get_object_or_404(KartuDigital.objects.select_related('penduduk'), kode=code)
    if not request.user.is_authenticated or (not is_officer(request.user) and card.penduduk.user_id != request.user.id):
        return redirect('core:login')
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="kartu-{card.kode}.pdf"'
    response['Cache-Control'] = 'no-store'
    kartu_pdf.bangun(card, response)
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
    """Jumlah pengajuan yang menunggu, untuk badge antrean petugas.

    Ditolak dengan 403, bukan dialihkan ke halaman masuk: pemanggilnya skrip di
    halaman petugas, dan sebuah tautan HTML tidak bisa dibaca sebagai JSON.
    """
    if not is_officer(request.user):
        return JsonResponse({'error': 'Akses khusus petugas.'}, status=403)
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


@throttle_public(limit=30, json_error=True)
def api_validate_nik(request):
    """Format NIK: 16 digit angka atau tidak.

    Untuk akun biasa hanya bentuknya yang dijawab. Kepastian "NIK ini sudah
    terdaftar" diberikan kepada siapa pun yang bisa masuk membuat basis data
    penduduk bisa ditambang nomor demi nomor (akun warga dibuat sendiri lewat
    /daftar/, jadi pintu masuknya terbuka); kepastian itu hanya dipakai petugas
    yang sedang memeriksa berkas.
    """
    nik = request.GET.get('nik', '')
    jawaban = {'valid': len(nik) == 16 and nik.isdigit()}
    if is_officer(request.user):
        jawaban['registered'] = Penduduk.objects.filter(nik=nik).exists()
    return JsonResponse(jawaban)


def _valid_date(value):
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return False
    return True


def _parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date() if value else None


@login_required(login_url='/login/')
@user_passes_test(is_officer, login_url='/login/')
def api_ocr_result(request, pk):
    """Hasil OCR satu dokumen untuk panel review petugas.

    Jalan masuknya hanya petugas: pembacaan mesin atas KTP warga dipakai di
    halaman detail pengajuan, bukan untuk dibagikan ke akun warga lewat API.
    """
    dokumen = get_object_or_404(Dokumen, pk=pk)
    return JsonResponse({
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
    })


@require_POST
@user_passes_test(is_officer, login_url='/login/')
def api_trigger_ocr(request, pk):
    """Mulai ulang OCR atas satu dokumen. Hanya POST, dari halaman detail pengajuan.

    require POST karena pekerjaan ini mengubah isi basis data dan menghabiskan CPU
    dua benang OCR: lewat GET, gambar <img src=".../api/trigger-ocr/7/"> di halaman
    lain bisa memicunya atas nama petugas yang sedang masuk.
    """
    dokumen = get_object_or_404(Dokumen, pk=pk)
    picu_async(dokumen.id)
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
