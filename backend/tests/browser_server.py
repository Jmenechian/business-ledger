"""Isolated browser-test server. Always uses a newly generated temporary ledger."""

import argparse
import ipaddress
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from backend.controllers.client_controller import create_client
from backend.main import create_app
from backend.models.client import ClientCreate
from backend.services.passwords import create_credential


def main():
    parser = argparse.ArgumentParser(description="Servidor aislado con datos sintéticos")
    parser.add_argument("--http", action="store_true")
    use_http = parser.parse_args().http
    with TemporaryDirectory(prefix="ledger-synthetic-browser-") as folder:
        directory = Path(folder)
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic browser fixture")])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        cert_path, key_path = directory / "synthetic.pem", directory / "synthetic.key"
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert_path, key_path)
        origin = "http://127.0.0.1:4177" if use_http else "https://127.0.0.1:4176"
        app = create_app(
            directory / "synthetic.db",
            origin=origin,
            credential=create_credential("Contraseña sintética para navegador 42"),
            **({"allow_http": True} if use_http else {}),
        )
        app.state.database.initialize()
        create_client(app.state.database, ClientCreate(nombre="Cuenta sintética API"))
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=4177 if use_http else 4176,
            loop="backend.services.event_loop:create_server_loop",
            **({} if use_http else {"ssl_context_factory": lambda config, factory: context}),
            proxy_headers=False,
            access_log=False,
            log_level="warning",
        )
        uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
