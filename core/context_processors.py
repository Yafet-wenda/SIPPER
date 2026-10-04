from .views import is_officer


def role_flags(request):
    return {'is_sipper_officer': is_officer(request.user)}