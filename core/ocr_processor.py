"""
OCR Processor untuk SIPPER - Ekstraksi data dari KTP dan KK menggunakan Tesseract OCR
"""
import re
import cv2
import numpy as np
from PIL import Image
import pytesseract
from django.utils import timezone
import platform
from .ktp_parser import parse_ktp_data

# Set Tesseract path untuk Windows
if platform.system() == 'Windows':
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for path in tesseract_paths:
        import os
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break


def preprocess_image(image_path, aggressive=False):
    """
    Preprocessing gambar untuk meningkatkan akurasi OCR:
    - Resize jika terlalu kecil
    - Konversi ke grayscale
    - Thresholding biner (opsional, hanya untuk foto scan)
    - Denoising
    
    Parameter 'aggressive': set False untuk gambar digital/text-based,
                            True untuk foto scan KTP/KK asli
    """
    # Load image dengan Pillow (mendukung berbagai format)
    img = Image.open(image_path)
    
    # Konversi ke RGB jika RGBA/PNG transparan
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Konversi ke OpenCV format
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    # Resize jika terlalu kecil (minimum 300px lebar untuk OCR baik)
    height, width = img_cv.shape[:2]
    if width < 800:
        scale = 800 / width
        img_cv = cv2.resize(img_cv, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Konversi ke grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Untuk gambar digital/text-based (kontras sudah tinggi), skip thresholding
    if not aggressive:
        # Hanya denoise ringan
        denoised = cv2.fastNlMeansDenoising(gray, h=5)
        return denoised
    
    # Untuk foto scan: adaptive thresholding + denoise kuat
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(binary, h=10)
    
    return denoised


def extract_text_from_image(image_path, lang='ind+eng', aggressive_preprocess=False):
    """
    Ekstrak teks dari gambar menggunakan Tesseract OCR.
    Mengembalikan dict dengan text mentah dan confidence score.
    
    Parameter 'aggressive_preprocess': set True untuk foto scan KTP/KK,
                                       False untuk gambar digital/text-based
    """
    try:
        # Load image
        img = Image.open(image_path)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Untuk foto KTP asli, pakai preprocessing + auto PSM selection
        if aggressive_preprocess:
            processed_img = preprocess_image(image_path, aggressive=True)
            return _extract_with_best_psm(processed_img, lang)
        
        # Untuk gambar digital: coba tanpa preprocessing, gunakan PSM 3 (auto)
        data = pytesseract.image_to_data(img, lang=lang, config='--oem 3 --psm 3', output_type=pytesseract.Output.DICT)
        result = _build_result(data)
        
        # Jika hasil buruk, fallback ke preprocessing ringan
        if result['confidence'] < 50 or len(result['text']) < 50:
            processed_img = preprocess_image(image_path, aggressive=False)
            data = pytesseract.image_to_data(processed_img, lang=lang, config='--oem 3 --psm 3', output_type=pytesseract.Output.DICT)
            result = _build_result(data)
        
        return result
    
    except Exception as e:
        return {
            'text': '',
            'confidence': 0,
            'error': str(e),
        }


def _extract_with_best_psm(img, lang):
    """Coba beberapa PSM mode dan return hasil dengan confidence tertinggi."""
    best_result = None
    best_confidence = 0
    
    # PSM modes yang cocok untuk dokumen KTP
    psm_modes = [3, 11, 12, 6]  # Auto > Sparse > Uniform
    
    for psm in psm_modes:
        try:
            config = f'--oem 3 --psm {psm}'
            data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DICT)
            result = _build_result(data)
            
            if result['confidence'] > best_confidence and len(result['text']) > 50:
                best_confidence = result['confidence']
                best_result = result
        except:
            continue
    
    return best_result or {'text': '', 'confidence': 0, 'error': 'All PSM modes failed'}


def _build_result(data):
    """Build result dict from pytesseract output."""
    texts = []
    confidences = []
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        conf = float(data['conf'][i])
        if text and conf > 30:
            texts.append(text)
            confidences.append(conf)
    
    full_text = ' '.join(texts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        'text': full_text,
        'confidence': round(avg_confidence, 2),
        'words': texts,
        'word_confidences': confidences,
    }


