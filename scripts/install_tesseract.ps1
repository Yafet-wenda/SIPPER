# Install Tesseract OCR di Windows
# Jalankan sebagai Administrator jika diperlukan

$ErrorActionPreference = 'Stop'

# Cek apakah sudah terinstall
$tesseractPath = Get-Command tesseract -ErrorAction SilentlyContinue
if ($tesseractPath) {
    Write-Host "Tesseract sudah terinstall di: $($tesseractPath.Source)" -ForegroundColor Green
    & tesseract --version
    exit 0
}

Write-Host "Mengunduh Tesseract OCR..." -ForegroundColor Cyan

# Download installer terbaru dari GitHub releases
$installerUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-v5.5.0.20241111.exe"
$installerPath = "$env:TEMP\tesseract-installer.exe"

try {
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    Write-Host "Download selesai, menginstall..." -ForegroundColor Cyan
    
    # Install silent dengan komponen bahasa Indonesia dan Inggris
    Start-Process -FilePath $installerPath -ArgumentList "/S", "/D=C:\Program Files\Tesseract-OCR" -Wait -NoNewWindow
    
    Write-Host "Instalasi selesai!" -ForegroundColor Green
    
    # Tambah ke PATH user
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $tesseractBin = "C:\Program Files\Tesseract-OCR"
    if ($currentPath -notlike "*$tesseractBin*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$tesseractBin", "User")
        Write-Host "PATH ditambahkan: $tesseractBin" -ForegroundColor Yellow
        Write-Host "Restart terminal untuk efek PATH." -ForegroundColor Yellow
    }
    
    # Verifikasi
    $env:Path += ";$tesseractBin"
    & "$tesseractBin\tesseract.exe" --version
    Write-Host "`nTesseract siap digunakan!" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "`nAlternatif: Download manual dari https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    exit 1
} finally {
    if (Test-Path $installerPath) {
        Remove-Item $installerPath -Force
    }
}
