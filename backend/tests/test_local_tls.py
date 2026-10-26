import pytest
from cryptography import x509

from backend.local_tls import provision
from backend.services.transport import Transport


def test_local_certificate_matches_transport_and_is_not_ca(tmp_path):
    provision(tmp_path)
    certificate = (tmp_path / "localhost.pem").read_bytes()
    parsed = x509.load_pem_x509_certificate(certificate)
    assert not parsed.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    Transport(
        "127.0.0.1",
        8443,
        "https://localhost:8443",
        tmp_path / "localhost.pem",
        tmp_path / "localhost.key",
    ).ssl_context()
    provision(tmp_path)
    assert (tmp_path / "localhost.pem").read_bytes() == certificate
    (tmp_path / "localhost.cer").unlink()
    with pytest.raises(ValueError):
        provision(tmp_path)