def parse_ktp_data(ocr_result):
    """
    Parse data spesifik dari hasil OCR KTP Indonesia.
    Mengekstrak: NIK, Nama, Tempat/Tgl Lahir, Alamat, RT/RW, Kel/Desa, Kecamatan, Agama, Status, Pekerjaan.
    """
    text = ocr_result.get('text', '')
    extracted = {}
    
    # Pattern untuk NIK (16 digit angka, mungkin dengan spasi atau titik)
    # Handle berbagai separator: :, >, -, atau whitespace
    nik_pattern = r'NIK[:>\-\s]+([\d\s\.]{16,20})'
    nik_match = re.search(nik_pattern, text, re.IGNORECASE)
    if nik_match:
        nik_raw = nik_match.group(1).replace(' ', '').replace('.', '')
        # Ambil hanya 16 digit pertama yang valid
        nik_digits = re.findall(r'\d', nik_raw)
        if len(nik_digits) >= 16:
            extracted['nik'] = ''.join(nik_digits)[:16]
    
    # Fallback: cari 16 digit berurutan di seluruh text jika pattern NIK tidak ketemu
    if 'nik' not in extracted:
        all_digits = re.findall(r'\b\d{16}\b', text.replace(' ', '').replace('.', ''))
        if all_digits:
            extracted['nik'] = all_digits[0]
    
    # Pattern untuk Nama (setelah label "Nama")
    # Handle berbagai separator dan format, termasuk karakter noise dari OCR
    nama_pattern = r'Nama[:>\-\s]+([A-Z][A-Za-z\s\.\-]+?)(?:Tempat|Tgl|\d{2}-\d{2}-\d{4}|JAKARTA|\n|$)'
    nama_match = re.search(nama_pattern, text, re.IGNORECASE)
    if nama_match:
        extracted['nama'] = nama_match.group(1).strip()
    
    # Fallback: jika nama belum ketemu, cari setelah "Nama:" sampai akhir baris atau angka tanggal
    if 'nama' not in extracted:
        simple_nama = re.search(r'Nama[:>\-\s]+([A-Z][A-Z\s]+)', text)
        if simple_nama:
            extracted['nama'] = simple_nama.group(1).strip()
    
    # Pattern untuk Tempat/Tgl Lahir
    # Handle variasi OCR: Tgl, Tal, Tanggal
    ttl_pattern = r'Tempat[/\\s]*(?:Tgl|Tal|Tanggal)\s*Lahir[:>\-\s]+(.+?)(?:Jenis|Kelamin|\n|$)'
    ttl_match = re.search(ttl_pattern, text, re.IGNORECASE)
    if ttl_match:
        ttl_raw = ttl_match.group(1).strip()
        # Bersihkan noise: hapus kata acak setelah tanggal (DD-MM-YYYY atau DD/MM/YYYY)
        # Ambil hanya bagian sampai pola tanggal
        ttl_clean = re.sub(r'(\d{2}[-/]\d{2}[-/]\d{4}).*$', r'\1', ttl_raw)
        extracted['tempat_tgl_lahir'] = ttl_clean.strip()
    
    # Pattern untuk Alamat
    alamat_pattern = r'Alamat[:\s]+(.+?)(?:RT/RW|\n|$)'
    alamat_match = re.search(alamat_pattern, text, re.IGNORECASE)
    if alamat_match:
        extracted['alamat'] = alamat_match.group(1).strip()
    
    # Pattern untuk RT/RW
    rt_rw_pattern = r'RT/RW[:\s]*(\d{3}/\d{3})'
    rt_rw_match = re.search(rt_rw_pattern, text)
    if rt_rw_match:
        extracted['rt_rw'] = rt_rw_match.group(1)
    
    # Pattern untuk Kel/Desa
    kel_pattern = r'Kel/Desa[:\s]+(.+?)(?:Kecamatan|\n|$)'
    kel_match = re.search(kel_pattern, text, re.IGNORECASE)
    if kel_match:
        extracted['kel_desa'] = kel_match.group(1).strip()
    
    # Pattern untuk Kecamatan
    kec_pattern = r'Kecamatan[:\s]+(.+?)(?:Agama|\n|$)'
    kec_match = re.search(kec_pattern, text, re.IGNORECASE)
    if kec_match:
        extracted['kecamatan'] = kec_match.group(1).strip()
    
    return extracted


