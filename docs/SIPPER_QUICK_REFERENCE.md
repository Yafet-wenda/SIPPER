# SIPPER - Quick Reference & Resources

---

## ⚡ Quick Commands Reference

### Virtual Environment
```bash
# Create
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Deactivate
deactivate
```

### Django Management
```bash
# Create project
django-admin startproject sipper_config .

# Create app
python manage.py startapp app_name

# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static
python manage.py collectstatic --noinput

# Run server
python manage.py runserver

# Run tests
python manage.py test

# Shell
python manage.py shell
```

### Git Commands
```bash
# Initialize
git init

# Add files
git add .
git add filename

# Commit
git commit -m "message"

# Push
git push origin main

# Pull
git pull origin main

# Create branch
git checkout -b branch-name

# Switch branch
git checkout branch-name

# Merge
git merge branch-name

# View status
git status

# View log
git log --oneline
```

### MySQL Commands
```bash
# Login
mysql -u root -p

# Show databases
SHOW DATABASES;

# Create database
CREATE DATABASE sipper_db;

# Use database
USE sipper_db;

# Show tables
SHOW TABLES;

# Backup
mysqldump -u user -p database > backup.sql

# Restore
mysql -u user -p database < backup.sql
```

---

## 📱 File Structure Quick Map

```
sipper-app/
├── sipper_config/          # Main Django config
│   ├── settings.py         # Configuration
│   ├── urls.py             # URL routing
│   └── wsgi.py             # Server entry
├── core/                   # Core app
│   ├── models.py           # Database models
│   ├── views.py            # View logic
│   ├── forms.py            # Form validation
│   └── urls.py             # App URLs
├── users/                  # User authentication
├── perantau/               # Perantau (citizen) features
├── verifikasi/             # Verification (admin) features
├── kartu/                  # Digital card features
├── templates/              # HTML templates
├── static/                 # CSS, JS, Images
│   ├── css/style.css       # Green theme
│   ├── js/main.js          # JavaScript
│   └── img/                # Images
├── media/                  # User uploaded files
├── manage.py               # Django CLI
├── requirements.txt        # Dependencies
└── .env                    # Environment variables
```

---

## 🎨 Color Palette Quick Reference

| Color | Hex Code | Usage |
|-------|----------|-------|
| Primary Dark | #065f46 | Headers, Navbar, Sidebar |
| Primary | #10b981 | Buttons, Links, Accents |
| Primary Light | #d1fae5 | Card Headers, Backgrounds |
| Primary Lighter | #f0fdf4 | Light Backgrounds |
| Secondary | #059669 | Hover States |
| Success | #10b981 | Positive Actions |
| Danger | #dc2626 | Destructive Actions |
| Warning | #f59e0b | Warnings |
| Info | #0ea5e9 | Information |
| Dark | #1e293b | Text |
| Light | #f8fafc | Backgrounds |
| Muted | #64748b | Secondary Text |

---

## 📚 Model Relationships

```python
# User Model Diagram
User (1) ──→ (1) Penduduk
  ↓
User (1) ──→ (0..n) AuditLog

# Penduduk Relationships
Penduduk (1) ──→ (1) Pengajuan
Penduduk (1) ──→ (0..n) Dokumen
Penduduk (1) ──→ (1) KartuDigital
Penduduk (1) ──→ (0..n) Pemutakhiran

# Pengajuan Relationships
Pengajuan ──→ Penduduk
Pengajuan ──→ User (verified_by)
```

---

## 🔑 Important Field Validations

| Field | Validation | Length |
|-------|-----------|--------|
| NIK | Numeric only | 16 digits |
| Email | Valid email format | 254 chars |
| Password | Min 8 chars | 255 chars |
| Phone | 10-15 digits | 15 chars |
| File Upload | PDF/JPG/PNG | Max 5MB |
| Text Fields | UTF-8 compatible | Varies |

---

## 🌐 API Endpoints

### Authentication
```
POST   /auth/login/           - User login
POST   /auth/register/        - User registration
GET    /auth/logout/          - User logout
GET    /auth/profile/         - User profile
```

### Perantau (Citizen)
```
GET    /perantau/dashboard/   - Dashboard
GET    /perantau/pendaftaran/ - Registration form
POST   /perantau/pendaftaran/ - Submit registration
GET    /perantau/edit/<id>/   - Edit data
POST   /perantau/edit/<id>/   - Update data
GET    /perantau/dokumen/     - List documents
POST   /perantau/dokumen/     - Upload document
```

