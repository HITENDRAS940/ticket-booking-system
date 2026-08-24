from pathlib import Path

import qrcode

QR_DIR = Path(__file__).resolve().parents[1] / "static" / "qrcodes"


def generate_booking_qr(reference: str) -> str:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{reference}.png"
    qrcode.make(reference).save(QR_DIR / filename)
    return f"/static/qrcodes/{filename}"

