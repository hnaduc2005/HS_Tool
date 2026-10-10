param([int]$StartupTimeoutSeconds = 90)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $projectRoot '.logs'
$envPath = Join-Path $projectRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) { throw 'Missing .env in the project root.' }
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

function Read-Setting([string]$Name, [string]$Default = '') {
    $line = Get-Content -LiteralPath $envPath | Where-Object { $_ -match ('^\s*' + [regex]::Escape($Name) + '\s*=') } | Select-Object -First 1
    if ($null -eq $line) { return $Default }
    return ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
}

$nodeExe = (Get-Command node -ErrorAction Stop).Source
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$childCheck = "const r=require('child_process').spawnSync(process.execPath,['-v']); if(r.error || r.status !== 0) { console.error('Node cannot create child processes in this execution environment.'); process.exit(1); }"
& $nodeExe -e $childCheck
if ($LASTEXITCODE -ne 0) { throw 'Run the program in a Windows terminal that permits child processes and outbound HTTPS.' }

function Start-ServiceProcess([string]$Name, [int]$Port, [string]$Executable, [string[]]$Arguments, [string]$Directory) {
    $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        Write-Host "$Name already listening on port $Port; checking readiness."
        return $null
    }
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logRoot "service-$Name.out.log") -RedirectStandardError (Join-Path $logRoot "service-$Name.err.log")
    Write-Host "Started $Name (PID $($process.Id))."
    return $process
}

function Wait-Http([string]$Url, [System.Diagnostics.Process]$Process) {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        if ($null -ne $Process -and $Process.HasExited) { throw "Service exited before responding at $Url. Check $logRoot." }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw "Service did not become ready at $Url. Check $logRoot."
}

$token = Read-Setting 'AI_SERVICE_TOKEN'
if (-not $token) { throw 'AI_SERVICE_TOKEN must be configured in .env.' }
$aiProcess = Start-ServiceProcess 'ai' 8000 $pythonExe @(('"' + (Join-Path $projectRoot 'ai-service/run.py') + '"')) (Join-Path $projectRoot 'ai-service')
Wait-Http 'http://127.0.0.1:8000/health' $aiProcess
try {
    $ready = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -Headers @{ 'x-service-token' = $token } -TimeoutSec 150
    if ($ready.status -ne 'ready') { throw 'Invalid readiness response.' }
} catch {
    throw "AI readiness failed: chat, embedding, database and legal corpus must be available from the running AI process. Check $logRoot."
}
if ($ready.embedding -eq 'ok') {
    Write-Host 'AI ready: chat, embedding, database and legal corpus checked.'
} else {
    Write-Host 'AI ready: chat, database and legal corpus checked; embedding temporarily unavailable, using normalized text and legal context retrieval.'
}

$backendPort = [int](Read-Setting 'PORT' '3001')
$backendEntry = Join-Path $projectRoot 'backend/node_modules/@nestjs/cli/bin/nest.js'
$frontendEntry = Join-Path $projectRoot 'frontend/node_modules/next/dist/bin/next'
if (-not (Test-Path -LiteralPath $backendEntry) -or -not (Test-Path -LiteralPath $frontendEntry)) { throw 'Missing Node dependencies. Run pnpm install first.' }
$backendProcess = Start-ServiceProcess 'backend' $backendPort $nodeExe @(('"' + $backendEntry + '"'), 'start', '--watch') (Join-Path $projectRoot 'backend')
$frontendProcess = Start-ServiceProcess 'frontend' 3000 $nodeExe @(('"' + $frontendEntry + '"'), 'dev', '--port', '3000') (Join-Path $projectRoot 'frontend')
Wait-Http "http://127.0.0.1:$backendPort/api/hs-codes/search?q=6109" $backendProcess
Wait-Http 'http://127.0.0.1:3000' $frontendProcess
Write-Host 'HS Atlas ready at http://localhost:3000'
try {
    & (Join-Path $PSScriptRoot 'start-corpus-index.ps1')
} catch {
    Write-Warning 'The application is ready, but the authorized corpus rebuild did not start. Check .logs/legal-normalization.'
}