### Verifikasi (Admin)
```
GET    /verifikasi/dashboard/        - Admin dashboard
GET    /verifikasi/pengajuan/        - List applications
GET    /verifikasi/pengajuan/<id>/   - View application detail
POST   /verifikasi/pengajuan/<id>/   - Verify/Reject
GET    /verifikasi/statistik/        - Statistics
```

### Kartu Digital
```
GET    /kartu/view/           - View digital card
GET    /kartu/validate/<code>/ - Validate card
```

### API (JSON)
```
GET    /api/pending-count/    - Get pending count
GET    /api/perantau/status/  - Get application status
GET    /api/chart-data/       - Get chart data
POST   /api/validate-nik/     - Validate NIK
```

---

## 🐍 Python/Django Versions

| Component | Recommended | Minimum |
|-----------|------------|---------|
| Python | 3.11+ | 3.10 |
| Django | 4.2+ | 4.2 |
| MySQL | 8.0+ | 5.7 |
| Bootstrap | 5.3+ | 5.1 |

---

## 📦 Key Dependencies

```
Django==4.2.0
mysqlclient==2.2.0
python-decouple==3.8
Pillow==10.0.0
qrcode==7.4.2
django-crispy-forms==2.1
crispy-bootstrap5==0.7
python-dotenv==1.0.0
requests==2.31.0
gunicorn==21.2.0
```

---

## 🔐 Security Best Practices

### Authentication
- [ ] Use strong passwords (min 8 chars)
- [ ] Enable HTTPS in production
- [ ] Use secure session cookies
- [ ] Implement CSRF protection

### Database
- [ ] Use parameterized queries (Django ORM)
- [ ] Regularly backup database
- [ ] Use strong database passwords
- [ ] Limit database user privileges

### Files
- [ ] Validate file uploads
- [ ] Store uploads outside web root
- [ ] Set appropriate file permissions
- [ ] Scan uploads for malware

### Code
- [ ] Keep dependencies updated
- [ ] Use environment variables for secrets
- [ ] Enable security headers
- [ ] Use Content Security Policy

---

## 📊 Useful Django Utilities

### QuerySet Operations
```python
# Filter
Penduduk.objects.filter(status='aktif')

# Exclude
Penduduk.objects.exclude(status='pulang')

# Get
penduduk = Penduduk.objects.get(nik='1234567890123456')

# All
semua = Penduduk.objects.all()

# Count
total = Penduduk.objects.count()

# Exists
exists = Penduduk.objects.filter(nik='xxx').exists()

# First/Last
first = Penduduk.objects.first()
last = Penduduk.objects.last()

# Aggregate
from django.db.models import Count
stats = Penduduk.objects.aggregate(total=Count('id'))

# Distinct
unique_provinsi = Penduduk.objects.values('provinsi_tujuan').distinct()
```

### Template Tags
```html
<!-- Conditionals -->
{% if user.is_authenticated %}
  <p>Welcome {{ user.first_name }}</p>
{% endif %}

<!-- Loops -->
{% for item in items %}
  <p>{{ item }}</p>
{% endfor %}

<!-- Filters -->
{{ text|lower }}
{{ value|add:"10" }}
{{ date|date:"Y-m-d" }}

<!-- Static files -->
{% load static %}
<img src="{% static 'img/logo.png' %}">

<!-- URLs -->
<a href="{% url 'app:view_name' pk=item.id %}">Link</a>

<!-- CSRF -->
{% csrf_token %}
```

---

## 🐛 Debugging Tips

### Print Statements
```python
# In views
print("Debug:", variable)

# Better - use logging
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message: %s", variable)
```

### Django Shell
```bash
python manage.py shell

# Then
>>> from core.models import Penduduk
>>> p = Penduduk.objects.first()
>>> print(p.nama)
>>> p.status
>>> p.pengajuan
```

### Check Queries
```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as ctx:
    # Your code here
    pass

print(f"Queries: {len(ctx)}")
for query in ctx:
    print(query)
```

---

## 🔗 External Resources

### Django Documentation
- **Official Docs**: https://docs.djangoproject.com/
- **Django Packages**: https://djangopackages.org/
- **Django REST Framework**: https://www.django-rest-framework.org/

### Frontend Resources
- **Bootstrap 5**: https://getbootstrap.com/
- **Font Awesome**: https://fontawesome.com/
- **Can I Use**: https://caniuse.com/

### MySQL Resources
- **MySQL Docs**: https://dev.mysql.com/doc/
- **MySQL Workbench**: https://www.mysql.com/products/workbench/

### Python/Testing
- **Python Docs**: https://docs.python.org/3/
- **Pytest**: https://docs.pytest.org/
- **Coverage.py**: https://coverage.readthedocs.io/

