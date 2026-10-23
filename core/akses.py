"""Hak akses petugas, didefinisikan di satu tempat.

Dulu fungsi ini tinggal di core/views.py, sehingga core.context_processors dan
modul lain harus mengimpor seluruh isi views (ORM, chatbot, llm, reportlab)
hanya untuk menanyakan satu hal. Pindah ke sini supaya pertanyaan "apakah akun
ini petugas" bisa dijawab tanpa menarik tumpukan view.
"""
from .models import UserRole


def is_officer(user):
    """Akun dianggap petugas bila is_staff ATAU punya UserRole 'petugas'.

    Dua sumber karena petugas bisa lahir dari dua jalan: dibuat di /admin/
    (is_staff) atau diangkat dari akun warga lewat perintah
    promote_officer (UserRole). Menutup salah satu jalur berarti orang yang
    sudah bekerja tidak bisa masuk antrean.
    """
    return user.is_authenticated and (
        user.is_staff or UserRole.objects.filter(user=user, role='petugas').exists())
