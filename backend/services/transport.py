"""Explicit private-interface TLS configuration, with no proxy trust."""

import ipaddress
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID


def origin_host(origin: str) -> str:
    try:
        url = urlsplit(origin)
        if (
            url.scheme != "https"
            or not url.hostname
            or not url.port
            or url.username is not None
            or origin != "https://" + url.netloc
            or not origin.isascii()
        ):
            raise ValueError()
        return url.netloc
    except ValueError:
        raise ValueError(
            "indique un origen HTTPS exacto con puerto, sin ruta ni credenciales"
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
    certificate: Path
    key: Path

    def ssl_context(self) -> ssl.SSLContext:
        allowed_networks = map(
            ipaddress.ip_network, ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
        )
        try:
            ip = ipaddress.ip_address(self.bind)
            if not (ip.is_loopback or any(ip in network for network in allowed_networks)):
                raise ValueError()
        except ValueError:
            raise ValueError("la dirección debe ser una IP privada o loopback explícita") from None
        origin_host(self.origin)
        url = urlsplit(self.origin)
        if not 1 <= self.port <= 65535 or url.port != self.port:
            raise ValueError("el puerto del origen debe coincidir con el del servidor")
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
