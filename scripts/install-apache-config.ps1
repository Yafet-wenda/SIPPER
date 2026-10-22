# =====================================================================
#  Memasang konfigurasi Apache yang dibutuhkan prod.bat.
#
#  Kerjanya tiga hal, semuanya di <XAMPP>\apache\conf:
#    1. menyalin apache\sipper-httpd.conf (template di repo) menjadi
#       conf\extra\httpd-sipper.conf, dengan __PROJECT_ROOT__ diganti lokasi
#       folder proyek ini;
#    2. mengaktifkan LoadModule proxy_http_module (XAMPP membawanya tapi
#       membiarkannya dikomentari, sehingga ProxyPass ke waitress berbalas 502);
#    3. menambahkan baris Include ke httpd.conf.
#
#  Sebelum menyentuh apa pun file lama dicadangkan sebagai *.bak-sipper-STAMP,
#  dan kalau "httpd -t" menolak hasil susunannya kedua file dikembalikan.
#  Apache baru disentuh kalau flag -Restart diberikan.
#
#  Cara pakai (dari folder proyek):
#      powershell -ExecutionPolicy Bypass -File scripts\install-apache-config.ps1
#      powershell -ExecutionPolicy Bypass -File scripts\install-apache-config.ps1 -Restart
#  Lokasi XAMPP dideteksi otomatis; kalau berada di tempat lain:
#      ... -ApacheHome E:\xampp
# =====================================================================
param(
    [string]$ApacheHome,
    [switch]$Restart,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot

# ---- lokasi Apache ----------------------------------------------------------
if (-not $ApacheHome) { $ApacheHome = $env:XAMPP_HOME }
if (-not $ApacheHome) {
    foreach ($kandidat in 'C:\xampp', 'D:\xampp', 'F:\xampp') {
        if (Test-Path (Join-Path $kandidat 'apache\bin\httpd.exe')) { $ApacheHome = $kandidat; break }
    }
}
if (-not $ApacheHome) {
    $httpd = Get-Command httpd.exe -ErrorAction SilentlyContinue
    if ($httpd) { $ApacheHome = Split-Path -Parent (Split-Path -Parent $httpd.Source) }
}
if (-not $ApacheHome -or -not (Test-Path (Join-Path $ApacheHome 'apache\bin\httpd.exe'))) {
    throw 'Apache tidak ditemukan. Jalankan ulang dengan -ApacheHome E:\xampp (isi dengan lokasi XAMPP Anda).'
}

$bin        = Join-Path $ApacheHome 'apache\bin'
$confDir    = Join-Path $ApacheHome 'apache\conf'
$extraDir   = Join-Path $confDir 'extra'
$httpdConf  = Join-Path $confDir 'httpd.conf'
$targetConf = Join-Path $extraDir 'httpd-sipper.conf'
$template   = Join-Path $repoRoot 'apache\sipper-httpd.conf'

Write-Host "  proyek : $repoRoot"
Write-Host "  Apache : $ApacheHome"

if (-not (Test-Path $template)) { throw "Template tidak ditemukan: $template" }

# ---- susun isi httpd-sipper.conf -------------------------------------------
$projectSlash  = $repoRoot.TrimEnd('\', '/').Replace('\', '/')
$staticDir     = Join-Path $repoRoot 'staticfiles'
$desired       = (Get-Content -Raw -LiteralPath $template).Replace('__PROJECT_ROOT__', $projectSlash)

if (-not (Test-Path (Join-Path $staticDir 'admin')) -and -not $DryRun) {
    Write-Warning 'staticfiles\ belum berisi hasil collectstatic - Alias /static/ akan memberi 404.'
    Write-Warning 'Jalankan:  .venv\Scripts\python.exe manage.py collectstatic --noinput'
}

# ---- sunting httpd.conf (mod_proxy_http + Include) -------------------------
$httpdText = Get-Content -Raw -LiteralPath $httpdConf

if ($httpdText -match '(?m)^\s*LoadModule proxy_module') {
    if ($httpdText -match '(?m)^\s*#?\s*LoadModule proxy_http_module\s+modules/mod_proxy_http\.so') {
        $httpdText = $httpdText -replace '(?m)^\s*#\s*(LoadModule proxy_http_module\s+modules/mod_proxy_http\.so)', '$1'
    } else {
        $httpdText = $httpdText -replace '(?m)^(\s*LoadModule proxy_module\s+modules/mod_proxy\.so[^\r\n]*)', "`$1`r`nLoadModule proxy_http_module modules/mod_proxy_http.so"
    }
    Write-Host '  mod_proxy_http : aktif'
} else {
    throw 'mod_proxy sendiri tidak dimuat di httpd.conf. Aktifkan dulu LoadModule proxy_module.'
}

if ($httpdText -notmatch '(?m)^\s*LoadModule headers_module') {
    Write-Warning 'mod_headers tidak aktif - baris "Header set Cache-Control" di template akan membuat httpd -t gagal.'
}

$includeLine = 'Include "conf/extra/httpd-sipper.conf"'
if ($httpdText -notmatch [regex]::Escape($includeLine)) {
    $anchor = 'Include "conf/extra/httpd-xampp.conf"'
    if ($httpdText.Contains($anchor)) {
        $httpdText = $httpdText.Replace($anchor, $anchor + "`r`n" + $includeLine)
    } else {
        $httpdText = $httpdText.TrimEnd("`r", "`n") + "`r`n`r`n" + $includeLine + "`r`n"
    }
    Write-Host '  Include        : ditambahkan'
} else {
    Write-Host '  Include        : sudah ada'
}

if ($DryRun) {
    Write-Host "`n  DRY RUN - tidak ada file yang diubah."
    Write-Host "  akan menulis : $targetConf"
    Write-Host '  akan menulis : httpd.conf (mod_proxy_http + Include)'
    exit 0
}

# ---- cadangkan, tulis, uji, gulung balik kalau gagal -----------------------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bakHttpd = "$httpdConf.bak-sipper-$stamp"
Copy-Item -LiteralPath $httpdConf -Destination $bakHttpd
$bakTarget = $null
if (Test-Path -LiteralPath $targetConf) {
    $bakTarget = "$targetConf.bak-sipper-$stamp"
    Copy-Item -LiteralPath $targetConf -Destination $bakTarget
}
Write-Host "  cadangan     : $bakHttpd"

Set-Content -LiteralPath $targetConf -Value $desired -Encoding ascii -NoNewline
Set-Content -LiteralPath $httpdConf  -Value $httpdText -Encoding ascii -NoNewline

Push-Location $ApacheHome
try {
    # httpd menulis "Syntax OK" di stderr. Dengan ErrorActionPreference=Stop,
    # PowerShell mengubah setiap baris stderr menjadi NativeCommandError dan
    # menghentikan skrip di tengah jalan. cmd /c menggabungkan kedua stream
    # sebelum PowerShell sempat panik, jadi teksnya bisa dibaca apa adanya.
    $testText = (& cmd.exe /c "`"$bin\httpd.exe`" -t 2>&1" | Out-String).Trim()
} finally {
    Pop-Location
}
Write-Host "  httpd -t     : $testText"

if ($testText -notmatch 'Syntax OK') {
    Copy-Item -LiteralPath $bakHttpd -Destination $httpdConf -Force
    if ($bakTarget) { Copy-Item -LiteralPath $bakTarget -Destination $targetConf -Force }
    else { Remove-Item -LiteralPath $targetConf -Force }
    throw 'Konfigurasi ditolak httpd -t. Semua file sudah dikembalikan seperti semula.'
}

Write-Host '  tersimpan, syntax OK.'

# ---- jalankan ulang Apache --------------------------------------------------
if ($Restart) {
    $pidStart = Join-Path $ApacheHome 'apache_start.bat'
    if (-not (Get-Process httpd -ErrorAction SilentlyContinue)) {
        Write-Warning 'Apache belum berjalan. Start lewat prod.bat - konfigurasi baru langsung dipakai.'
    } elseif (Get-Service -Name 'Apache*' -ErrorAction SilentlyContinue) {
        # Versi service: httpd sendiri yang menanganinya.
        Push-Location $ApacheHome
        try { & cmd.exe /c "`"$bin\httpd.exe`" -k restart 2>&1" | Out-String | Write-Host } finally { Pop-Location }
    } else {
        # Versi konsol (apache_start.bat): "-k restart" hanya bicara ke service,
        # jadi jawabnya "No installed service Apache2.4" dan konfigurasi baru tidak
        # pernah terpakai. Satu-satunya jalan adalah matikan prosesnya lalu start.bat.
        Write-Host '  restart        : Apache versi konsol, proses httpd ditutup lalu dijalankan lagi ...'
        Stop-Process -Name httpd -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        if (Test-Path -LiteralPath $pidStart) {
            Start-Process -FilePath $pidStart -WorkingDirectory $ApacheHome
        } else {
            Start-Process -FilePath (Join-Path $bin 'httpd.exe') -ArgumentList '-k', 'start' -WorkingDirectory $ApacheHome
        }
    }
    Start-Sleep -Seconds 4
    if (Get-Process httpd -ErrorAction SilentlyContinue) { Write-Host '  Apache berjalan lagi dengan konfigurasi baru.' }
    else { Write-Warning 'Apache belum hidup lagi setelah restart. Jalankan apache_start.bat; konfigurasi lama tersimpan di httpd.conf.bak-sipper-* kalau perlu digulung balik.' }
}

Write-Host "`nSelesai. Lanjutkan dengan prod.bat, lalu cek http://localhost/health/."
