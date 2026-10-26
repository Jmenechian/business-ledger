"""Explicit private-interface transport; plaintext requires deliberate opt-in."""

import ipaddress
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

PRIVATE_NETWORKS = tuple(
    map(ipaddress.ip_network, ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))
)


def private_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
        return ip.is_loopback or any(ip in network for network in PRIVATE_NETWORKS)
    except ValueError:
        return False


def origin_host(origin: str, allow_http: bool = False) -> str:
    try:
        url = urlsplit(origin)
        if (
            url.scheme not in ({"https", "http"} if allow_http else {"https"})
            or not url.hostname
            or not url.port
            or url.username is not None
            or origin != url.scheme + "://" + url.netloc
            or not origin.isascii()
        ):
            raise ValueError()
        if (
            url.scheme == "http"
            and url.hostname != "localhost"
            and not private_address(url.hostname)
        ):
            raise ValueError()
        return url.netloc
    except ValueError:
        raise ValueError(
            "indique un origen HTTPS exacto con puerto, sin ruta ni credenciales; "
            "HTTP privado requiere habilitación explícita"
        ) from None


def dns_matches(pattern: str, hostname: str) -> bool:
    pattern, hostname = pattern.lower(), hostname.lower()
    if "*" not in pattern:
        return pattern == hostname
    return (
        pattern.startswith("*.")
        and pattern.count("*") == 1
        and pattern.count(".") == hostname.count(".")
        and hostname.endswith(pattern[1:])
    )


@dataclass(frozen=True)
class Transport:
    bind: str
    port: int
    origin: str
    certificate: Path | None = None
    key: Path | None = None
    allow_http: bool = False

    def ssl_context(self) -> ssl.SSLContext | None:
        if not private_address(self.bind):
            raise ValueError("la dirección debe ser una IP privada o loopback explícita")
        origin_host(self.origin, allow_http=self.allow_http)
        url = urlsplit(self.origin)
        if not 1 <= self.port <= 65535 or url.port != self.port:
            raise ValueError("el puerto del origen debe coincidir con el del servidor")
        if url.scheme == "http":
            if self.certificate is not None or self.key is not None:
                raise ValueError("HTTP no admite archivos TLS; elija una sola configuración")
            return None
        if self.certificate is None or self.key is None:
            raise ValueError("HTTPS requiere certificado y clave TLS")
        try:
            certificate = x509.load_pem_x509_certificate(self.certificate.read_bytes())
            now = datetime.now(timezone.utc)
            if not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc:
                raise ValueError()
            names = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value
            try:
                hostname_ip = ipaddress.ip_address(url.hostname)
                matches = hostname_ip in names.get_values_for_type(x509.IPAddress)
            except ValueError:
                matches = any(
                    dns_matches(name, url.hostname)
                    for name in names.get_values_for_type(x509.DNSName)
                )
            if not matches:
                raise ValueError()
            try:
                usage = certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
                if ExtendedKeyUsageOID.SERVER_AUTH not in usage:
                    raise ValueError()
            except x509.ExtensionNotFound:
                pass
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.certificate, self.key, password=lambda: "")
            return context
        except (OSError, ValueError, ssl.SSLError, x509.ExtensionNotFound):
            raise ValueError(
                "certificado o clave TLS inválidos; verifique vigencia y SAN del origen"
            ) from None
