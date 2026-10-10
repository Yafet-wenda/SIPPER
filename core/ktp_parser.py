"""
KTP Parser - Handle berbagai format OCR KTP Indonesia
"""
import re


def parse_ktp_data(ocr_result):
    """
    Parse data dari hasil OCR KTP Indonesia.
    Handle dua format:
    1. Format baris per baris: "NIK: 1234567890123456"
    2. Format kolom (OCR scan): semua label di kiri, semua value di kanan
    """
    text = ocr_result.get('text', '')
    
    # Deteksi format kolom: jika semua label muncul berurutan tanpa value
    has_column_format = bool(re.search(r'NIK\s+Nama\s+Tempat', text))
    
    if has_column_format:
        return _parse_ktp_column_format(text)
    else:
        return _parse_ktp_normal_format(text)


def _parse_ktp_column_format(text):
    """Parse KTP dengan format kolom (label di kiri, value di kanan)."""
    extracted = {}
    
    # Ekstrak NIK (16 digit berurutan - handle spasi)
    text_no_space = text.replace(' ', '')
    nik_match = re.search(r'\b(\d{16})\b', text_no_space)
    if not nik_match:
        # Fallback: cari 16 digit dengan spasi
        nik_match = re.search(r'(\d[\d\s]{14,18}\d)', text)
        if nik_match:
            digits = re.findall(r'\d', nik_match.group(1))
            if len(digits) == 16:
                extracted['nik'] = ''.join(digits)
    else:
        extracted['nik'] = nik_match.group(1)
    
    # Ekstrak Nama (setelah NIK, biasanya 2-4 kata ALL CAPS)
    if 'nik' in extracted:
        nik_str = extracted['nik']
        nik_pos = text.find(nik_str[:8])
        if nik_pos >= 0:
            after_nik = text[nik_pos + 16:]
            nama_match = re.search(r'([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)', after_nik)
            if nama_match:
                nama_raw = nama_match.group(1).strip()
                # Hapus kata yang bukan nama (kota, tanggal, dll)
                nama_parts = nama_raw.split()
                nama_clean = []
                skip_words = ['WAMENA', 'JAKARTA', 'BANDUNG', 'SURABAYA', 'LANI', 'JAYA']
                for part in nama_parts:
                    if part not in skip_words and not re.match(r'\d{2}-\d{2}', part):
                        nama_clean.append(part)
                if len(nama_clean) >= 2:
                    extracted['nama'] = ' '.join(nama_clean)
                elif len(nama_clean) == 1 and len(nama_clean[0]) > 3:
                    # Single word name (rare tapi mungkin)
                    pass
    
    # Fallback: cari "Nama :" diikuti text
    if 'nama' not in extracted:
        nama_fallback = re.search(r'Nama\s*[:>\-\s]+\s*([A-Z][A-Z\s]+?)(?:Temp|Tgl|Lahir|\d{2}[-/]\d{2})', text, re.IGNORECASE)
        if nama_fallback:
            extracted['nama'] = nama_fallback.group(1).strip()
    
    # Ekstrak Tempat/Tgl Lahir (handle variasi OCR ekstrem)
    # Pattern 1: "Tempai/T gi Lahir LANI JAYA, 01- -11-2007"
    ttl_match = re.search(r'(?:Tempat|Tempai)[/\\s]*(?:Tgl|Tal|Tanggal|T\s+gi)\s*Lahir[:>\-\s]+(.+?)(?:Alamat|Jenis|Kelamin|\n|$)', text, re.IGNORECASE)
    if ttl_match:
        ttl_raw = ttl_match.group(1).strip()
        # Bersihkan noise dan normalisasi tanggal
        ttl_clean = re.sub(r'(\d{1,2})[-\s]+[-/]?(\d{2})[-/](\d{4})', r'\1-\2-\3', ttl_raw)
        ttl_clean = re.sub(r'(\d{2}[-/]\d{2}[-/]\d{4}).*$', r'\1', ttl_clean)
        extracted['tempat_tgl_lahir'] = ttl_clean.strip()
    
    # Fallback: cari pola kota + tanggal langsung (LANI JAYA, 01- -11-2007)
    if 'tempat_tgl_lahir' not in extracted:
        ttl_fallback = re.search(r'([A-Z]+(?:\s+[A-Z]+)?),?\s*(\d{1,2}[-\s]*\d{2}[-/]\d{4})', text)
        if ttl_fallback:
            kota = ttl_fallback.group(1).strip()
            tgl = ttl_fallback.group(2).strip().replace(' ', '-')
            tgl = re.sub(r'(\d)-(\d{2})-', r'\1-\2-', tgl)
            extracted['tempat_tgl_lahir'] = f'{kota}, {tgl}'
    
    # Fallback 2: cari tanggal saja jika kota tidak jelas
    if 'tempat_tgl_lahir' not in extracted:
        date_only = re.search(r'(\d{1,2}[-\s]+\d{2}[-/]\d{4})', text)
        if date_only:
            tgl = date_only.group(1).strip().replace(' ', '-')
            tgl = re.sub(r'(\d)-(\d{2})-', r'\1-\2-', tgl)
            extracted['tempat_tgl_lahir'] = tgl
    
    # Ekstrak Jenis Kelamin (handle OCR error: LAKELAKI, LAKILAKI, LAKI LAKI)
    if re.search(r'LAKI[-\s]*LAKI|LAKELAKI|LAKILAKI', text):
        extracted['jenis_kelamin'] = 'LAKI-LAKI'
    elif re.search(r'PEREMPUAN', text):
        extracted['jenis_kelamin'] = 'PEREMPUAN'
    
    # Fallback untuk jenis kelamin: cari "LAK" atau "PER" jika text sangat rusak
    if 'jenis_kelamin' not in extracted:
        if re.search(r'\bLAK\b', text):
            extracted['jenis_kelamin'] = 'LAKI-LAKI'
        elif re.search(r'\bPER\b', text):
            extracted['jenis_kelamin'] = 'PEREMPUAN'
    
    # Ekstrak Alamat (cari JL./Jalan diikuti teks sampai angka RT/RW atau NO)
    alamat_match = re.search(r'(J[AL]\.?\s+[A-Z][A-Z\s]*?)(?=\s*NO\s*\d|\s*\d{3}/\d{3}|\s*RT)', text)
    if not alamat_match:
        # Fallback: cari "JL" atau "JALAN" sampai ketemu angka
        alamat_match = re.search(r'(J[AL][A-Z\s\.]*?)(?=\s+NO|\s+\d{3})', text)
    if alamat_match:
        extracted['alamat'] = alamat_match.group(1).strip()
    
    # Ekstrak RT/RW (handle format rusak: "RT/RW" tanpa angka jelas)
    rt_rw_match = re.search(r'(\d{3}[/\\]\d{3,4})', text)
    if not rt_rw_match:
        # Fallback: cari pattern "000/000" atau serupa
        rt_rw_match = re.search(r'(0+\s*/\s*0+)', text)
    if rt_rw_match:
        extracted['rt_rw'] = rt_rw_match.group(1).replace(' ', '')
    
    # Ekstrak Kel/Desa (handle OCR error: Kei/Desa, text tanpa RT/RW jelas)
    # Cari setelah "RT/RW" atau pattern "Kei/Desa"
    kel_match = re.search(r'(?:Kei|Kel)[/\\]Desa\s*[:>\-\s]*([A-Z]+(?:\s+[A-Z]+)*)', text, re.IGNORECASE)
    if not kel_match:
        # Fallback: cari kata ALL CAPS setelah "RT/RW" atau angka RT/RW
        rt_pattern = r'(?:RT/RW|RTIRW|0+\s*/\s*0+)'
        rt_match = re.search(rt_pattern, text)
        if rt_match:
            after_rt = text[rt_match.end():]
            kel_match = re.search(r'([A-Z]+(?:\s+[A-Z]+)?)(?=\s+(?:KECAMA|KECAMATAN|AGAMA|STATUS)|$)', after_rt)
    if kel_match:
        kel_value = kel_match.group(1).strip()
        if kel_value not in ['KECAMATAN', 'AGAMA', 'STATUS', 'Kecamatan']:
            extracted['kel_desa'] = kel_value
    
    # Ekstrak Kecamatan (handle OCR error: Kecama, Kecamtan)
    kec_match = re.search(r'(?:Kecama|Kecamatan)\s*[:>\-\s]*([A-Z]+(?:\s+[A-Z]+)*)', text, re.IGNORECASE)
    if not kec_match:
        # Fallback: kata ALL CAPS sebelum Agama atau setelah Kel/Desa
        kec_match = re.search(r'([A-Z]+)(?=\s+(?:KRISTEN|ISLAM|KATOLIK|HINDU|BUDDHA))', text)
    if not kec_match:
        # Fallback 2: cari "HUBIKIAK" atau nama kecamatan Papua yang umum
        kec_match = re.search(r'(HUBIKIAK|WAMENA|SENTANI|JAYAPURA|[A-Z]{5,})(?=\s+(?:KRISTEN|ISLAM|AGAMA))', text)
    if kec_match:
        extracted['kecamatan'] = kec_match.group(1).strip()
    
    # Ekstrak Agama
    agama_match = re.search(r'(KRISTEN|ISLAM|KATOLIK|HINDU|BUDDHA|KONGHUCU)', text)
    if agama_match:
        extracted['agama'] = agama_match.group(1)
    
    # Ekstrak Status Perkawinan
    if re.search(r'BELUM KAWIN', text):
        extracted['status_perkawinan'] = 'BELUM KAWIN'
    elif re.search(r'KAWIN', text):
        extracted['status_perkawinan'] = 'KAWIN'
    
    # Ekstrak Pekerjaan
    pekerjaan_match = re.search(r'(MAHASISWA|PEGAWAI NEGERI|SWASTA|BURUH|PETANI|GURU|DOKTER)', text)
    if pekerjaan_match:
        extracted['pekerjaan'] = pekerjaan_match.group(1)
    
    # Ekstrak Kewarganegaraan
    if re.search(r'WNI', text):
        extracted['kewarganegaraan'] = 'WNI'
    elif re.search(r'WNA', text):
        extracted['kewarganegaraan'] = 'WNA'
    
    return extracted


