"""Mesin penjawab berbasis aturan untuk Asisten Verifikasi Dokumen SIPPER.

Tidak ada model AI, tidak ada permintaan jaringan, dan tidak ada kunci API di
sini. Jawaban disusun dari basis pengetahuan statis tentang cara kerja SIPPER
ditambah data pengajuan yang diterima sebagai konteks, sehingga hasilnya
deterministik, jalan offline, dan bisa diuji sebagai fungsi murni tanpa
database maupun HTTP.

Kontrak konteks (semua kunci opsional; nilai tanggal sudah berbentuk teks
karena pemanggil yang memformatnya):

    {
      'pengajuan_id': int,
      'status_kode': 'menunggu' | 'disetujui' | 'ditolak' | 'perlu_perbaikan',
      'status': 'Menunggu',
      'catatan': str,
      'dikirim': str,
      'diverifikasi': str,
      'penduduk': {'nama', 'nik', 'daerah_asal', 'kota_tujuan', 'tujuan',
                   'tanggal_mulai', 'perkiraan_kembali', 'nomor_telepon'},
      'dokumen': [{'nama', 'jenis', 'jenis_label', 'status_label', 'confidence',
                   'extracted_nik', 'ai_verified', 'ai_verification_notes',
                   'diproses'}],
      'ktp': {...} | None,
      'kk': {...} | None,
      'kartu': {'kode', 'berlaku_sampai', 'status', 'valid'} | None,
      'lengkap': bool,
    }
"""
import os
import re

MAX_PANJANG_PESAN = 500

# Fakta teknis yang dikutip jawaban. Disimpan sebagai konstanta supaya satu
# perubahan di ocr_processor.py cukup dicari di sini, tidak tersebar di teks.
BATAS_CONFIDENCE_KATA = 30
MODE_PSM = (3, 11, 12, 6)
MASA_BERLAKU_KARTU_HARI = 365
DOKUMEN_WAJIB = ('KTP', 'Kartu Keluarga')
EKSTENSI_DITERIMA = ('pdf', 'jpg', 'jpeg', 'png')

_TANDA_BACA = re.compile(r'[^\w\s]', re.UNICODE)
_SPASI = re.compile(r'\s+')

SAPAAN = [
    'Apa arti confidence score OCR?',
    'Kenapa status verifikasinya belum terverifikasi?',
    'Apakah dokumen pengajuan ini sudah lengkap?',
]


def _normalisasi(teks):
    """Huruf kecil, tanda baca jadi spasi, spasi berlebih dirapatkan."""
    teks = _TANDA_BACA.sub(' ', str(teks or '').lower())
    return _SPASI.sub(' ', teks).strip()


def _skor_kata_kunci(kata_kunci, teks_normal, kumpulan_kata):
    """Bobot kecocokan satu kata kunci terhadap pesan.

    Frasa dinilai jumlah katanya agar niat yang spesifik ("status pengajuan")
    mengalahkan niat umum ("status"). Kata kunci pendek (<= 3 huruf) wajib
    cocok sebagai kata utuh supaya 'ai' tidak ikut terhitung di 'sampai'.
    """
    if len(kata_kunci) <= 3:
        return 1 if kata_kunci in kumpulan_kata else 0
    return len(kata_kunci.split()) if kata_kunci in teks_normal else 0


def _penduduk(konteks):
    return konteks.get('penduduk') or {}


def _dokumen(konteks):
    return konteks.get('dokumen') or []


def _cari_dokumen(konteks, jenis):
    for dokumen in _dokumen(konteks):
        if dokumen.get('jenis') == jenis:
            return dokumen
    return None


def _kartu(konteks):
    return konteks.get('kartu') or None


# --------------------------------------------------------------------------
# Penjawab per niat. Menerima konteks, mengembalikan teks (boleh multi-baris).
# --------------------------------------------------------------------------

