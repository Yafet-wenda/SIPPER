# Install Tesseract OCR and Indonesian language data on Windows.

$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $scriptPath = $PSCommandPath
    $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $scriptPath
    $elevated = Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') `
        -ArgumentList $arguments -Verb RunAs -Wait -PassThru
    exit $elevated.ExitCode
}

$tesseractBin = 'C:\Program Files\Tesseract-OCR'
$tesseractExe = Join-Path $tesseractBin 'tesseract.exe'
$indonesianData = Join-Path $tesseractBin 'tessdata\ind.traineddata'
$installerUrl = 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe'
$languageUrl = 'https://github.com/tesseract-ocr/tessdata_fast/raw/refs/heads/main/ind.traineddata'
$installerPath = Join-Path $env:TEMP 'tesseract-installer.exe'
$languagePath = Join-Path $env:TEMP 'tesseract-ind.traineddata'

try {
    if (-not (Test-Path -LiteralPath $tesseractExe)) {
        Write-Host 'Mengunduh Tesseract OCR...'
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
        Write-Host 'Download selesai, menginstall...'
        $installer = Start-Process -FilePath $installerPath `
            -ArgumentList '/S', "/D=$tesseractBin" -Wait -PassThru
        if ($installer.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $tesseractExe)) {
            throw 'Instalasi Tesseract gagal.'
        }
    }

    if (-not (Test-Path -LiteralPath $indonesianData)) {
        Write-Host 'Mengunduh data bahasa Indonesia...'
        Invoke-WebRequest -Uri $languageUrl -OutFile $languagePath -UseBasicParsing
        if ((Get-Item -LiteralPath $languagePath).Length -lt 100000) {
            throw 'Berkas data bahasa Indonesia tidak lengkap.'
        }
        Copy-Item -LiteralPath $languagePath -Destination $indonesianData -Force
    }

    $currentPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($currentPath -notlike "*$tesseractBin*") {
        [Environment]::SetEnvironmentVariable('Path', "$currentPath;$tesseractBin", 'User')
        Write-Host "PATH ditambahkan: $tesseractBin"
    }
    $env:Path += ";$tesseractBin"

    & $tesseractExe --version
    if ($LASTEXITCODE -ne 0) {
        throw 'Tesseract tidak dapat dijalankan.'
    }
    $languages = & $tesseractExe --list-langs
    if ($LASTEXITCODE -ne 0 -or $languages -notcontains 'ind' -or $languages -notcontains 'eng') {
        throw 'Data bahasa Indonesia dan Inggris belum tersedia.'
    }
    Write-Host 'Tesseract siap digunakan dengan bahasa Indonesia dan Inggris.'
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}
finally {
    foreach ($temporaryFile in @($installerPath, $languagePath)) {
        if (Test-Path -LiteralPath $temporaryFile) {
            Remove-Item -LiteralPath $temporaryFile -Force
        }
    }
}
