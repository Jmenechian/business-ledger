"""Windows network-selection checks with synthetic cmdlets; no machine changes."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows launcher helpers")
HELPER = Path(__file__).resolve().parents[2] / "scripts" / "lan.ps1"


def run_synthetic(tmp_path, commands):
    script = tmp_path / "synthetic-network.ps1"
    helper = str(HELPER).replace("'", "''")
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n. '" + helper + "'\n" + commands,
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lan_address_private_only_canonical_ipv4(tmp_path):
    run_synthetic(
        tmp_path,
        r"""
foreach ($address in @('10.0.0.1','172.16.0.1','172.31.255.254','192.168.50.10')) {
    if (-not (Test-LedgerPrivateIPv4 $address)) { throw 'Valid private address rejected' }
}
$unsafe = @('127.0.0.1','0.0.0.0','8.8.8.8','169.254.1.2','172.32.0.1','::1',
            'localhost','192.168.050.10','10.1')
foreach ($address in $unsafe) {
    if (Test-LedgerPrivateIPv4 $address) { throw 'Unsafe or ambiguous address accepted' }
}
""",
    )


def test_lan_selection_rejects_public_profiles_and_missing_requested_address(tmp_path):
    run_synthetic(
        tmp_path,
        r"""
function Get-NetConnectionProfile {
    [pscustomobject]@{InterfaceIndex=1;NetworkCategory='Private'}
    [pscustomobject]@{InterfaceIndex=2;NetworkCategory='Public'}
}
function Get-NetIPAddress {
    param($InterfaceIndex,$AddressFamily,$AddressState)
    if ($InterfaceIndex -ne 1) { throw 'Public interface must not be queried' }
    [pscustomobject]@{IPAddress='192.168.50.10';InterfaceAlias='Synthetic LAN'}
    [pscustomobject]@{IPAddress='169.254.1.2';InterfaceAlias='Synthetic link local'}
}
if ((Get-LedgerLanAddress) -ne '192.168.50.10') { throw 'Wrong automatic address' }
if ((Get-LedgerLanAddress -Address '192.168.50.10') -ne '192.168.50.10') {
    throw 'Requested address lost'
}
$rejected=$false
try { Get-LedgerLanAddress -Address '192.168.50.99' | Out-Null } catch { $rejected=$true }
if (-not $rejected) { throw 'Unassigned address accepted' }
function Get-NetConnectionProfile { [pscustomobject]@{InterfaceIndex=2;NetworkCategory='Public'} }
$rejected=$false
try { Get-LedgerLanAddress | Out-Null } catch { $rejected=$true }
if (-not $rejected) { throw 'Public-only network accepted' }
""",
    )


def test_multiple_lan_interfaces_require_explicit_selection(tmp_path):
    run_synthetic(
        tmp_path,
        r"""
function Get-NetConnectionProfile { [pscustomobject]@{InterfaceIndex=1;NetworkCategory='Private'} }
function Get-NetIPAddress {
    [pscustomobject]@{IPAddress='192.168.50.10';InterfaceAlias='Synthetic LAN A'}
    [pscustomobject]@{IPAddress='10.0.0.10';InterfaceAlias='Synthetic LAN B'}
}
function Read-Host { return '2' }
if ((Get-LedgerLanAddress) -ne '192.168.50.10') { throw 'Selection not applied' }
function Read-Host { return '99' }
$rejected=$false
try { Get-LedgerLanAddress | Out-Null } catch { $rejected=$true }
if (-not $rejected) { throw 'Invalid selection accepted' }
""",
    )