def _jawab_ringkasan(konteks):
    if not konteks.get('pengajuan_id'):
        return None
    warga = _penduduk(konteks)
    baris = [
        f"Ringkasan pengajuan #{konteks.get('pengajuan_id')}",
        f"Warga: {warga.get('nama') or '-'} (NIK {warga.get('nik') or '-'})",
        f"Rute: {warga.get('daerah_asal') or '-'} → {warga.get('kota_tujuan') or '-'} untuk {warga.get('tujuan') or '-'}",
        f"Status: {konteks.get('status') or '-'}",
        f"Dikirim: {konteks.get('dikirim') or '-'}",
    ]
    dokumen = _dokumen(konteks)
    if dokumen:
        baris.append('Dokumen:')
        for item in dokumen:
            conf = item.get('confidence')
            conf_teks = f"{conf:.1f}%" if isinstance(conf, (int, float)) else 'belum di-OCR'
            tanda = 'terverifikasi otomatis' if item.get('ai_verified') else 'perlu cek manual'
            baris.append(f"- {item.get('jenis_label') or item.get('jenis')}: {item.get('nama')}, "
                         f"status {item.get('status_label') or '-'}, confidence {conf_teks}, {tanda}")
    else:
        baris.append('Dokumen: belum ada berkas terunggah.')
    if not konteks.get('lengkap', True):
        kurang = [label for label in DOKUMEN_WAJIB if label not in
                  {(d.get('jenis_label') or '') for d in dokumen}]
        baris.append(f"Belum lengkap, masih kurang: {', '.join(kurang) or 'periksa ulang jenis dokumen'}.")
    kartu = _kartu(konteks)
    if kartu:
        baris.append(f"Kartu digital: {kartu.get('kode')} berlaku sampai {kartu.get('berlaku_sampai')} "
                     f"({kartu.get('status')}).")
    baris.append(_saran_tindakan(konteks))
    return '\n'.join(baris)


def _saran_tindakan(konteks):
    """Satu kalimat langkah berikutnya, dipakai beberapa penjawab."""
    kode = konteks.get('status_kode')
    if kode == 'menunggu':
        return 'Langkah berikutnya: cocokkan hasil OCR dengan berkas asli, isi catatan, lalu pilih status verifikasi di bawah.'
    if kode == 'perlu_perbaikan':
        return 'Langkah berikutnya: warga perlu mengunggah ulang berkas; setelah itu status kembali ke Menunggu dan OCR dijalankan ulang otomatis.'
    if kode == 'ditolak':
        return 'Langkah berikutnya: pastikan catatan penolakan terisi jelas karena itu yang dibaca warga lewat email dan dashboard.'
    if kode == 'disetujui':
        return 'Pengajuan sudah selesai; kartu digital terbit otomatis dan tautan validasinya bisa dipindai lewat QR.'
    return 'Langkah berikutnya: tentukan status verifikasi pengajuan ini.'


def _jawab_status_pengajuan(konteks):
    if not konteks.get('pengajuan_id'):
        return None
    arti = {
        'menunggu': 'belum ada keputusan petugas. Pengajuan ini masih mengantre di daftar /petugas/.',
        'disetujui': f'sudah disetujui. Kartu digital terbit otomatis dengan masa berlaku {MASA_BERLAKU_KARTU_HARI} hari dan warga dikabari lewat email.',
        'ditolak': 'ditolak. Warga menerima email berisi catatan petugas dan bisa mengirim ulang pengajuan dari dashboard.',
        'perlu_perbaikan': 'perlu perbaikan. Warga harus mengunggah ulang berkas yang bermasalah; begitu diganti, status kembali ke Menunggu dan OCR dijalankan ulang.',
    }
    kode = konteks.get('status_kode') or ''
    teks = [f"Status pengajuan ini: {konteks.get('status') or '-'} — {arti.get(kode, 'status tidak dikenal.')}",
            f"Dikirim {konteks.get('dikirim') or '-'}, diverifikasi {konteks.get('diverifikasi') or 'belum'}."]
    if konteks.get('catatan'):
        teks.append(f"Catatan petugas: {konteks['catatan']}")
    teks.append(_saran_tindakan(konteks))
    return '\n'.join(teks)


def _jawab_catatan(konteks):
    if not konteks.get('pengajuan_id'):
        return None
    if konteks.get('catatan'):
        return (f"Catatan petugas untuk pengajuan ini: \"{konteks['catatan']}\". "
                'Catatan ini ikut terkirim ke warga lewat email pemberitahuan status dan tampil di dashboard mereka.')
    return ('Pengajuan ini belum punya catatan petugas. Catatan wajib diisi saat menolak atau meminta perbaikan, '
            'karena hanya itu penjelasan yang diterima warga.')


