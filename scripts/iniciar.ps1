$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
try {
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
    if (-not (Test-Path -LiteralPath $runtime)) {
        New-Item -ItemType Directory -Path $runtime | Out-Null
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls.exe $runtime /inheritance:r /grant:r "${identity}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F'
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron restringir los permisos del directorio privado.' }
    }
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
    $passwordFile = Join-Path $runtime 'password.json'
    if (-not (Test-Path -LiteralPath $passwordFile)) {
        & $python -m backend.password --out $passwordFile
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar la contrasena.' }
    }
    $database = Join-Path $runtime 'ledger.db'
    if (-not (Test-Path -LiteralPath $database)) {
        Write-Host 'Se iniciara una cuenta vacia de prueba. La base anterior no se importa automaticamente.'
    }
    if (Get-NetTCPConnection -LocalPort 8443 -State Listen -ErrorAction SilentlyContinue) {
        throw 'El puerto 8443 esta ocupado. Cierre la instancia anterior antes de continuar.'
    }
    # A bounded job opens the browser only when this exact HTTPS endpoint is healthy.
    $opener = Start-Job -ScriptBlock {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try {
                $health = Invoke-RestMethod 'https://localhost:8443/api/health' -TimeoutSec 1
                if ($health.estado -eq 'ok') { Start-Process 'https://localhost:8443'; return }
            } catch { }
            Start-Sleep -Seconds 1
        }
    }
    try {
        Write-Host 'Business Ledger: https://localhost:8443. Ctrl+C para detener.'
        & $python -m backend.server --db $database --bind 127.0.0.1 --port 8443 --origin https://localhost:8443 --tls-cert (Join-Path $runtime 'localhost.pem') --tls-key (Join-Path $runtime 'localhost.key') --password-file $passwordFile
        if ($LASTEXITCODE -ne 0) { throw 'El servidor no pudo iniciarse.' }
    } finally { Stop-Job $opener; Remove-Job $opener }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
