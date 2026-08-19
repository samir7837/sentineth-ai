from pathlib import Path

from pypdf import PdfReader


def extract_text_from_pdf(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    reader = PdfReader(str(path))

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text.strip())

    text = "\n\n".join(pages)

    if not text.strip():
        raise ValueError(
            "No extractable text found in PDF. "
            "The document may be scanned or image-based."
        )

    return text