def _jawab_kelengkapan(konteks):
    dokumen = _dokumen(konteks)
    jenis_ada = {item.get('jenis') for item in dokumen}
    if 'ktp' not in jenis_ada or 'kk' not in jenis_ada:
        kurang = []
        if 'ktp' not in jenis_ada:
            kurang.append('KTP')
        if 'kk' not in jenis_ada:
            kurang.append('Kartu Keluarga')
        return (f"Dokumen belum lengkap. Yang masih kurang: {', '.join(kurang)}. "
                f"SIPPER mewajibkan keduanya sebelum pengajuan bisa diproses. Ekstensi yang diterima: {', '.join(EKSTENSI_DITERIMA)}.")
    baris = [f"Dokumen wajib sudah lengkap ({len(dokumen)} berkas terunggah):"]
    for item in dokumen:
        conf = item.get('confidence')
        conf_teks = f"{conf:.1f}%" if isinstance(conf, (int, float)) else 'belum di-OCR'
        baris.append(f"- {item.get('jenis_label') or item.get('jenis')}: {item.get('nama')} "
                     f"({item.get('status_label') or '-'}, confidence {conf_teks})")
    belum_ocr = [item.get('jenis_label') or item.get('jenis') for item in dokumen if not item.get('diproses')]
    if belum_ocr:
        baris.append(f"Perlu diproses OCR: {', '.join(belum_ocr)}. Pakai tombol Proses Ulang OCR di panel atas.")
    belum_valid = [item.get('jenis_label') or item.get('jenis') for item in dokumen
                   if item.get('status_label') and item['status_label'] != 'Valid']
    if belum_valid:
        baris.append(f"Belum ditandai valid oleh petugas: {', '.join(belum_valid)}.")
    return '\n'.join(baris)


def _jawab_confidence(konteks):
    teks = [
        'Confidence score adalah rata-rata tingkat kepercayaan Tesseract atas kata-kata yang berhasil dibaca, dalam persen.',
        f'Cara hitungnya: kata dengan confidence di bawah {BATAS_CONFIDENCE_KATA} dibuang, sisanya dirata-rata lalu dibulatkan dua desimal. '
        f'Kalau percobaan pertama kurang meyakinkan, mesin mencoba mode PSM {", ".join(str(m) for m in MODE_PSM)} dan mengambil hasil terbaik.',
        'Panduan praktis (ini acuan baca, bukan ambang yang dipaksakan kode):',
        '- di atas 85%: umumnya terbaca bersih, cukup cocokkan NIK dan nama;',
        '- 70-85%: periksa manual field yang rawan salah baca (angka 0/O, 1/I, 5/S);',
        '- di bawah 70%: jangan dipercaya apa adanya, minta warga mengunggah scan yang lebih tajam dan tidak miring.',
    ]
    dokumen = _cari_dokumen(konteks, 'ktp') or (_dokumen(konteks)[0] if _dokumen(konteks) else None)
    if dokumen:
        conf = dokumen.get('confidence')
        if isinstance(conf, (int, float)):
            teks.insert(0, f"Confidence {dokumen.get('jenis_label') or dokumen.get('jenis')} pada pengajuan ini: {conf:.1f}%.")
        else:
            teks.insert(0, f"{dokumen.get('jenis_label') or dokumen.get('jenis')} pada pengajuan ini belum diproses OCR.")
    return '\n'.join(teks)


def _jawab_ocr_kosong(konteks):
    return '\n'.join([
        'Hasil OCR kosong biasanya karena salah satu dari ini:',
        '1. Berkas belum diproses. OCR jalan di thread latar belakang setelah unggahan atau setelah tombol Proses Ulang OCR ditekan, jadi tunggu beberapa detik lalu muat ulang halaman.',
        '2. Berkasnya PDF hasil pindai berlapis gambar buram, atau foto miring/berbayang. Tesseract hanya membaca teks yang terlihat jelas.',
        '3. Jenis dokumennya bukan KTP atau KK. Selain dua jenis itu SIPPER tidak menjalankan parser data terstruktur, jadi panel Data Terstruktur tetap kosong walau teksnya terbaca.',
        '4. Berkas bukan gambar (mis. PDF berisi teks vektor). Jalur OCR di sini mengonversi lewat OpenCV, jadi PDF teks bisa gagal.',
        'Langkah tercepat: tekan Proses Ulang OCR, lalu bandingkan teks mentah di panel kiri dengan berkas aslinya.',
    ])


def _jawab_nik(konteks):
    teks = [
        'NIK adalah nomor induk kependudukan 16 digit dan menjadi kunci verifikasi di SIPPER.',
        'Alurnya: Tesseract membaca teks KTP, lalu parser mencari pola "NIK" diikuti 16-20 karakter angka (spasi dan titik diabaikan). Hasilnya disimpan di field extracted_nik.',
        'NIK di database bersifat unik, jadi dua penduduk tidak mungkin berbagi nomor yang sama.',
    ]
    warga = _penduduk(konteks)
    ktp = _cari_dokumen(konteks, 'ktp')
    if warga.get('nik') or ktp:
        teks.append('')
        teks.append(f"Pada pengajuan ini — NIK terdaftar: {warga.get('nik') or '-'}.")
        if ktp:
            bacaan = ktp.get('extracted_nik') or 'tidak terbaca'
            teks.append(f"NIK hasil OCR dari {ktp.get('nama') or 'KTP'}: {bacaan}.")
            if ktp.get('ai_verified'):
                teks.append('Keduanya cocok persis, karena itu statusnya terverifikasi otomatis.')
            elif ktp.get('extracted_nik'):
                teks.append('Keduanya TIDAK cocok. Ini harus diselesaikan manual: bisa salah baca OCR, atau memang KTP bukan milik warga ini.')
            else:
                teks.append('NIK tidak terbaca, jadi verifikasi otomatis tidak bisa jalan. Baca teks mentah di panel OCR untuk memastikan angkanya ada.')
        else:
            teks.append('Pengajuan ini belum punya dokumen KTP, jadi tidak ada NIK pembanding dari OCR.')
    return '\n'.join(teks)


