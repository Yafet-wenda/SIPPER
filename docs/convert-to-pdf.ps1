$docxPath = Join-Path $PSScriptRoot "laporan-implementasi-ocr.docx"
$pdfPath  = Join-Path $PSScriptRoot "laporan-implementasi-ocr.pdf"

$word = New-Object -ComObject Word.Application
$word.Visible = $false

try {
    $doc = $word.Documents.Open($docxPath)
    $doc.SaveAs([ref]$pdfPath, [ref]17) # 17 = wdFormatPDF
    $doc.Close()
    Write-Host "PDF created successfully at $pdfPath"
} catch {
    Write-Error "Conversion failed: $_"
} finally {
    $word.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
}
