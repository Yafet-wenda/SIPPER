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


# Confidence di bawah angka ini menandakan berkas bukan tangkapan layar bersih.
# Angkanya dari pengujian laporan: gambar digital selalu > 90%, foto KTP asli
# berkisar 40-70% -> hanya kelompok kedua yang perlu praproses agresif.
AMBAT_PREPROCESS = 70.0


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


def _tandai_belum_dinilai(dokumen_obj, catatan):
    """Simpan alasan mesin tidak bisa menilai berkas.

    Tanpa ini panel review hanya menampilkan baris kosong dan petugas tidak tahu
    apakah berkasnya belum diproses, gagal dibaca, atau memang tidak dinilai.
    """
    dokumen_obj.ai_score = None
    dokumen_obj.ai_prescreen = 'belum_dinilai'
    dokumen_obj.ai_verified = False
    dokumen_obj.ai_verification_notes = catatan
    dokumen_obj.save(update_fields=[
        'ai_score', 'ai_prescreen', 'ai_verified', 'ai_verification_notes',
    ])


def ekstrak_dengan_pilihan_praproses(file_path, lang='ind+eng'):
    """Pilih jalur OCR berdasarkan hasil, bukan berdasarkan nama berkas.

    Laporan menjanjikan "conditional preprocessing": gambar digital cukup dibaca
    polos, foto hasil pindai perlu thresholding. Jenis berkas tidak bisa dipercaya
    dari ekstensi, jadi pemilihannya berbasis hasil: confidence rendah diulang
    lewat jalur agresif, dan yang teksnya lebih meyakinkan yang dipakai.
    """
    polos = extract_text_from_image(file_path, lang=lang)
    if polos.get('error') or polos.get('confidence', 0) >= AMBAT_PREPROCESS:
        return polos
    praproses = extract_text_from_image(file_path, lang=lang, aggressive_preprocess=True)
    if not praproses.get('error') and praproses.get('confidence', 0) > polos.get('confidence', 0):
        return praproses
    return polos


def process_document(dokumen_obj):
    """Proses lengkap: ekstrak teks, parse field KTP/KK, lalu nilai kecocokannya.

    Args:
        dokumen_obj: Instance model Dokumen

    Returns:
        dict hasil pemrosesan. ``skipped`` True berarti berkas sengaja tidak
        dinilai mesin (mis. PDF), bukan kegagalan yang perlu diulang.
    """
    import os

    from .ai_verifikasi import nilai_berkas

    # Dapatkan path file absolut
    try:
        file_path = dokumen_obj.file.path
    except (ValueError, OSError):
        _tandai_belum_dinilai(dokumen_obj, 'Berkas tidak terdaftar di penyimpanan, OCR tidak bisa jalan.')
        return {'success': False, 'error': 'Berkas tidak terdaftar di penyimpanan.'}

    # Cek apakah file ada
    if not os.path.exists(file_path):
        _tandai_belum_dinilai(dokumen_obj, f'Berkas hilang dari penyimpanan: {os.path.basename(file_path)}')
        return {'success': False, 'error': f'File tidak ditemukan: {file_path}'}

    # Tesseract hanya menerima gambar. PDF dulunya gagal dengan pesan error PIL
    # yang tidak menjelaskan apa pun di log; sekarang sebabnya ditulis terang.
    if file_path.lower().endswith('.pdf'):
        catatan = (
            'Berkas PDF belum bisa dibaca OCR: Tesseract menerima gambar, '
            'ekstraksi halaman PDF belum dipasang. Unggah ulang halaman terkait '
            'sebagai JPG/PNG bila ingin dinilai mesin.'
        )
        _tandai_belum_dinilai(dokumen_obj, catatan)
        return {'success': False, 'skipped': True, 'error': catatan}

    # Tentukan jenis dokumen
    jenis = dokumen_obj.jenis

    # Ekstrak teks
    ocr_result = ekstrak_dengan_pilihan_praproses(file_path)

    if ocr_result.get('error'):
        _tandai_belum_dinilai(dokumen_obj, f'Teks berkas gagal dibaca mesin: {ocr_result["error"]}')
        return {
            'success': False,
            'error': f'OCR gagal: {ocr_result["error"]}',
        }

    # Parse data berdasarkan jenis. parse_ktp_data diambil dari core/ktp_parser.py:
    # satu-satunya versi yang mengenal format kolom. File ini dulu mendefinisikan
    # ulang nama yang sama sehingga parser lengkap itu tidak pernah terpakai.
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

    # Prapemilahan AI (laporan "Validasi agentik AI"): bandingkan hasil OCR
    # dengan isian formulir, lalu tentukan Valid / Perlu review manual dari
    # ambang 85%.
    hasil = nilai_berkas(
        dokumen_obj.penduduk, parsed_data, ocr_result['confidence'], jenis,
    )
    dokumen_obj.ai_score = hasil['skor']
    dokumen_obj.ai_prescreen = hasil['prescreen']
    dokumen_obj.ai_verified = hasil['prescreen'] == 'valid'
    dokumen_obj.ai_verification_notes = hasil['catatan']

    # Hanya kolom hasil OCR/AI yang ditulis. Simpan penuh akan menimpa kolom lain
    # dengan isi salinan yang dibaca thread ini sebelum Tesseract jalan — prosesnya
    # bisa sampai puluhan detik — sehingga keputusan petugas yang baru masuk di tab
    # lain hilang tanpa jejak. Panel review berjanji "mesin tidak pernah
    # mengubah status dokumen"; janji itu hanya benar kalau status tidak ikut
    # ditulis kembali, walaupun nilainya basi.
    dokumen_obj.save(update_fields=[
        'ocr_text', 'ocr_confidence', 'extracted_nik', 'extracted_data',
        'ocr_processed_at', 'ai_score', 'ai_prescreen', 'ai_verified',
        'ai_verification_notes',
    ])

    return {
        'success': True,
        'ocr_text': ocr_result['text'],
        'confidence': ocr_result['confidence'],
        'parsed_data': parsed_data,
        'ai_verified': dokumen_obj.ai_verified,
        'skor': dokumen_obj.ai_score,
        'prescreen': dokumen_obj.ai_prescreen,
        'notes': dokumen_obj.ai_verification_notes,
    }