def _jawab_verifikasi_otomatis(konteks):
    teks = [
        'Yang disebut "verifikasi AI" di SIPPER adalah aturan pembanding, bukan model machine learning.',
        'Aturannya satu: kalau NIK hasil OCR sama persis (string identik) dengan NIK penduduk terdaftar, dokumen ditandai ai_verified dengan catatan "NIK cocok"; '
        'kalau tidak, catatannya "Menunggu verifikasi manual petugas".',
        'Artinya tanda centang hijau hanya membuktikan nomor NIK-nya sama. Nama, alamat, dan keaslian berkas tetap keputusan petugas.',
        'OCR itu sendiri (Tesseract) berjalan lokal di server ini; yang bisa keluar ke layanan cloud hanya percakapan asisten bila GEMINI_API_KEY diisi.',
    ]
    ktp = _cari_dokumen(konteks, 'ktp')
    if ktp:
        teks.append('')
        teks.append(f"Status pada pengajuan ini: {'terverifikasi otomatis' if ktp.get('ai_verified') else 'belum terverifikasi otomatis'}. "
                    f"Catatan sistem: {ktp.get('ai_verification_notes') or '-'}")
    return '\n'.join(teks)


def _jawab_kartu(konteks):
    teks = [
        f'Kartu digital terbit otomatis begitu pengajuan berstatus disetujui: satu kartu per penduduk, kodenya diawali "SPR-", masa berlaku {MASA_BERLAKU_KARTU_HARI} hari sejak persetujuan.',
        'Kartu memuat QR yang mengarah ke halaman validasi publik /kartu/<kode>/. Siapa pun yang memindai melihat status kartu tanpa perlu login.',
        'Kalau tanggal berlaku_sampai sudah lewat, statusnya berubah jadi expired saat halaman validasi dibuka.',
    ]
    kartu = _kartu(konteks)
    if kartu:
        teks.append('')
        teks.append(f"Kartu pengajuan ini: {kartu.get('kode')} — status {kartu.get('status')}, berlaku sampai {kartu.get('berlaku_sampai')}, "
                    f"{'masih valid' if kartu.get('valid') else 'sudah tidak valid'}.")
    else:
        teks.append('')
        teks.append(f"Pengajuan ini belum punya kartu (status sekarang: {konteks.get('status') or '-'}).")
    return '\n'.join(teks)


def _jawab_cara_verifikasi(konteks):
    return '\n'.join([
        'Alur verifikasi petugas di SIPPER:',
        '1. Buka pengajuan dari daftar di /petugas/ (bisa dicari nama/NIK atau disaring statusnya).',
        '2. Buka berkas aslinya lewat tautan dokumen; gambar tampil sebagai pratinjau, PDF dibuka sebagai tautan.',
        '3. Bandingkan panel Hasil Analisis AI dengan berkas: NIK, nama, dan alamat.',
        '4. Kalau teks OCR kosong atau confidence rendah, tekan Proses Ulang OCR.',
        '5. Tandai tiap dokumen Valid atau Tidak valid lewat tombol di tabel dokumen.',
        '6. Isi catatan (wajib untuk Ditolak dan Perlu perbaikan), pilih status, lalu simpan. Warga langsung dikabari lewat email.',
        'Status yang tersedia: Menunggu, Disetujui, Ditolak, Perlu perbaikan.',
    ])


def _jawab_proses_ulang(konteks):
    return '\n'.join([
        'Tombol Proses Ulang OCR memanggil /api/trigger-ocr/<id dokumen>/ dan OCR-nya dikerjakan di thread latar belakang supaya halaman tidak membeku.',
        'Karena itu hasilnya tidak muncul seketika: tunggu beberapa detik lalu muat ulang halaman, atau buka lagi panelnya.',
        'Dokumen yang ditampilkan panel ini adalah KTP bila ada, kalau tidak maka dokumen pertama.',
        'Setiap pemrosesan dicatat di AuditLog (berhasil dengan nilai confidence, atau gagal dengan pesan errornya) dan terlihat di halaman histori.',
    ])


