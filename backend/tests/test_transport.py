import http.client
import ipaddress
import json
import socket
import ssl
import struct
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from backend.main import create_app
from backend.services.transport import Transport


@pytest.fixture
def tls_files(tmp_path):
    def create(expired=False):
        key = ec.generate_private_key(ec.SECP256R1())
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic test CA")])
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic TLS test")])
        now = datetime.now(timezone.utc)
        authority = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2))
            .not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
            )
            .sign(ca_key, hashes.SHA256())
        )
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(ca_name)
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
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(True, False, False, False, False, False, False, False, False),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        cert_path = tmp_path / ("expired.pem" if expired else "synthetic.pem")
        key_path = tmp_path / ("expired.key" if expired else "synthetic.key")
        cert_path.write_bytes(
            certificate.public_bytes(serialization.Encoding.PEM)
            + authority.public_bytes(serialization.Encoding.PEM)
        )
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


def test_real_https_login_write_and_logout(
    tls_files, tmp_path, credential, synthetic_password, caplog
):
    certificate, key = tls_files()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    origin = f"https://localhost:{port}"
    context = Transport("127.0.0.1", port, origin, certificate, key).ssl_context()
    app = create_app(tmp_path / "synthetic-tls.db", origin=origin, credential=credential)
    config = uvicorn.Config(
        app,
        loop="backend.services.event_loop:create_server_loop",
        ssl_context_factory=lambda config, factory: context,
        proxy_headers=False,
        access_log=False,
        log_level="critical",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    connection = None
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        trusted = ssl.create_default_context(cafile=str(certificate))
        # Browsers and readiness checks can close/reset connections abruptly.
        # Exercise both incomplete TLS and a reset after a successful handshake.
        for handshake in (False, True):
            for _ in range(3):
                raw = socket.create_connection(("127.0.0.1", port), timeout=5)
                interrupted = (
                    trusted.wrap_socket(raw, server_hostname="localhost") if handshake else raw
                )
                linger = struct.pack("HH" if sys.platform == "win32" else "ii", 1, 0)
                interrupted.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
                interrupted.close()
        connection = http.client.HTTPSConnection("127.0.0.1", port, context=trusted, timeout=5)

        def request(method, path, payload=None, cookie=""):
            headers = {"Host": f"localhost:{port}", "Origin": origin}
            if cookie:
                headers["Cookie"] = cookie
            if payload is not None:
                headers["Content-Type"] = "application/json"
            connection.request(
                method,
                path,
                body=json.dumps(payload) if payload is not None else None,
                headers=headers,
            )
            response = connection.getresponse()
            response.read()
            return response

        assert request("GET", "/api/health").status == 200
        assert request("GET", "/api/clients").status == 401
        logged_in = request("POST", "/api/auth/login", {"password": synthetic_password})
        assert logged_in.status == 200
        cookie = logged_in.getheader("Set-Cookie").split(";", 1)[0]
        assert (
            request("POST", "/api/clients", {"nombre": "Cuenta sintética TLS"}, cookie).status
            == 201
        )
        assert request("POST", "/api/auth/logout", cookie=cookie).status == 204
        assert request("GET", "/api/clients", cookie=cookie).status == 401
    finally:
        if connection:
            connection.close()
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
    assert not thread.is_alive()
    assert "Exception in callback" not in caplog.text
