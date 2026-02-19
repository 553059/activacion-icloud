"""
profile_generator.py

Generador dinámico de perfiles .mobileconfig para iOS (Wi‑Fi + DNS).
Uso legítimo: automatizar ajustes de red en dispositivos bajo control del usuario.

No debe usarse para evadir mecanismos de seguridad o para actividades ilegales.
"""
from __future__ import annotations
import plistlib
import uuid
import ipaddress
from typing import List, Optional


class MobileConfigBuilder:
    """Construye un .mobileconfig (plist XML) con payloads Wi‑Fi que incluyen DNS.

    Ejemplo:
        b = MobileConfigBuilder(display_name="DNS Bypass")
        xml = b.build_wifi_profile(ssid="MiRed", password="contraseña", dns=["1.1.1.1"])\
               .as_bytes()

    Luego enviar al iPhone con Content-Type: application/x-apple-aspen-config
    """

    def __init__(self, display_name: str = "Configuration Profile", identifier_base: str = "com.example.profile"):
        self.display_name = display_name
        self.identifier_base = identifier_base
        self.payloads = []

    @staticmethod
    def _validate_dns(dns: List[str]) -> List[str]:
        valid = []
        for d in dns:
            try:
                # acepta IPv4/IPv6
                ipaddress.ip_address(d)
                valid.append(d)
            except Exception:
                raise ValueError(f"DNS inválido: {d}")
        return valid

    def add_wifi_payload(self, ssid: str, password: Optional[str] = None, encryption: Optional[str] = "WPA", auto_join: bool = True, dns_servers: Optional[List[str]] = None, hidden: bool = False):
        """Añade payload tipo `com.apple.wifi.managed`.

        - ssid: nombre de la red
        - password: opcional; si se provee se añadirá Password y EncryptionType
        - dns_servers: lista de IPs DNS (se añaden dentro del payload Wi‑Fi)
        """
        if dns_servers:
            dns_servers = self._validate_dns(dns_servers)

        pid = f"{self.identifier_base}.wifi.{uuid.uuid4()}"
        payload = {
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": pid,
            "PayloadUUID": str(uuid.uuid4()).upper(),
            "PayloadDisplayName": f"Wi‑Fi — {ssid}",
            "SSID_STR": ssid,
            "AutoJoin": bool(auto_join),
            "HiddenNetwork": bool(hidden),
        }
        if password:
            payload["Password"] = password
            payload["EncryptionType"] = encryption
        if dns_servers:
            payload["DNSServerAddresses"] = dns_servers
        self.payloads.append(payload)
        return self

    def build(self) -> dict:
        root_uuid = str(uuid.uuid4()).upper()
        root_id = f"{self.identifier_base}.{root_uuid[:8].lower()}"
        doc = {
            "PayloadContent": self.payloads,
            "PayloadDisplayName": self.display_name,
            "PayloadIdentifier": root_id,
            "PayloadRemovalDisallowed": False,
            "PayloadType": "Configuration",
            "PayloadUUID": root_uuid,
            "PayloadVersion": 1,
        }
        return doc

    def as_bytes(self) -> bytes:
        doc = self.build()
        return plistlib.dumps(doc)

    def save(self, path: str) -> None:
        data = self.as_bytes()
        with open(path, "wb") as f:
            f.write(data)


# --- Signing helpers (opcional, requiere OpenSSL en PATH) ---
import subprocess
import tempfile

def sign_profile_with_openssl(profile_bytes: bytes, certfile: str, keyfile: str) -> bytes:
    """Firma un .mobileconfig usando OpenSSL CMS/SMIME y devuelve bytes firmados (DER).

    Requisitos: `openssl` disponible en PATH y certificados PEM válidos.
    """
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, 'profile.mobileconfig')
        out_path = os.path.join(td, 'profile.signed')
        with open(in_path, 'wb') as fh:
            fh.write(profile_bytes)
        cmd = [
            'openssl', 'cms', '-sign', '-in', in_path,
            '-signer', certfile, '-inkey', keyfile,
            '-outform', 'DER', '-nodetach', '-binary', '-out', out_path
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"OpenSSL failed: {proc.stderr.decode(errors='ignore')}")
        with open(out_path, 'rb') as fh:
            return fh.read()


def verify_signed_profile_with_openssl(signed_bytes: bytes, ca_certfile: str) -> bool:
    """Verifica firma CMS de un mobileconfig (requiere OpenSSL). Devuelve True si válida."""
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, 'signed.mobileconfig')
        out_path = os.path.join(td, 'verified.plist')
        with open(in_path, 'wb') as fh:
            fh.write(signed_bytes)
        cmd = [
            'openssl', 'cms', '-verify', '-in', in_path, '-inform', 'DER',
            '-CAfile', ca_certfile, '-out', out_path
        ]
        proc = subprocess.run(cmd, capture_output=True)
        return proc.returncode == 0


# Demo / sanity check cuando se ejecuta como script
if __name__ == "__main__":
    b = MobileConfigBuilder(display_name="DNS Bypass Profile", identifier_base="com.jarvis.dnsbypass")
    b.add_wifi_payload(ssid="TuRedWiFi", password=None, encryption=None, dns_servers=["1.1.1.1", "8.8.8.8"]) 
    b.save("dns-bypass.mobileconfig")
    print("Perfil generado: dns-bypass.mobileconfig")
