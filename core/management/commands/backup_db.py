from datetime import datetime
from pathlib import Path
from django.core.management import BaseCommand, call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Export seluruh data Django ke file JSON backup.'

    def add_arguments(self, parser):
        parser.add_argument('--keep', type=int, default=14, help='Jumlah file backup terbaru yang disimpan, sisanya dihapus (default 14).')

    def handle(self, *args, **options):
        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(exist_ok=True)
        filename = backup_dir / f'sipper-{datetime.now():%Y%m%d-%H%M%S}.json'
        # Ditulis sebagai .part lalu diganti nama: backup yang gagal (kredit database
        # habis, koneksi ditolak) tidak boleh menyisakan file setengah jadi yang
        # terlihat seperti cadangan sah.
        partial = filename.with_suffix('.part')
        try:
            # contenttypes dan auth.permission sengaja tidak ikut: keduanya dibuat ulang
            # oleh `migrate`, dan memulihkan versi lama akan menimpa struktur yang baru.
            with partial.open('w', encoding='utf-8') as output:
                call_command('dumpdata', '--natural-foreign', '--natural-primary',
                             '--exclude', 'contenttypes.contenttype', '--exclude', 'auth.permission',
                             indent=2, stdout=output)
            partial.rename(filename)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        self.stdout.write(self.style.SUCCESS(f'Backup dibuat: {filename}'))

        keep = max(options['keep'], 1)
        history = sorted(backup_dir.glob('sipper-*.json'), key=lambda path: path.name)
        for stale in history[:-keep]:
            stale.unlink()
            self.stdout.write(f'Backup lama dibuang: {stale.name}')