def _jawab_email(konteks):
    return '\n'.join([
        'Setiap perubahan status pengajuan memicu email pemberitahuan ke warga.',
        'Status di database disimpan lebih dulu, baru email dikirim. Jadi kalau SMTP mati, keputusan petugas tidak ikut batal — hanya pemberitahuannya yang hilang, '
        'dan kegagalan itu dicatat ke AuditLog supaya tetap terlihat di halaman histori.',
        'Pada pemasangan pengembangan, backend email biasanya masih konsol, jadi suratnya tercetak di log server dan tidak benar-benar terkirim.',
    ])


def _llm_aktif():
    """Apakah LLM cloud sedang terpasang. Dibaca dari environment (konfigurasi
    server, bukan input pengguna) supaya jawaban privasi tidak berbohong saat
    GEMINI_API_KEY diisi di .env."""
    return bool(os.getenv('GEMINI_API_KEY', '').strip())


def _jawab_privasi(konteks):
    baris = ['Semua pemrosesan berkas dan OCR berjalan di server ini; Tesseract terpasang lokal.']
    if _llm_aktif():
        baris.append(
            'Perhatian: asisten ini kini memakai LLM cloud (Gemini). Pertanyaan Anda beserta '
            'ringkasan data pengajuan (nama, NIK, rute) dikirim ke server Google untuk '
            'menyusun jawaban. Kalau gagal, asisten jatuh ke mesin aturan yang sepenuhnya lokal.'
        )
    else:
        baris.append(
            'Asisten ini saat ini berjalan penuh di mesin aturan lokal — tidak ada pertanyaan '
            'petugas yang dikirim keluar, tidak ada kunci API yang terpasang.'
        )
    baris.append(
        'Berkas warga disimpan di folder media dan hanya bisa dibuka pemiliknya atau petugas '
        "lewat /dokumen/<id>/file/, disajikan dengan header anti-sniff dan tanpa cache."
    )
    return '\n'.join(baris)


def _jawab_data_penduduk(konteks):
    warga = _penduduk(konteks)
    if not warga:
        return None
    return '\n'.join([
        'Data penduduk pada pengajuan ini (hasil isian warga, bukan hasil OCR):',
        f"- Nama: {warga.get('nama') or '-'}",
        f"- NIK: {warga.get('nik') or '-'}",
        f"- Daerah asal: {warga.get('daerah_asal') or '-'}",
        f"- Kota tujuan: {warga.get('kota_tujuan') or '-'}",
        f"- Tujuan berpindah: {warga.get('tujuan') or '-'}",
        f"- Tanggal mulai: {warga.get('tanggal_mulai') or '-'}",
        f"- Perkiraan kembali: {warga.get('perkiraan_kembali') or '-'}",
        f"- Nomor telepon: {warga.get('nomor_telepon') or '-'}",
        '',
        'Bandingkan nilai ini dengan panel Data Terstruktur: selisihnya itulah yang perlu diklarifikasi ke warga.',
    ])


def _jawab_selisih(konteks):
    """Bandingkan isian warga dengan hasil baca OCR — inti kerja verifikasi."""
    warga = _penduduk(konteks)
    ktp = _cari_dokumen(konteks, 'ktp')
    if not ktp:
        return 'Belum ada dokumen KTP pada pengajuan ini, jadi tidak ada hasil OCR yang bisa dibandingkan.'
    if not ktp.get('diproses'):
        return 'Dokumen KTP belum diproses OCR. Tekan Proses Ulang OCR dulu, tunggu beberapa detik, lalu tanyakan lagi.'
    extracted = ktp.get('extracted_data') or {}
    if not extracted:
        return ('OCR sudah jalan tapi tidak ada data terstruktur yang berhasil diurai. '
                'Artinya teksnya terbaca namun polanya tidak dikenali parser — periksa teks mentah di panel kiri.')
    baris = ['Perbandingan isian warga vs hasil OCR KTP:']
    pasangan = [('nama', 'Nama', warga.get('nama')), ('nik', 'NIK', warga.get('nik')),
                ('alamat', 'Alamat', None), ('tempat_lahir', 'Tempat lahir', None),
                ('tanggal_lahir', 'Tanggal lahir', None), ('pekerjaan', 'Pekerjaan', None),
                ('agama', 'Agama', None), ('status_perkawinan', 'Status', None)]
    ada_selisih = False
    for kunci, label, nilai_warga in pasangan:
        if kunci not in extracted:
            continue
        nilai_ocr = extracted.get(kunci) or '-'
        if nilai_warga:
            sama = _normalisasi(nilai_warga) == _normalisasi(nilai_ocr)
            tanda = 'cocok' if sama else 'BEDA'
            ada_selisih = ada_selisih or not sama
            baris.append(f"- {label}: warga \"{nilai_warga}\" vs OCR \"{nilai_ocr}\" → {tanda}")
        else:
            baris.append(f"- {label}: OCR \"{nilai_ocr}\" (tidak ada pembanding di data warga)")
    if not ada_selisih:
        baris.append('Tidak ada selisih pada field yang bisa dibandingkan. Keputusan akhir tetap di tangan petugas.')
    else:
        baris.append('Ada selisih. Cek apakah ini salah baca OCR (confidence rendah, angka mirip huruf) atau memang data warga yang perlu diperbaiki.')
    return '\n'.join(baris)


