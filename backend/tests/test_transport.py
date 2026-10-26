import ipaddress
import ssl
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from backend.services.transport import Transport


@pytest.fixture
def tls_files(tmp_path):
    def create(expired=False):
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic TLS test")])
        now = datetime.now(timezone.utc)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(hours=-1 if expired else 1))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    ]
                ),
                critical=False,
            )
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256())
        )
        cert_path = tmp_path / ("expired.pem" if expired else "synthetic.pem")
        key_path = tmp_path / ("expired.key" if expired else "synthetic.key")
        cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        return cert_path, key_path

    return create


def test_tls_context_and_fail_closed_configuration(tls_files):
    certificate, key = tls_files()

    def context(bind="127.0.0.1", port=8443, origin="https://localhost:8443"):
        return Transport(bind, port, origin, certificate, key).ssl_context()

    assert context().minimum_version == ssl.TLSVersion.TLSv1_2
    for bind in ["192.168.50.10", "10.0.0.1", "172.16.1.2", "::1", "fd00::1"]:
        assert context(bind).minimum_version == ssl.TLSVersion.TLSv1_2
    for bind in ["0.0.0.0", "::", "8.8.8.8", "localhost", "192.0.2.1"]:
        with pytest.raises(ValueError):
            context(bind)
    for origin in [
        "",
        "http://localhost:8443",
        "https://localhost:8080",
        "https://other.invalid:8443",
        "https://localhost:8443/",
        "https://user@localhost:8443",
        "https://localhost:8443?x=1",
    ]:
        with pytest.raises(ValueError):
            context(origin=origin)
    expired, expired_key = tls_files(True)
    with pytest.raises(ValueError):
        Transport("127.0.0.1", 8443, "https://localhost:8443", expired, expired_key).ssl_context()
    with pytest.raises(ValueError):
        Transport(
            "127.0.0.1", 8443, "https://localhost:8443", certificate, expired_key
        ).ssl_context()


def test_https_boundary_rejects_plaintext_foreign_hosts_and_origins(client):
    assert client.get("http://localhost:8443/api/health").status_code == 426
    assert client.get("/api/health", headers={"Host": "evil.invalid"}).status_code == 403
    assert client.get("/api/health", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    for origin in ["", "null", "http://localhost:8443", "https://evil.invalid"]:
        response = client.post(
            "/api/clients", json={"nombre": "Sintético"}, headers={"Origin": origin}
        )
        assert response.status_code == 403
    response = client.get("/api/health", headers={"X-Forwarded-Proto": "http"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert (
        client.get(
            "http://localhost:8443/api/health", headers={"X-Forwarded-Proto": "https"}
        ).status_code
        == 426
    )
