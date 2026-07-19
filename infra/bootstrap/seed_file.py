"""`make seed-file`: gera um arquivo posicional de exemplo válido e envia pra `uploads/` (§6.9)."""

import os
import uuid
from datetime import UTC, datetime

from resources.aws_clients import build_client


def _record(record_type: str, *fields: tuple[str, int, str]) -> str:
    line = record_type
    for text, width, align in fields:
        line += text.rjust(width, "0") if align == "R0" else text.ljust(width)
    return line.ljust(200)


def build_sample_file() -> str:
    today = datetime.now(UTC).strftime("%Y%m%d")

    header = _record("0", (today, 8, "L"), ("SEED_FILE", 30, "L"), ("1", 6, "R0"))
    pedido = _record(
        "1",
        ("SOLICITAR", 10, "L"),
        ("", 36, "L"),
        ("CUST00001", 20, "L"),
        ("MARIA SILVA", 60, "L"),
        ("12345678901", 14, "R0"),
        ("1", 2, "R0"),
    )
    item = _record("2", ("1", 8, "R0"), ("2", 8, "R0"))
    trailer = _record("9", ("1", 8, "R0"), ("1", 8, "R0"))

    return "\n".join([header, pedido, item, trailer]) + "\n"


def main() -> None:
    bucket_name = os.environ.get("PEDIDOS_BUCKET_NAME", "pedidos-bucket")
    key = f"uploads/seed-{uuid.uuid4().hex[:8]}.txt"

    s3 = build_client("s3")
    s3.put_object(Bucket=bucket_name, Key=key, Body=build_sample_file().encode("utf-8"))

    print(f"seed-file: enviado s3://{bucket_name}/{key}")


if __name__ == "__main__":
    main()
