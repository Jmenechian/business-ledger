function Test-LedgerPrivateIPv4 {
    param([string]$Address)
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref]$parsed)) { return $false }
    if ($parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or $parsed.ToString() -ne $Address) { return $false }
    $bytes = $parsed.GetAddressBytes()
    return ($bytes[0] -eq 10 -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168))
}

function Get-LedgerLanAddress {
    param([string]$Address)
    $adapters = @(Get-NetAdapter -ErrorAction Stop | Where-Object { $_.Status -eq 'Up' })
    $candidates = @(foreach ($adapter in $adapters) {
        Get-NetIPAddress -InterfaceIndex $adapter.InterfaceIndex -AddressFamily IPv4 -AddressState Preferred -ErrorAction Stop |
            Where-Object { Test-LedgerPrivateIPv4 $_.IPAddress }
    })
    $candidates = @($candidates | Sort-Object IPAddress -Unique)
    if ($candidates.Count -eq 0) {
        throw 'No se encontro una IPv4 privada activa (10.x, 172.16-31.x o 192.168.x). Revisa que la PC este conectada a la red local.'
    }
    if ($Address) {
        if (-not ($candidates | Where-Object { $_.IPAddress -eq $Address })) {
            throw 'La direccion elegida no pertenece a una interfaz activa de la red local.'
        }
        return $Address
    }
    if ($candidates.Count -eq 1) { return $candidates[0].IPAddress }
    Write-Host 'Elegi la direccion de la red compartida con las otras PCs y celulares:'
    for ($index = 0; $index -lt $candidates.Count; $index++) {
        Write-Host ("{0}. {1} ({2})" -f ($index + 1), $candidates[$index].IPAddress, $candidates[$index].InterfaceAlias)
    }
    $answer = Read-Host 'Numero de direccion'
    $selection = 0
    if (-not [int]::TryParse($answer, [ref]$selection) -or $selection -lt 1 -or $selection -gt $candidates.Count) {
        throw 'Seleccion de red no valida.'
    }
    return $candidates[$selection - 1].IPAddress
}