def _jawab_bantuan(konteks):
    return '\n'.join([
        'Saya asisten berbasis aturan untuk membantu verifikasi pengajuan ini. Yang bisa saya jawab:',
        '- Ringkasan pengajuan, status, dan langkah berikutnya',
        '- Kelengkapan dokumen dan perbandingan data warga vs hasil OCR',
        '- Arti confidence score, NIK, dan status verifikasi otomatis',
        '- Cara kerja OCR dan tombol Proses Ulang',
        '- Kartu digital, email pemberitahuan, dan alur kerja petugas',
        '- Privasi data',
        '',
        'Saya menjawab dari basis pengetahuan tetap dan data pengajuan yang sedang terbuka, jadi saya tidak bisa menafsirkan pertanyaan di luar itu.',
    ])


def _jawab_sapaan(konteks):
    return ('Halo. Saya asisten verifikasi dokumen SIPPER. '
            'Tanyakan ringkasan pengajuan ini, arti confidence, kelengkapan dokumen, atau alasan status verifikasinya.')


def _jawab_terima_kasih(konteks):
    return 'Sama-sama. Kalau ada dokumen yang masih meragukan, bandingkan teks OCR-nya dengan berkas asli sebelum memutuskan status.'


def _jawab_kemampuan(konteks):
    return ('Saya bukan model bahasa besar. Saya kumpulan aturan pencocokan kata kunci yang menjawab dari basis pengetahuan SIPPER '
            'dan dari data pengajuan yang sedang Anda buka. Keuntungannya: cepat, gratis, offline, dan jawabannya selalu sama untuk pertanyaan yang sama.')


# --------------------------------------------------------------------------
# Basis aturan. Urutan menentukan pemenang saat skor seri, jadi niat yang
# paling spesifik diletakkan lebih dulu.
# --------------------------------------------------------------------------

