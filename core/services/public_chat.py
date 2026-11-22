import json
from ipaddress import ip_address
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from django.conf import settings


class PublicChatError(Exception):
    pass


def _is_local_url(url):
    try:
        hostname = urlsplit(url).hostname or ''
        try:
            local = ip_address(hostname).is_loopback
        except ValueError:
            local = hostname.casefold() == 'localhost'
        return local and urlsplit(url).scheme in {'http', 'https'}
    except ValueError:
        return False


def answer_public_chat(pesan):
    """Jawab pertanyaan publik dengan Ollama lokal; tidak menerima konteks database."""
    if not _is_local_url(settings.OLLAMA_API_URL):
        raise PublicChatError('Server AI lokal belum dikonfigurasi.')

    payload = {
        'model': settings.OLLAMA_MODEL,
        'stream': False,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Anda adalah Asisten AI SIPPER untuk pengguna umum. Jawablah pertanyaan '
                    'umum dengan bahasa Indonesia yang jelas, relevan, dan aman. Jika tidak yakin, '
                    'katakan dengan jujur dan jangan mengarang. Fakta resmi SIPPER: SIPPER adalah '
                    'Sistem Informasi Penduduk Perantauan, website untuk pendataan warga yang '
                    'merantau, bukan sistem pengelolaan wajib pajak. SIPPER dikembangkan oleh '
                    'Yafet Wenda, mahasiswa Teknik Informatika di PENS. GitHub: '
                    'https://github.com/Yafet-wenda; repositori: '
                    'https://github.com/Yafet-wenda/SIPPER; kanal YouTube: Pena Yafet. '
                    'Gunakan fakta ini apa adanya jika ditanya tentang SIPPER atau pembuatnya. '
                    'Jangan menebak informasi pribadi lain atau URL yang tidak tersedia. '
                    'Untuk panduan SIPPER, jelaskan pendaftaran akun, pengajuan data, unggah '
                    'KTP/KK, verifikasi petugas, kirim ulang, pemutakhiran, kartu digital, dan QR. '
                    'Jangan mengarang status pengajuan pribadi, NIK, alamat, nama, atau keputusan '
                    'petugas. Arahkan pengguna untuk login dan membuka Ringkasan jika menanyakan '
                    'status pribadinya.'
                ),
            },
            {'role': 'user', 'content': pesan},
        ],
        'options': {'temperature': 0.3, 'num_predict': 350},
    }
    request = Request(
        f'{settings.OLLAMA_API_URL.rstrip("/")}/api/chat',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with build_opener().open(request, timeout=settings.OLLAMA_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise PublicChatError('Ollama lokal tidak dapat dihubungi.') from error

    message = data.get('message')
    answer = message.get('content') if isinstance(message, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise PublicChatError('Ollama tidak menghasilkan jawaban.')
    return answer.strip()[:4000]
