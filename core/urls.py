from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core'
urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('pemutakhiran/', views.update_data, name='update_data'),
    path('histori/', views.history, name='history'),
    path('daftar/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password/', views.change_password, name='change_password'),
    path('profil/', views.profile, name='profile'),
    path('lupa-password/', auth_views.PasswordResetView.as_view(template_name='password_reset_form.html',
                                                                success_url=reverse_lazy('core:password_reset_done')), name='password_reset'),
    path('lupa-password/terkirim/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset-password/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html',
                                                                                          success_url=reverse_lazy('core:password_reset_complete')), name='password_reset_confirm'),
    path('reset-password/selesai/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('pengajuan/', views.application, name='application'),
    path('pengajuan/<int:pk>/kirim-ulang/', views.resubmit_application, name='resubmit_application'),
    path('petugas/', views.officer, name='officer'),
    path('petugas/pengajuan/<int:pk>/', views.application_detail, name='application_detail'),
    path('petugas/dokumen/<int:pk>/', views.document_review, name='document_review'),
    path('dokumen/<int:pk>/file/', views.document_file, name='document_file'),
    path('petugas/statistik/', views.statistics, name='statistics'),
    path('kartu/', views.card_lookup, name='card_lookup'),
    path('kartu/<str:code>/', views.validate_card, name='validate_card'),
    path('kartu/<str:code>/qr.png', views.card_qr, name='card_qr'),
    path('scan-kartu/', views.scan_card, name='scan_card'),
    path('health/', views.health, name='health'),
    path('kartu/<str:code>/download/', views.download_card, name='download_card'),
    path('api/pending-count/', views.api_pending_count, name='api_pending_count'),
    path('api/landing-stats/', views.api_landing_stats, name='api_landing_stats'),
    path('api/status/', views.api_status, name='api_status'),
    path('api/validate-nik/', views.api_validate_nik, name='api_validate_nik'),
]