def _parse_ktp_normal_format(text):
    """Parse KTP dengan format normal (label: value per baris)."""
    extracted = {}
    
    # NIK
    nik_pattern = r'NIK[:>\-\s]+([\d\s\.]{16,20})'
    nik_match = re.search(nik_pattern, text, re.IGNORECASE)
    if nik_match:
        nik_raw = nik_match.group(1).replace(' ', '').replace('.', '')
        nik_digits = re.findall(r'\d', nik_raw)
        if len(nik_digits) >= 16:
            extracted['nik'] = ''.join(nik_digits)[:16]
    
    if 'nik' not in extracted:
        all_digits = re.findall(r'\b\d{16}\b', text.replace(' ', '').replace('.', ''))
        if all_digits:
            extracted['nik'] = all_digits[0]
    
    # Nama
    nama_pattern = r'Nama[:>\-\s]+([A-Z][A-Za-z\s\.\-]+?)(?:Tempat|Tgl|\d{2}-\d{2}-\d{4}|\n|$)'
    nama_match = re.search(nama_pattern, text, re.IGNORECASE)
    if nama_match:
        extracted['nama'] = nama_match.group(1).strip()
    
    if 'nama' not in extracted:
        simple_nama = re.search(r'Nama[:>\-\s]+([A-Z][A-Z\s]+)', text)
        if simple_nama:
            extracted['nama'] = simple_nama.group(1).strip()
    
    # Tempat/Tgl Lahir
    ttl_pattern = r'Tempat[/\\s]*(?:Tgl|Tal|Tanggal)\s*Lahir[:>\-\s]+(.+?)(?:Jenis|Kelamin|\n|$)'
    ttl_match = re.search(ttl_pattern, text, re.IGNORECASE)
    if ttl_match:
        ttl_raw = ttl_match.group(1).strip()
        ttl_clean = re.sub(r'(\d{2}[-/]\d{2}[-/]\d{4}).*$', r'\1', ttl_raw)
        extracted['tempat_tgl_lahir'] = ttl_clean.strip()
    
    # Alamat
    alamat_pattern = r'Alamat[:\s]+(.+?)(?:RT/RW|\n|$)'
    alamat_match = re.search(alamat_pattern, text, re.IGNORECASE)
    if alamat_match:
        extracted['alamat'] = alamat_match.group(1).strip()
    
    # RT/RW
    rt_rw_pattern = r'RT/RW[:\s]*(\d{3}/\d{3})'
    rt_rw_match = re.search(rt_rw_pattern, text)
    if rt_rw_match:
        extracted['rt_rw'] = rt_rw_match.group(1)
    
    # Kel/Desa
    kel_pattern = r'Kel/Desa[:\s]+(.+?)(?:Kecamatan|\n|$)'
    kel_match = re.search(kel_pattern, text, re.IGNORECASE)
    if kel_match:
        extracted['kel_desa'] = kel_match.group(1).strip()
    
    # Kecamatan
    kec_pattern = r'Kecamatan[:\s]+(.+?)(?:Agama|\n|$)'
    kec_match = re.search(kec_pattern, text, re.IGNORECASE)
    if kec_match:
        extracted['kecamatan'] = kec_match.group(1).strip()
    
    # Agama
    agama_pattern = r'Agama[:\s]+(.+?)(?:Status|\n|$)'
    agama_match = re.search(agama_pattern, text, re.IGNORECASE)
    if agama_match:
        extracted['agama'] = agama_match.group(1).strip()
    
    # Status Perkawinan
    status_pattern = r'Status[:\s]+(.+?)(?:Pekerjaan|\n|$)'
    status_match = re.search(status_pattern, text, re.IGNORECASE)
    if status_match:
        extracted['status_perkawinan'] = status_match.group(1).strip()
    
    # Pekerjaan
    pekerjaan_pattern = r'Pekerjaan[:\s]+(.+?)(?:Kewarganegaraan|\n|$)'
    pekerjaan_match = re.search(pekerjaan_pattern, text, re.IGNORECASE)
    if pekerjaan_match:
        extracted['pekerjaan'] = pekerjaan_match.group(1).strip()
    
    # Kewarganegaraan
    warga_pattern = r'Kewarganegaraan[:\s]+(.+?)(?:Berlaku|\n|$)'
    warga_match = re.search(warga_pattern, text, re.IGNORECASE)
    if warga_match:
        extracted['kewarganegaraan'] = warga_match.group(1).strip()
    
    return extracted
