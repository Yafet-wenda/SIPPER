import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any engine decision so both this module and settings.py
# see the same DB_ENGINE value.
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

if os.getenv('DB_ENGINE', 'mysql').lower().startswith('mysql'):
    import pymysql

    pymysql.install_as_MySQLdb()

    # XAMPP ships MariaDB 10.4, while Django 5.2 gates MySQL support at 10.5.
    # SIPPER only relies on features 10.4 already provides (utf8mb4,
    # STRICT_TRANS_TABLES, InnoDB transactions), so lower the gate to 10.4.
    # MariaDB 10.5 is the first release with INSERT ... RETURNING, which the
    # MySQL backend assumes for every MariaDB — disable it so Django falls
    # back to lastrowid. Remove this shim if XAMPP is upgraded to a
    # MariaDB >= 10.5 bundle.
    from django.db.backends.mysql.features import DatabaseFeatures

    DatabaseFeatures.minimum_database_version = property(lambda self: (10, 4))
    DatabaseFeatures.can_return_columns_from_insert = False
    DatabaseFeatures.can_return_rows_from_bulk_insert = False
