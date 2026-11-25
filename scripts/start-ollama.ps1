param(
    [string]$Model = $env:OLLAMA_MODEL
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env'
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            if (-not (Get-Item "Env:$name" -ErrorAction SilentlyContinue)) {
                Set-Item "Env:$name" $value
            }
        }
    }
}

if (-not $Model) {
    $Model = $env:OLLAMA_MODEL
}
if (-not $Model) {
    $Model = 'llama3.2:3b'
}

$ollamaExe = Get-Command ollama.exe -ErrorAction SilentlyContinue
if (-not $ollamaExe) {
    $candidate = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $candidate) {
        $ollamaExe = $candidate
    }
}

if (-not $ollamaExe) {
    Write-Host "Ollama belum terpasang. Unduh dari https://ollama.com/download"
    exit 1
}

$apiUrl = $env:OLLAMA_API_URL
if (-not $apiUrl) {
    $apiUrl = 'http://127.0.0.1:11434'
}
$apiUrl = $apiUrl.TrimEnd('/')

function Test-Ollama {
    try {
        Invoke-RestMethod -Uri "$apiUrl/api/tags" -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

if (-not (Test-Ollama)) {
    Write-Host "Menyalakan Ollama..."
    if ($ollamaExe -is [System.Management.Automation.ApplicationInfo]) {
        $ollamaExe = $ollamaExe.Source
    }
    Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null

    $siap = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Ollama) {
            $siap = $true
            break
        }
    }
    if (-not $siap) {
        Write-Host "Ollama gagal memulai API lokal."
        exit 1
    }
}

try {
    $tags = Invoke-RestMethod -Uri "$apiUrl/api/tags" -TimeoutSec 5
    $namaModel = @($tags.models | ForEach-Object { $_.name })
    $adaModel = $namaModel -contains $Model
    if (-not $adaModel) {
        $adaModel = @($namaModel | Where-Object { $_ -like "$Model*" }).Count -gt 0
    }

    if (-not $adaModel) {
        Write-Host "Mengunduh model Ollama $Model..."
        & $ollamaExe pull $Model
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Model $Model gagal diunduh."
            exit 1
        }
    }
}
catch {
    Write-Host "Ollama aktif, tetapi model tidak dapat diperiksa: $($_.Exception.Message)"
    exit 1
}

Write-Host "Ollama siap dengan model $Model."
