"""Batas ukuran badan permintaan sebelum Django mulai membacanya.

Apache tidak menegakkan LimitRequestBody pada permintaan yang diteruskan ke
Waitress, dan Django sendiri baru menolak file terlalu besar setelah file itu
singgah ke disk. Middleware ini memotong lebih awal lewat Content-Length.
"""

from django.http import HttpResponse

from .uploads import MAX_UPLOAD_BYTES, SEMUA_LAMPILAN

# Sedikit di atas batas aplikasi supaya pengguna masih mendapat pesan "maksimal
# 5 MB per berkas", bukan 413 kosong dari server. Jatahnya dikalikan jumlah slot
# unggah pada form pengajuan (KTP, KK, dan pasfoto bisa dikirim bersamaan),
# bukan satu berkas.
HARD_LIMIT_BYTES = MAX_UPLOAD_BYTES * len(SEMUA_LAMPILAN) + 3 * 1024 * 1024


class MaxUploadSizeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            length = 0
        if length > HARD_LIMIT_BYTES:
            response = HttpResponse(f'Ukuran kiriman terlalu besar. Setiap dokumen maksimal {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.', status=413)
            response['Content-Type'] = 'text/plain; charset=utf-8'
            return response
        return self.get_response(request)
