"""Hak akses petugas, didefinisikan di satu tempat.

Dulu fungsi ini tinggal di core/views.py, sehingga core.context_processors dan
modul lain harus mengimpor seluruh isi views (ORM, chatbot, llm, reportlab)
hanya untuk menanyakan satu hal. Pindah ke sini supaya pertanyaan "apakah akun
ini petugas" bisa dijawab tanpa menarik tumpukan view.
"""
from django.contrib.auth.models import Group, Permission

from .models import UserRole

ADMIN_GROUP_NAME = 'SIPPER Admin'


def sinkronkan_akses_peran(user):
    """Sinkronkan role pilihan dengan akses panel admin Django."""
    if user.is_superuser:
        return

    role = UserRole.objects.filter(user=user).values_list('role', flat=True).first()
    grup_admin = Group.objects.filter(name=ADMIN_GROUP_NAME).first()
    if role == 'admin':
        if grup_admin is None:
            grup_admin = Group.objects.create(name=ADMIN_GROUP_NAME)
        grup_admin.permissions.set(Permission.objects.all())
        user.groups.add(grup_admin)
        is_staff = True
    else:
        if grup_admin is not None:
            user.groups.remove(grup_admin)
        is_staff = False

    if user.is_staff != is_staff:
        user.is_staff = is_staff
        user.save(update_fields=['is_staff'])


def is_officer(user):
    """Akun dianggap petugas bila is_staff ATAU punya UserRole 'petugas'.

    Dua sumber karena petugas bisa lahir dari dua jalan: dibuat di /admin/
    (is_staff) atau diangkat dari akun warga lewat perintah
    promote_officer (UserRole). Menutup salah satu jalur berarti orang yang
    sudah bekerja tidak bisa masuk antrean.
    """
    return user.is_authenticated and (
        user.is_staff or UserRole.objects.filter(
            user=user, role__in=('petugas', 'admin')
        ).exists())
