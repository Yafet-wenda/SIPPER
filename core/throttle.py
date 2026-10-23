"""Batas kasar permintaan per alamat IP untuk endpoint yang terbuka tanpa login.

Dipakai oleh core.views, tapi tidak mengenal ORM maupun view, sehingga modul
lain bisa memakainya tanpa menarik seluruh isi views.py ke dalam memori proses.
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

PUBLIC_LIMIT = 60
PUBLIC_WINDOW = 300


def client_ip(request):
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
            key = f'publik:{func.__name__}:{client_ip(request)}'
            if cache.get(key, 0) >= limit:
                if json_error:
                    response = JsonResponse({'error': 'Terlalu banyak permintaan.'}, status=429)
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
