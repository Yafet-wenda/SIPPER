import json
from ipaddress import ip_address
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from django.conf import settings


class PublicChatError(Exception):
    pass


def riwayat_valid(riwayat):
    if not isinstance(riwayat, list) or len(riwayat) > 12:
        return False
    for item in riwayat:
        if not isinstance(item, dict):
            return False
        if item.get('peran') not in {'user', 'assistant'}:
            return False
        isi = item.get('isi')
        if not isinstance(isi, str) or not isi.strip() or len(isi) > 500:
            return False
    return True


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


def answer_public_chat(pesan, riwayat=None):
    """Jawab pertanyaan publik dengan Ollama lokal; tidak menerima data database."""
    if not _is_local_url(settings.OLLAMA_API_URL):
        raise PublicChatError('Server AI lokal belum dikonfigurasi.')

    messages = [
        {
            'role': 'system',
            'content': (
                'Anda adalah "Asisten AI SIPPER", asisten profesional untuk sistem '
                'Sistem Informasi Penduduk Perantauan milik Yafet Wenda. '
                'Jawablah dalam bahasa Indonesia yang jelas, ringkas, terstruktur, '
                'dan sopan. Gunakan daftar langkah, manfaat, atau catatan bila membantu. '
                '\n\n'
                'KONTEKS RESMI SIPPER:\n'
                '- SIPPER adalah website pendataan dan pengajuan warga perantauan, '
                'bukan sistem pengelolaan wajib pajak, bukan portal pemerintah resmi, dan bukan pengganti '
                'KTP atau dokumen resmi.\n'
                '- Alur utama: daftar akun dengan nama, email, dan password minimal 8 '
                'karakter; lengkapi pengajuan; isi NIK 16 digit, asal, tujuan merantau, '
                'tujuan, nomor telepon, dan tanggal bila diperlukan; unggah KTP serta '
                'Kartu Keluarga; unggah pasfoto opsional; kirim pengajuan.\n'
                '- Lampiran wajib adalah KTP dan KK. Format: PDF/JPG/JPEG/PNG; setiap '
                'berkas dibatasi maksimal 5 MB. Scan harus jelas, utuh, terang, dan tidak miring.\n'
                '- Status pengajuan: Menunggu, Perlu Perbaikan, Ditolak, atau Disetujui. '
                'Petugas memberi catatan untuk penolakan/perbaikan. Status disetujui '
                'menghasilkan kartu digital dengan QR dan masa berlaku menurut sistem.\n'
                '- Warga dapat memutakhirkan domisili melalui menu Pemutakhiran. Pengajuan '
                'Ditolak/Perlu Perbaikan dapat diperbaiki dan dikirim ulang dari Ringkasan.\n'
                '- Manfaat SIPPER: pendataan terpusat, pemantauan status, verifikasi dokumen, '
                'riwayat keputusan, kartu digital, pendaftaran dan pengajuan berbasis akun.\n'
                '- OCR membantu membaca teks dan membandingkan data; confidence adalah tingkat '
                'keyakinan pembacaan, bukan jaminan identitas. Keputusan identitas tetap oleh petugas.\n'
                '- Tidak mengungkapkan status atau data pribadi tanpa pengguna yang login. '
                'Untuk status pribadi, arahkan ke login dan menu Ringkasan/dashboard.\n'
                '- Identitas pembuat: Yafet Wenda, mahasiswa Teknik Informatika di PENS. '
                'GitHub https://github.com/Yafet-wenda; repositori '
                'https://github.com/Yafet-wenda/SIPPER; YouTube Pena Yafet.\n'
                '\n'
                'Untuk pertanyaan umum yang tidak berkaitan dengan SIPPER, jawab dengan '
                'pengetahuan yang Anda miliki secara aman dan tidak terlalu teknis kecuali '
                'pengguna meminta penjelasan teknis. Jika pertanyaan membutuhkan data mutakhir '
                'atau tidak dapat dipastikan, nyatakan keterbatasannya dan sarankan sumber '
                'resmi. Jangan mengarang status pribadi, NIK, alamat, keputusan petugas, '
                'tanggal, atau sumber informasi.'
            ),
        },
    ]

    if riwayat_valid(riwayat):
        for item in riwayat[-12:]:
            messages.append({
                'role': 'assistant' if item['peran'] == 'assistant' else 'user',
                'content': item['isi'][:500],
            })
    messages.append({'role': 'user', 'content': pesan})

    payload = {
        'model': settings.OLLAMA_MODEL,
        'stream': False,
        'messages': messages,
        'options': {'temperature': 0.25, 'top_p': 0.9, 'num_predict': 700},
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
