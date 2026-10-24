#!/usr/bin/env python
import os
import sys


def main():
	# Peramban modern menaikkan URL yang diketik tanpa skema menjadi https, jadi `runserver`
	# http polos tidak pernah bisa dibuka di mesin ini. Namanya dialihkan ke runserver_tls
	# (https dengan sertifikat self-signed, lihat core/management/commands/runserver_tls.py)
	# supaya kebiasaan lama `manage.py runserver` langsung menyajikan https://127.0.0.1:8000.
	if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
		sys.argv[1] = 'runserver_tls'
	os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sipper.settings')
	from django.core.management import execute_from_command_line
	execute_from_command_line(sys.argv)


if __name__ == '__main__':
	main()
