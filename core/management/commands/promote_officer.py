from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from core.models import UserRole


class Command(BaseCommand):
    help = 'Set an existing account as a SIPPER officer without changing auth tables.'

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options['username']).first()
        if not user:
            raise CommandError('User tidak ditemukan.')
        UserRole.objects.update_or_create(user=user, defaults={'role': 'petugas'})
        self.stdout.write(self.style.SUCCESS(f'{user.username} sekarang memiliki role petugas.'))
