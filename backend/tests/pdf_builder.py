"""Minimal valid PDF generation for tests.

Building a real PDF (rather than monkeypatching text extraction) means
the tests exercise `extraction_service.extract_text_from_pdf` and pypdf
for real, which is where format bugs actually live.
"""


def build_pdf(lines: list[str]) -> bytes:
    """Return a single-page PDF containing `lines` as extractable text."""

    operators = [b"BT", b"/F1 12 Tf", b"72 720 Td", b"14 TL"]

    for line in lines:
        escaped = (
            line.replace("\\", r"\\")
            .replace("(", r"\(")
            .replace(")", r"\)")
        )
        operators.append(f"({escaped}) Tj".encode("latin-1"))
        operators.append(b"T*")

    operators.append(b"ET")

    content = b"\n".join(operators)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> "
            b"/Contents 4 0 R >>"
        ),
        (
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []

    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii")
        out += body
        out += b"\nendobj\n"

    xref_offset = len(out)
    size = len(objects) + 1

    out += f"xref\n0 {size}\n".encode("ascii")
    out += b"0000000000 65535 f \n"

    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")

    out += b"trailer\n"
    out += f"<< /Size {size} /Root 1 0 R >>\n".encode("ascii")
    out += f"startxref\n{xref_offset}\n".encode("ascii")
    out += b"%%EOF\n"

    return bytes(out)
