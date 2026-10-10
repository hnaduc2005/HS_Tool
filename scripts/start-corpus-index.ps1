Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$directory = Join-Path $projectRoot '.logs/legal-normalization'
$approvalPath = Join-Path $directory 'embedding-approval.json'
if (-not (Test-Path -LiteralPath $approvalPath)) { return }
$approval = Get-Content -LiteralPath $approvalPath -Raw | ConvertFrom-Json
if ($approval.resume_daily -ne $true -or @($approval.document_ids).Count -eq 0) { return }
$progressPath = Join-Path $directory 'embedding-progress.json'
if (Test-Path -LiteralPath $progressPath) {
    $progress = Get-Content -LiteralPath $progressPath -Raw | ConvertFrom-Json
    if ($progress.PSObject.Properties.Name -contains 'status' -and $progress.status -eq 'complete') { return }
}
$scriptPath = Join-Path $projectRoot 'scripts/normalize_legal_corpus.py'
$pidPath = Join-Path $directory 'embedding-worker.pid'
if (Test-Path -LiteralPath $pidPath) {
    $workerId = [int](Get-Content -LiteralPath $pidPath -Raw)
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $workerId" -ErrorAction SilentlyContinue
    if ($existing -and $existing.CommandLine -and $existing.CommandLine.Contains($scriptPath)) {
        Write-Host "Corpus index already running in background (PID $workerId)."
        return
    }
}
$arguments = @($scriptPath, '--embed-only', '--resume-daily')
foreach ($documentId in $approval.document_ids) {
    $validatedId = [guid]::Empty
    if (-not [guid]::TryParse([string]$documentId, [ref]$validatedId)) { throw 'Invalid approved document ID.' }
    $arguments += @('--document-id', $validatedId.ToString())
}
$worker = Start-Process -FilePath (Get-Command python -ErrorAction Stop).Source -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $directory 'embedding-worker.out.log') -RedirectStandardError (Join-Path $directory 'embedding-worker.err.log')
Set-Content -LiteralPath $pidPath -Value $worker.Id -Encoding ASCII
Write-Host "Corpus index continues in background (PID $($worker.Id)); daily quota waits and progress are saved."
