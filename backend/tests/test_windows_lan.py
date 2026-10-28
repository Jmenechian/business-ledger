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


def test_lan_selection_uses_active_interface_without_profile_lookup(tmp_path):
    run_synthetic(
        tmp_path,
        r"""
function Get-NetAdapter {
    [pscustomobject]@{InterfaceIndex=1;Status='Up'}
    [pscustomobject]@{InterfaceIndex=2;Status='Down'}
}
function Get-NetIPAddress {
    param($InterfaceIndex,$AddressFamily,$AddressState)
    if ($InterfaceIndex -ne 1) { throw 'Public interface must not be queried' }
    [pscustomobject]@{IPAddress='192.168.50.10';InterfaceAlias='Synthetic LAN'}
}
if ((Get-LedgerLanAddress) -ne '192.168.50.10') { throw 'Wrong automatic address' }
if ((Get-LedgerLanAddress -Address '192.168.50.10') -ne '192.168.50.10') {
    throw 'Requested address lost'
}
$rejected=$false
try { Get-LedgerLanAddress -Address '192.168.50.99' | Out-Null } catch { $rejected=$true }
if (-not $rejected) { throw 'Unassigned address accepted' }
""",
    )


def test_multiple_lan_interfaces_require_explicit_selection(tmp_path):
    run_synthetic(
        tmp_path,
        r"""
function Get-NetAdapter { [pscustomobject]@{InterfaceIndex=1;Status='Up'} }
function Get-NetIPAddress {
    [pscustomobject]@{IPAddress='192.168.50.10';InterfaceAlias='Synthetic LAN A';InterfaceIndex=1}
    [pscustomobject]@{IPAddress='10.0.0.10';InterfaceAlias='Synthetic LAN B';InterfaceIndex=1}
}
function Get-NetRoute { @() }
function Read-Host { return '2' }
if ((Get-LedgerLanAddress) -ne '192.168.50.10') { throw 'Selection not applied' }
function Read-Host { return '99' }
$rejected=$false
try { Get-LedgerLanAddress | Out-Null } catch { $rejected=$true }
if (-not $rejected) { throw 'Invalid selection accepted' }
""",
    )


def test_lan_address_prefers_adapter_with_best_default_route(tmp_path):
    run_synthetic(
        tmp_path,
        r"""
function Get-NetAdapter {
    [pscustomobject]@{InterfaceIndex=1;Status='Up'}
    [pscustomobject]@{InterfaceIndex=2;Status='Up'}
}
function Get-NetIPAddress {
    param($InterfaceIndex,$AddressFamily,$AddressState)
    if ($InterfaceIndex -eq 1) {
        [pscustomobject]@{IPAddress='192.168.0.11';InterfaceAlias='Ethernet';InterfaceIndex=1}
    } else {
        [pscustomobject]@{IPAddress='192.168.56.1';InterfaceAlias='Ethernet 3';InterfaceIndex=2}
    }
}
function Get-NetRoute {
    param($DestinationPrefix)
    [pscustomobject]@{InterfaceIndex=1;RouteMetric=25}
}
function Get-NetIPInterface {
    param($InterfaceIndex,$AddressFamily)
    [pscustomobject]@{InterfaceMetric=10}
}
function Read-Host { throw 'A single best default route should be automatic' }
if ((Get-LedgerLanAddress) -ne '192.168.0.11') { throw 'Default-route adapter not selected' }
""",
    )
