"""Provision a loopback-only leaf certificate; never installs system trust."""

import argparse
import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def provision(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / name for name in ("localhost.pem", "localhost.key", "localhost.cer")]
    if all(path.exists() for path in paths):
        return
    if any(path.exists() for path in paths):
        raise ValueError("configuracion TLS incompleta; no se sobrescriben archivos existentes")
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Business Ledger localhost")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, hashes.SHA256())
    )
    values = [
        certificate.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        certificate.public_bytes(serialization.Encoding.DER),
    ]
    for path, value in zip(paths, values, strict=True):
        with path.open("xb") as stream:
            stream.write(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preparar certificado HTTPS solo para este PC")
    parser.add_argument("--directory", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        provision(arguments.directory)
    except (OSError, ValueError):
        parser.exit(1, "No se pudo preparar el certificado local; revise los archivos privados.\n")


if __name__ == "__main__":
    main()
