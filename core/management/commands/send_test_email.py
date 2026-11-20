from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Kirim satu email uji untuk memeriksa backend email.'

    def add_arguments(self, parser):
        parser.add_argument('ke', nargs='?', help='Alamat tujuan. Kosong = email superuser pertama.')

    def handle(self, *args, **options):
        backend_path = settings.EMAIL_BACKEND
        backend = backend_path.rsplit('.', 1)[-1]
        is_console = backend_path.endswith('.console.EmailBackend')
        is_smtp = backend_path.endswith('.smtp.EmailBackend')
        target = options.get('ke') or User.objects.filter(is_superuser=True).order_by('id').values_list('email', flat=True).first()
        if not target:
            self.stderr.write(self.style.ERROR('Tidak ada alamat tujuan dan tidak ada superuser yang punya email.'))
            return
        if is_console:
            self.stdout.write(self.style.WARNING(
                'EMAIL_BACKEND masih console: pesan hanya dicetak, tidak dikirim ke penerima.'
            ))
        sent = send_mail(
            subject='SIPPER: uji jalur email',
            message=(
                'Email ini dikirim oleh perintah `manage.py send_test_email`.\r\n'
                'Pesan ini hanya menguji pengiriman email; tidak memuat data akun atau warga.\r\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[target],
            fail_silently=False,
        )
        if sent and is_smtp:
            self.stdout.write(self.style.SUCCESS(
                'Server SMTP menerima pesan uji. Ini belum membuktikan pesan masuk ke inbox; '
                'periksa Inbox, Spam, dan folder Semua Email.'
            ))
        elif sent and is_console:
            self.stdout.write(self.style.WARNING('Pesan uji ditulis ke konsol; tidak ada email yang dikirim.'))
        elif sent:
            self.stdout.write(self.style.SUCCESS(
                f'Backend {backend} menerima pesan uji; periksa kotak masuk untuk memastikan penerimaan.'
            ))
        else:
            self.stderr.write(self.style.ERROR(f'Backend {backend} tidak menerima pesan uji.'))
