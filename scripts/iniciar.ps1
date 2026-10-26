[CmdletBinding()]
param([switch]$Lan, [string]$DireccionLAN)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
. (Join-Path $PSScriptRoot 'lan.ps1')
try {
    if (Get-NetTCPConnection -LocalPort 8443 -State Listen -ErrorAction SilentlyContinue) {
        throw 'El puerto 8443 esta ocupado. Detene la instancia anterior antes de continuar.'
    }
    $bindAddress = '127.0.0.1'
    $origin = 'https://localhost:8443'
    if ($Lan) {
        $bindAddress = Get-LedgerLanAddress -Address $DireccionLAN
        $origin = "http://${bindAddress}:8443"
    } elseif ($DireccionLAN) { throw 'DireccionLAN requiere el modo -Lan.' }
    $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Se requiere Python 3.11 o posterior.' }
    }
    & $python -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python.' }
    Push-Location frontend
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias web. Se requiere Node 22.12+.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar la interfaz.' }
    } finally { Pop-Location }

    $runtime = Join-Path (Get-Location) 'private\local-test'
    $privateRoot = Split-Path $runtime -Parent
    foreach ($directory in @($privateRoot, $runtime)) {
        if ((Test-Path -LiteralPath $directory) -and ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'El directorio privado no puede ser un enlace o junction.'
        }
    }
    if (-not (Test-Path -LiteralPath $runtime)) {
        New-Item -ItemType Directory -Path $runtime | Out-Null
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $runtime /inheritance:r /grant:r "${identity}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F'
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron restringir los permisos del directorio privado.' }
    if (-not $Lan) {
        & $python -m backend.local_tls --directory $runtime
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar HTTPS local.' }
        $certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $runtime 'localhost.cer')
        $trusted = Test-Path "Cert:\CurrentUser\Root\$($certificate.Thumbprint)"
        if (-not $trusted) {
            Write-Host 'HTTPS local requiere confiar en este certificado, solo para tu usuario de Windows.'
            Write-Host "Huella: $($certificate.Thumbprint)"
            $answer = Read-Host 'Instalar este certificado local en CurrentUser\Root? [S/N]'
            if ($answer -notmatch '^[sS]$') { throw 'Instalacion cancelada. No se modifico el almacen de confianza.' }
            Import-Certificate -FilePath (Join-Path $runtime 'localhost.cer') -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
        }
    }
    $passwordFile = Join-Path $runtime 'password.json'
    if (-not (Test-Path -LiteralPath $passwordFile)) {
        & $python -m backend.password --out $passwordFile
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar la contrasena.' }
    }
    $database = Join-Path $runtime 'ledger.db'
    if (-not (Test-Path -LiteralPath $database)) {
        Write-Host 'Se iniciara una cuenta vacia de prueba. La base anterior no se importa automaticamente.'
    }
    Write-Host "Acceso: $origin"
    if ($Lan) {
        Write-Host 'Modo HTTP de red local: la conexion no esta cifrada.'
        Write-Host 'Abri esa misma direccion en las PCs y celulares de la misma red.'
        Write-Host 'Si no conecta, habilita la regla local con habilitar-lan.bat como administrador.'
    }
    if (Get-NetTCPConnection -LocalPort 8443 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Otra instancia inicio durante la preparacion. Detenela antes de continuar.'
    }
    # Open only after the exact selected HTTP/HTTPS endpoint is healthy.
    $opener = Start-Job -ArgumentList $origin -ScriptBlock {
        param($localOrigin)
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try {
                $health = Invoke-RestMethod "$localOrigin/api/health" -TimeoutSec 1
                if ($health.estado -eq 'ok') { Start-Process $localOrigin; return }
            } catch { }
            Start-Sleep -Seconds 1
        }
    }
    try {
        Write-Host "Business Ledger: $origin. Ctrl+C para detener."
        $serverArguments = @('-m', 'backend.server', '--db', $database, '--bind', $bindAddress, '--port', '8443', '--origin', $origin, '--password-file', $passwordFile)
        if ($Lan) { $serverArguments += '--allow-http' }
        else { $serverArguments += @('--tls-cert', (Join-Path $runtime 'localhost.pem'), '--tls-key', (Join-Path $runtime 'localhost.key')) }
        & $python @serverArguments
        if ($LASTEXITCODE -ne 0) { throw 'El servidor no pudo iniciarse.' }
    } finally { Stop-Job $opener; Remove-Job $opener }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