ATURAN = [
    {
        'id': 'selisih_data',
        'kata_kunci': ('selisih', 'perbedaan', 'beda data', 'cocok tidak', 'cocokkan', 'bandingkan',
                       'bandingkan data', 'data warga dengan', 'perbandingan', 'samakah',
                       'sesuai tidak', 'kesesuaian', 'cocok atau tidak'),
        'penjawab': _jawab_selisih,
        'saran': ['Apa arti confidence score OCR?', 'Apakah dokumen pengajuan ini sudah lengkap?'],
    },
    {
        'id': 'ringkasan',
        'kata_kunci': ('ringkasan', 'ringkas', 'kesimpulan', 'rangkuman', 'summary', 'cek pengajuan ini',
                       'gimana pengajuan ini', 'bagaimana pengajuan ini', 'ulas pengajuan'),
        'penjawab': _jawab_ringkasan,
        'saran': ['Apa langkah verifikasi berikutnya?', 'Apakah dokumen pengajuan ini sudah lengkap?'],
    },
    {
        'id': 'status_pengajuan',
        'kata_kunci': ('status pengajuan', 'status pengajuan ini', 'sudah sampai mana', 'progress',
                       'progres', 'tahap', 'sedang apa', 'menunggu apa', 'status verifikasi pengajuan'),
        'penjawab': _jawab_status_pengajuan,
        'saran': ['Buatkan ringkasan pengajuan ini', 'Apa langkah verifikasi berikutnya?'],
    },
    {
        'id': 'catatan_petugas',
        'kata_kunci': ('kenapa ditolak', 'mengapa ditolak', 'alasan', 'catatan petugas', 'catatan',
                       'kenapa perlu perbaikan', 'alasan penolakan'),
        'penjawab': _jawab_catatan,
        'saran': ['Apa status pengajuan ini?', 'Bagaimana alur verifikasi petugas?'],
    },
    {
        'id': 'kelengkapan',
        'kata_kunci': ('dokumen lengkap', 'berkas lengkap', 'apa yang kurang', 'kurang apa', 'lengkap tidak',
                       'sudah lengkap', 'dokumen apa saja', 'berkas apa saja', 'kelengkapan', 'wajib unggah',
                       'kartu keluarga', 'unggah', 'upload', 'berkas', 'dokumen'),
        'penjawab': _jawab_kelengkapan,
        'saran': ['Bandingkan data warga dengan hasil OCR', 'Kenapa hasil OCR kosong?'],
    },
    {
        'id': 'confidence',
        'kata_kunci': ('confidence', 'kepercayaan', 'akurasi', 'skor ocr', 'persen', 'berapa akurat',
                       'tingkat keyakinan'),
        'penjawab': _jawab_confidence,
        'saran': ['Kenapa hasil OCR kosong?', 'Kenapa status verifikasinya belum terverifikasi?'],
    },
    {
        'id': 'ocr_bermasalah',
        'kata_kunci': ('ocr gagal', 'hasil ocr kosong', 'kosong', 'tidak terbaca', 'gagal baca', 'error ocr',
                       'kenapa kosong', 'teks tidak muncul', 'blur', 'buram'),
        'penjawab': _jawab_ocr_kosong,
        'saran': ['Apa arti confidence score OCR?', 'Bagaimana cara kerja tombol Proses Ulang OCR?'],
    },
    {
        'id': 'nik',
        'kata_kunci': ('nik', 'nomor induk', 'nomor ktp', '16 digit'),
        'penjawab': _jawab_nik,
        'saran': ['Kenapa status verifikasinya belum terverifikasi?', 'Bandingkan data warga dengan hasil OCR'],
    },
    {
        'id': 'verifikasi_otomatis',
        'kata_kunci': ('verifikasi ai', 'status ai', 'ai', 'auto verifikasi', 'verifikasi otomatis',
                       'kecerdasan buatan', 'machine learning', 'model ai', 'cara kerja ai', 'terverifikasi'),
        'penjawab': _jawab_verifikasi_otomatis,
        'saran': ['Apa arti confidence score OCR?', 'Apakah data warga saya dikirim ke internet?'],
    },
    {
        'id': 'kartu_digital',
        'kata_kunci': ('kartu digital', 'kartu', 'qr', 'qrcode', 'kode kartu', 'masa berlaku kartu',
                       'berlaku sampai'),
        'penjawab': _jawab_kartu,
        'saran': ['Apa status pengajuan ini?', 'Bagaimana email pemberitahuan bekerja?'],
    },
    {
        'id': 'alur_petugas',
        'kata_kunci': ('cara verifikasi', 'cara menyetujui', 'alur verifikasi', 'langkah verifikasi',
                       'cara kerja petugas', 'langkah berikutnya', 'apa yang harus saya lakukan',
                       'cara menandai', 'cara menolak'),
        'penjawab': _jawab_cara_verifikasi,
        'saran': ['Buatkan ringkasan pengajuan ini', 'Apakah dokumen pengajuan ini sudah lengkap?'],
    },
    {
        'id': 'proses_ulang',
        'kata_kunci': ('proses ulang', 'reprocess', 'ulangi ocr', 'trigger ocr', 'proses ocr lagi',
                       'jalankan ocr', 'tombol proses'),
        'penjawab': _jawab_proses_ulang,
        'saran': ['Kenapa hasil OCR kosong?', 'Apa arti confidence score OCR?'],
    },
    {
        'id': 'ocr_umum',
        'kata_kunci': ('ocr', 'tesseract', 'baca dokumen', 'ekstrak teks', 'scan', 'pindai', 'parser'),
        'penjawab': _jawab_proses_ulang,
        'saran': ['Apa arti confidence score OCR?', 'Kenapa hasil OCR kosong?'],
    },
    {
        'id': 'email',
        'kata_kunci': ('email', 'surel', 'notifikasi', 'pemberitahuan', 'smtp', 'kabar warga',
                       'email pemberitahuan', 'pemberitahuan status', 'notifikasi status', 'surat'),
        'penjawab': _jawab_email,
        'saran': ['Apa status pengajuan ini?', 'Bagaimana alur verifikasi petugas?'],
    },
    {
        'id': 'privasi',
        'kata_kunci': ('privasi', 'keamanan data', 'data dikirim', 'dikirim ke internet', 'kirim ke internet',
                       'dikirim ke mana', 'internet', 'cloud', 'lokal', 'offline', 'pihak ketiga',
                       'pihak luar', 'aman tidak', 'data saya aman', 'apakah aman', 'data bocor', 'kebocoran'),
        'penjawab': _jawab_privasi,
        'saran': ['Kamu pakai AI dari mana?', 'Bagaimana cara kerja verifikasi otomatis?'],
    },
    {
        'id': 'data_penduduk',
        'kata_kunci': ('data penduduk', 'identitas', 'profil warga', 'alamat', 'daerah asal', 'kota tujuan',
                       'tanggal mulai', 'perkiraan kembali', 'nomor telepon', 'kapan kembali', 'berapa lama',
                       'data warga'),
        'penjawab': _jawab_data_penduduk,
        'saran': ['Bandingkan data warga dengan hasil OCR', 'Buatkan ringkasan pengajuan ini'],
    },
    {
        'id': 'kemampuan_diri',
        'kata_kunci': ('kamu ai apa', 'pakai ai apa', 'pakai ai', 'ai dari mana', 'kamu ai', 'ai apa',
                       'model apa', 'kamu siapa', 'siapa kamu', 'basis aturan', 'rule based',
                       'gpt', 'chatgpt', 'gemini', 'openai', 'ollama', 'llm'),
        'penjawab': _jawab_kemampuan,
        'saran': ['Apa yang bisa kamu bantu?', 'Apakah data warga saya dikirim ke internet?'],
    },
    {
        'id': 'bantuan',
        'kata_kunci': ('bantu', 'help', 'bisa apa', 'fitur', 'menu', 'apa saja', 'cara pakai', 'panduan'),
        'penjawab': _jawab_bantuan,
        'saran': list(SAPAAN),
    },
    {
        'id': 'terima_kasih',
        'kata_kunci': ('terima kasih', 'makasih', 'thanks', 'thx', 'sip', 'oke terima'),
        'penjawab': _jawab_terima_kasih,
        'saran': ['Buatkan ringkasan pengajuan ini'],
    },
    {
        'id': 'sapaan',
        'kata_kunci': ('halo', 'hai', 'hi', 'hey', 'selamat', 'assalamualaikum', 'pagi', 'siang',
                       'sore', 'malam', 'permisi'),
        'penjawab': _jawab_sapaan,
        'saran': list(SAPAAN),
    },
]


