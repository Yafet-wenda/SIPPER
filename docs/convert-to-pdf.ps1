$docxPath = Join-Path $PSScriptRoot "laporan-implementasi-ocr.docx"
$pdfPath  = Join-Path $PSScriptRoot "laporan-implementasi-ocr.pdf"

$word = New-Object -ComObject Word.Application
$word.Visible = $false

try {
    $doc = $word.Documents.Open([string]$docxPath)
    # SaveAs2 dengan nilai biasa: [ref] ditolak Word 16 lewat PowerShell 5
    # ("Cannot convert ... psobject to type Object"), dan itu membuat skrip ini
    # selama ini hanya berhasil di atas.
    $doc.SaveAs2([string]$pdfPath, 17) # 17 = wdFormatPDF
    $doc.Close([ref]$false)
    Write-Host "PDF created successfully at $pdfPath"
} catch {
    Write-Error "Conversion failed: $_"
} finally {
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
}
