from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Kirim satu email uji untuk membuktikan jalur SMTP benar-benar bekerja.'

    def add_arguments(self, parser):
        parser.add_argument('ke', nargs='?', help='Alamat tujuan. Kosong = email superuser pertama.')

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND.rsplit('.', 1)[-1]
        target = options.get('ke') or User.objects.filter(is_superuser=True).order_by('id').values_list('email', flat=True).first()
        if not target:
            self.stderr.write(self.style.ERROR('Tidak ada alamat tujuan dan tidak ada superuser yang punya email.'))
            return
        if backend == 'console':
            self.stdout.write(self.style.WARNING('EMAIL_BACKEND masih console: email hanya dicetak, tidak benar-benar terkirim.'))
        sent = send_mail(
            subject='SIPPER: uji jalur email',
            message=(
                'Email ini dikirim oleh perintah `manage.py send_test_email`.\r\n'
                'Kalau Anda membacanya di inbox, berarti notifikasi status dan '
                'link reset password SIPPER (/lupa-password/) sudah bisa dipakai.\r\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[target],
            fail_silently=False,
        )
        if sent:
            self.stdout.write(self.style.SUCCESS(f'Terkirim ke {target} lewat backend {backend}.'))
        else:
            self.stderr.write(self.style.ERROR(f'Backend {backend} menolak mengirim ke {target}.'))