def _saran_berdasarkan_konteks(konteks):
    """Saran tindak lanjut saat tidak ada aturan yang cocok."""
    saran = []
    ktp = _cari_dokumen(konteks, 'ktp')
    if ktp and not ktp.get('diproses'):
        saran.append('Kenapa hasil OCR kosong?')
    if ktp and not ktp.get('ai_verified'):
        saran.append('Kenapa status verifikasinya belum terverifikasi?')
    if not konteks.get('lengkap', True):
        saran.append('Apakah dokumen pengajuan ini sudah lengkap?')
    if konteks.get('status_kode') == 'menunggu':
        saran.append('Apa langkah verifikasi berikutnya?')
    for bawaan in SAPAAN:
        if bawaan not in saran:
            saran.append(bawaan)
        if len(saran) >= 3:
            break
    return saran[:3]


_PENOLAK = (
    'Pertanyaan itu di luar basis pengetahuan saya. '
    'Saya menjawab seputar verifikasi pengajuan ini: hasil OCR, confidence, NIK, kelengkapan dokumen, '
    'status pengajuan, kartu digital, dan alur kerja petugas.'
)


def jawab(pesan, konteks=None):
    """Kembalikan dict {'jawaban', 'kategori', 'saran'} untuk satu pesan petugas.

    Fungsi murni: tidak menyentuh database, tidak membuka berkas, tidak melakukan
    permintaan jaringan. Niat dipilih dari skor kecocokan kata kunci tertinggi;
    seri dimenangkan aturan yang lebih dulu terdaftar.
    """
    konteks = konteks if isinstance(konteks, dict) else {}
    normal = _normalisasi(pesan)[:MAX_PANJANG_PESAN]
    if not normal:
        return {
            'jawaban': 'Saya tidak menerima pesan kosong. Ketik pertanyaan tentang pengajuan ini, misalnya "Apa arti confidence score OCR?".',
            'kategori': 'kosong',
            'saran': list(SAPAAN),
        }

    kumpulan_kata = set(normal.split())
    terbaik = None
    skor_terbaik = 0
    for aturan in ATURAN:
        skor = sum(_skor_kata_kunci(kunci, normal, kumpulan_kata) for kunci in aturan['kata_kunci'])
        if skor > skor_terbaik:
            terbaik = aturan
            skor_terbaik = skor

    if terbaik is None:
        return {'jawaban': _PENOLAK, 'kategori': 'tidak_dikenal', 'saran': _saran_berdasarkan_konteks(konteks)}

    jawaban = terbaik['penjawab'](konteks)
    if jawaban is None:
        return {'jawaban': _PENOLAK, 'kategori': 'tidak_dikenal', 'saran': _saran_berdasarkan_konteks(konteks)}

    return {'jawaban': jawaban, 'kategori': terbaik['id'], 'saran': list(terbaik.get('saran') or [])[:3]}
