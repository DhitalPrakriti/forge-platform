import asyncio
import base64
import binascii
import hashlib
import json
import sys
from pathlib import PurePosixPath

from forge.core.errors import DomainError
from forge.knowledge.schemas import DocumentUpload


def invalid(message):
    return DomainError("DOCUMENT_INVALID", message, 422)


async def extract(payload: DocumentUpload):
    filename = payload.filename
    if PurePosixPath(filename).name != filename or "\\" in filename:
        raise invalid("Use a filename without a path.")
    kind = filename.rsplit(".", 1)[-1].lower()
    if kind not in {"pdf", "txt", "md"}:
        raise invalid("Upload a PDF, UTF-8 text (.txt), or Markdown (.md) file.")
    try:
        raw = base64.b64decode(payload.content_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise invalid("Invalid file encoding.") from exc
    if not raw or len(raw) > 3_000_000:
        raise invalid("Files must contain between 1 byte and 3 MB.")
    if kind == "pdf":
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "forge.knowledge.pdf_extract",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(15):
                output, _ = await process.communicate(raw)
            if process.returncode != 0:
                raise invalid(
                    "PDF extraction failed. Use an unencrypted text PDF, at most 50 pages."
                )
            pages = json.loads(output)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
    else:
        try:
            pages = [raw.decode("utf-8-sig").replace("\x00", "").strip()]
        except UnicodeDecodeError as exc:
            raise invalid("Text and Markdown must use UTF-8 encoding.") from exc
    count = sum(len(page) for page in pages)
    if not 1 <= count <= 200_000:
        raise invalid("Provide 1–200,000 extracted characters. Scanned PDFs need OCR first.")
    chunks = []
    for number, page in enumerate(pages, 1):
        # Overlap preserves context across boundaries; source page/chunk remains explicit.
        for offset in range(0, len(page), 1000):
            text = page[offset : offset + 1200].strip()
            if text:
                chunks.append(
                    {
                        "position": len(chunks) + 1,
                        "page": number if kind == "pdf" else None,
                        "text": text,
                    }
                )
    return kind, hashlib.sha256(raw).hexdigest(), count, len(pages), chunks
