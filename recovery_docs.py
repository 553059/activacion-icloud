"""
recovery_docs.py

Generador de "Recovery Kit" (plantilla exportable a Markdown / TXT / PDF opcional).

Incluye:
 - carta para contactar al propietario
 - guía para solicitar soporte a Apple (pruebas de compra)

Uso: generate_recovery_kit(device_info, owner_contact, output_path, format)
"""
from __future__ import annotations
from datetime import datetime
import os
from typing import Optional

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


def _contact_letter(device_info: dict, requester_name: str) -> str:
    return f"""{requester_name}

Asunto: Solicitud de desvinculación de dispositivo — {device_info.get('model') or 'dispositivo'} ({device_info.get('serial') or 'S/N'})

Estimado propietario,

Le escribo para solicitar su ayuda para desvincular/transferir el dispositivo indicado arriba. Adjunto copia de la factura y los datos necesarios para verificar la propiedad.

Atentamente,
{requester_name}
"""


def _apple_support_steps() -> str:
    return (
        "Pasos recomendados para solicitar soporte a Apple por Activation Lock:\n"
        "1) Reúne la factura original o comprobante de compra con fecha y número de serie.\n"
        "2) Accede a https://support.apple.com/es-es/HT201441 y sigue el flujo para 'Dispositivo bloqueado por activación'.\n"
        "3) Proporciona número de serie, IMEI (si aplica) y copia de la compra cuando te lo soliciten.\n"
        "4) Conserva el número de caso y el correo de confirmación.\n"
    )


def generate_recovery_kit(device_info: dict, requester_name: str, proof_of_purchase_path: Optional[str] = None, out_path: str = "recovery_kit.md", fmt: str = "md") -> str:
    """Genera el recovery kit y lo guarda en out_path.

    - device_info: dict con keys (model, serial, udid, imei, ios_version)
    - requester_name: nombre que aparecerá en la carta
    - proof_of_purchase_path: ruta opcional a la factura (solo referencia en el documento)
    - fmt: 'md' | 'txt' | 'pdf' (pdf requiere reportlab)

    Devuelve la ruta al archivo generado.
    """
    ts = datetime.utcnow().isoformat()[:19].replace("T", " ")
    header = f"# Recovery kit — {device_info.get('model','dispositivo')}\nGenerated: {ts} UTC\n\n"
    meta = (
        f"- Modelo: {device_info.get('model') or '—'}\n"
        f"- Serie: {device_info.get('serial') or '—'}\n"
        f"- UDID: {device_info.get('udid') or '—'}\n"
        f"- IMEI: {device_info.get('imei') or '—'}\n"
        f"- iOS: {device_info.get('ios_version') or '—'}\n\n"
    )
    sections = """
## Carta para el propietario

%s

## Guía para soporte Apple

%s

""" % (_contact_letter(device_info, requester_name), _apple_support_steps())

    if proof_of_purchase_path:
        sections += f"Adjunto: {proof_of_purchase_path}\n\n"

    content = header + meta + sections

    out_path = os.path.abspath(out_path)
    if fmt in ("md", "txt"):
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        return out_path

    if fmt == "pdf":
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError("reportlab no está disponible. Instala 'reportlab' para exportar PDF.")
        doc = SimpleDocTemplate(out_path)
        styles = getSampleStyleSheet()
        story = []
        for part in content.split('\n\n'):
            story.append(Paragraph(part.replace('\n', '<br/>'), styles['BodyText']))
            story.append(Spacer(1, 6))
        doc.build(story)
        return out_path

    raise ValueError("Formato no soportado: use 'md'|'txt'|'pdf'")


if __name__ == '__main__':
    demo = {
        'model': 'iPhone X',
        'serial': 'DX3AB12B0Q',
        'udid': '00008020-001C2D223E11002E',
        'imei': '012345678901234',
        'ios_version': '14.8'
    }
    p = generate_recovery_kit(demo, requester_name='Soporte Tec', out_path='recovery_kit.md', fmt='md')
    print('Recovery kit guardado en', p)
