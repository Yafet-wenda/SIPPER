"""Penanda peran untuk semua template.

Template bertanya "apakah pemanggil ini petugas" di banyak tempat (menu
antrean, tombol khusus petugas). Jawaban dihitung sekali di sini supaya tidak
ada HTML yang menyimpulkan sendiri dari kolom akun.
"""
from .akses import is_officer


def role_flags(request):
    return {'is_sipper_officer': is_officer(request.user)}
