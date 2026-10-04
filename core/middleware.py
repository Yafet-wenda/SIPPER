"""Batas ukuran badan permintaan sebelum Django mulai membacanya.

Apache tidak menegakkan LimitRequestBody pada permintaan yang diteruskan ke
Waitress, dan Django sendiri baru menolak file terlalu besar setelah file itu
singgah ke disk. Middleware ini memotong lebih awal lewat Content-Length.
"""

from django.http import HttpResponse

from .views import MAX_UPLOAD_BYTES

# Sedikit di atas batas aplikasi supaya pengguna masih mendapat pesan "maksimal 5 MB",
# bukan 413 kosong dari server.
HARD_LIMIT_BYTES = MAX_UPLOAD_BYTES + 3 * 1024 * 1024


class MaxUploadSizeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            length = int(request.META.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            length = 0
        if length > HARD_LIMIT_BYTES:
            response = HttpResponse('Ukuran kiriman terlalu besar. Dokumen maksimal 5 MB.', status=413)
            response['Content-Type'] = 'text/plain; charset=utf-8'
            return response
        return self.get_response(request)
