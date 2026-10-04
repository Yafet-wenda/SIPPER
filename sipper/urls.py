from django.urls import include, path
from core.admin_site import sipper_admin

# /media/ sengaja TIDAK pernah disajikan sebagai Alias publik. File warga dilayani
# lewat core.views.document_file yang memeriksa kepemilikan/petugas.
urlpatterns = [path('admin/', sipper_admin.urls), path('', include('core.urls'))]

handler404 = 'core.views.handler404'
handler500 = 'core.views.handler500'