def parse_kk_data(ocr_result):
    """
    Parse data spesifik dari hasil OCR Kartu Keluarga.
    Mengekstrak: No. KK, Nama Kepala Keluarga, Alamat, RT/RW, Kode Provinsi, dll.
    """
    text = ocr_result.get('text', '')
    extracted = {}
    
    # Pattern untuk No. KK (16 digit)
    kk_pattern = r'No\.\s*Kartu\s*Keluarga[:\s]*([\d\s\.]{16,20})'
    kk_match = re.search(kk_pattern, text, re.IGNORECASE)
    if not kk_match:
        # Alternatif pattern
        kk_pattern = r'(\d{16})'
        kk_match = re.search(kk_pattern, text)
    
    if kk_match:
        kk_raw = kk_match.group(1).replace(' ', '').replace('.', '')
        kk_digits = re.findall(r'\d', kk_raw)
        if len(kk_digits) >= 16:
            extracted['no_kk'] = ''.join(kk_digits)[:16]
    
    # Pattern untuk Nama Kepala Keluarga
    kepala_pattern = r'Nama\s*Kepala\s*Keluarga[:\s]+(.+?)(?:Alamat|\n|$)'
    kepala_match = re.search(kepala_pattern, text, re.IGNORECASE)
    if kepala_match:
        extracted['nama_kepala_keluarga'] = kepala_match.group(1).strip()
    
    # Pattern untuk Alamat
    alamat_pattern = r'Alamat[:\s]+(.+?)(?:RT/RW|\n|$)'
    alamat_match = re.search(alamat_pattern, text, re.IGNORECASE)
    if alamat_match:
        extracted['alamat'] = alamat_match.group(1).strip()
    
    return extracted


def process_document(dokumen_obj):
    """
    Proses lengkap: ekstrak teks dari file dokumen, parse data spesifik,
    dan simpan hasil ke model Dokumen.
    
    Args:
        dokumen_obj: Instance model Dokumen
    
    Returns:
        dict dengan hasil pemrosesan
    """
    from django.conf import settings
    import os
    
    # Dapatkan path file absolut
    file_path = dokumen_obj.file.path
    
    # Cek apakah file ada
    if not os.path.exists(file_path):
        return {
            'success': False,
            'error': f'File tidak ditemukan: {file_path}',
        }
    
    # Tentukan jenis dokumen
    jenis = dokumen_obj.jenis
    
    # Ekstrak teks
    ocr_result = extract_text_from_image(file_path)
    
    if ocr_result.get('error'):
        return {
            'success': False,
            'error': f'OCR gagal: {ocr_result["error"]}',
        }
    
    # Parse data berdasarkan jenis
    if jenis == 'ktp':
        parsed_data = parse_ktp_data(ocr_result)
    elif jenis == 'kk':
        parsed_data = parse_kk_data(ocr_result)
    else:
        parsed_data = {}
    
    # Update model
    dokumen_obj.ocr_text = ocr_result['text']
    dokumen_obj.ocr_confidence = ocr_result['confidence']
    dokumen_obj.extracted_nik = parsed_data.get('nik')
    dokumen_obj.extracted_data = parsed_data
    dokumen_obj.ocr_processed_at = timezone.now()
    
    # Auto-verifikasi sederhana: jika NIK dari OCR cocok dengan NIK penduduk
    if parsed_data.get('nik') and dokumen_obj.penduduk.nik == parsed_data['nik']:
        dokumen_obj.ai_verified = True
        dokumen_obj.ai_verification_notes = f'NIK cocok: {parsed_data["nik"]}'
    else:
        dokumen_obj.ai_verified = False
        dokumen_obj.ai_verification_notes = 'Menunggu verifikasi manual petugas'
    
    dokumen_obj.save()
    
    return {
        'success': True,
        'ocr_text': ocr_result['text'],
        'confidence': ocr_result['confidence'],
        'parsed_data': parsed_data,
        'ai_verified': dokumen_obj.ai_verified,
        'notes': dokumen_obj.ai_verification_notes,
    }
