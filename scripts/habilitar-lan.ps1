[CmdletBinding()]
param([string]$DireccionLAN)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
. (Join-Path $PSScriptRoot 'lan.ps1')
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not (New-Object Security.Principal.WindowsPrincipal $identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Ejecuta habilitar-lan.bat con clic derecho, Ejecutar como administrador.'
    }
    $address = Get-LedgerLanAddress -Address $DireccionLAN
    $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Primero ejecuta iniciar.bat para preparar el entorno local.' }
    # Windows virtualenv uses the base interpreter as its actual process image.
    $runtimeExecutable = & $python -c 'import sys; print(sys._base_executable)'
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $runtimeExecutable -PathType Leaf)) {
        throw 'No se pudo identificar el ejecutable Python del servidor.'
    }
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $digest = $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($python.ToLowerInvariant())) }
    finally { $hasher.Dispose() }
    $suffix = ([BitConverter]::ToString($digest)).Replace('-', '').Substring(0, 12)
    $ruleName = "BusinessLedger-LAN-$suffix"
    Write-Host "Se habilitara TCP 8443 solo en red Privada, direccion $address y subred local."
    $existing = Get-NetFirewallRule -Name $ruleName -PolicyStore PersistentStore -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.Group -ne 'Business Ledger') { throw 'Ya existe una regla ajena con ese nombre; no se modifica.' }
        Remove-NetFirewallRule -Name $ruleName -PolicyStore PersistentStore | Out-Null
    }
    New-NetFirewallRule -Name $ruleName -DisplayName 'Business Ledger - LAN privada' -Group 'Business Ledger' -PolicyStore PersistentStore -Direction Inbound -Action Allow -Enabled True -Protocol TCP -LocalPort 8443 -LocalAddress $address -RemoteAddress LocalSubnet -Profile Private -Program $runtimeExecutable -EdgeTraversalPolicy Block | Out-Null
    Write-Host "Regla habilitada. Inicia iniciar-lan.bat y abri http://${address}:8443."
    Write-Host "Para quitar esta regla: Remove-NetFirewallRule -Name '$ruleName'"
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
