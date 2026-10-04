from datetime import datetime
from pathlib import Path
from django.core.management import BaseCommand, call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Export seluruh data Django ke file JSON backup.'

    def handle(self, *args, **options):
        backup_dir = Path(settings.BASE_DIR) / 'backups'
        backup_dir.mkdir(exist_ok=True)
        filename = backup_dir / f'sipper-{datetime.now():%Y%m%d-%H%M%S}.json'
        with filename.open('w', encoding='utf-8') as output:
            call_command('dumpdata', '--natural-foreign', '--natural-primary', indent=2, stdout=output)
        self.stdout.write(self.style.SUCCESS(f'Backup dibuat: {filename}'))