### Deployment
- **Gunicorn**: https://gunicorn.org/
- **Nginx**: https://nginx.org/
- **Let's Encrypt**: https://letsencrypt.org/
- **DigitalOcean**: https://www.digitalocean.com/

### Development Tools
- **VS Code**: https://code.visualstudio.com/
- **PyCharm Community**: https://www.jetbrains.com/pycharm/
- **Git**: https://git-scm.com/
- **Postman**: https://www.postman.com/

---

## 📞 Getting Help

### Documentation Locations
- **Main Docs**: `/docs/` directory in project
- **API Docs**: `/docs/api.md`
- **Setup Guide**: `/docs/SETUP.md`
- **Deployment**: `/docs/DEPLOYMENT.md`

### Common Issues Resolution
```
404 Not Found → Check urls.py routing
Template Not Found → Check TEMPLATES in settings.py
ModuleNotFoundError → Check pip install and virtual env
Database Error → Check .env DB credentials
Static files missing → Run collectstatic
```

### Team Communication
- **Code Issues**: Use GitHub Issues
- **Documentation**: Update README.md
- **Pull Requests**: Follow conventional commits
- **Discussions**: Use GitHub Discussions

---

## 📋 Development Workflow

### Daily Workflow
1. Pull latest code: `git pull origin main`
2. Activate environment: `source venv/bin/activate`
3. Run migrations: `python manage.py migrate`
4. Start server: `python manage.py runserver`
5. Make changes
6. Run tests: `python manage.py test`
7. Commit: `git commit -m "message"`
8. Push: `git push origin branch-name`

### Feature Development
1. Create feature branch: `git checkout -b feature/feature-name`
2. Make changes and commits
3. Push branch: `git push origin feature/feature-name`
4. Create Pull Request
5. Wait for review
6. Merge to main
7. Delete branch

### Release Process
1. Update version number
2. Update CHANGELOG
3. Create release tag: `git tag -a v1.0.0`
4. Push tag: `git push origin v1.0.0`
5. Build and deploy

---

## 📈 Performance Metrics to Monitor

| Metric | Target | How to Check |
|--------|--------|-------------|
| Page Load Time | < 2s | Chrome DevTools |
| Database Queries | < 5 per page | Django Debug Toolbar |
| Server Response | < 500ms | Network tab |
| CSS File Size | < 50KB | Network tab |
| JS File Size | < 100KB | Network tab |
| Image Size | < 100KB | Network tab |

---

## 🎯 Success Checklist

### Before Going Live
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Security audit done
- [ ] Database backed up
- [ ] SSL certificate ready
- [ ] Monitoring configured
- [ ] Logging configured
- [ ] Backup plan made
- [ ] Rollback plan ready
- [ ] Team trained

### Monthly Tasks
- [ ] Security updates
- [ ] Dependency updates
- [ ] Database optimization
- [ ] Log review
- [ ] Performance analysis
- [ ] User feedback review

---

## 💡 Tips & Tricks

### Django Shortcuts
```python
# Instead of try-except
from django.shortcuts import get_object_or_404
obj = get_object_or_404(Model, id=1)

# Bulk operations
Model.objects.bulk_create([obj1, obj2, obj3])
Model.objects.bulk_update([obj1, obj2], fields=['field'])

# Update in bulk
Model.objects.filter(status='old').update(status='new')

# Delete in bulk
Model.objects.filter(status='deleted').delete()
```

### Template Tips
```html
<!-- Check if list is empty -->
{% empty %}
  <p>No items found</p>

<!-- Use with_namespace -->
{% url 'app:view' as view_url %}
<a href="{{ view_url }}">Link</a>

<!-- Use include with context -->
{% include 'template.html' with var=value %}
```

### Browser DevTools
```
F12 → Open DevTools
Ctrl+Shift+I → Open DevTools
Ctrl+Shift+J → Open Console
Ctrl+Shift+K → Open Console
Ctrl+Shift+M → Toggle responsive
```

---

## 🚀 Optimization Tips

```python
# Use .only() to limit fields
Penduduk.objects.only('id', 'nama')

# Use .values() for dictionaries
Penduduk.objects.values('id', 'nama')

# Cache repeated queries
from django.views.decorators.cache import cache_page
@cache_page(60 * 15)
def view(request):
    pass

# Use raw SQL when needed
Penduduk.objects.raw("SELECT * FROM penduduk WHERE...")

# Bulk operations
Penduduk.objects.bulk_create([...])
```

---

**Quick Reference Guide Siap Digunakan!**

*Last Updated: 2024*
