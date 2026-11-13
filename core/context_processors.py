"""Penanda peran untuk semua template.

Template bertanya "apakah pemanggil ini petugas" di banyak tempat (menu
antrean, tombol khusus petugas). Jawaban dihitung sekali di sini supaya tidak
ada HTML yang menyimpulkan sendiri dari kolom akun.
"""
from .akses import is_officer
from .llm import ocr_vision_tersedia


def role_flags(request):
    return {
        'is_sipper_officer': is_officer(request.user),
        'gemini_ocr_available': ocr_vision_tersedia(),
    }
