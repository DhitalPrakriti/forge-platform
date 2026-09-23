"""Bounded subprocess entry point: PDF bytes on stdin, extracted pages as JSON on stdout."""

import io
import json
import resource
import sys


def main():
    # Limit damage from compressed/malformed files independently of the API process.
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    # macOS does not support lowering RLIMIT_AS reliably. Linux deployments also cap memory.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    from pypdf import PdfReader

    try:
        raw = sys.stdin.buffer.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("size")
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 50:
            raise ValueError("pages or encryption")
        pages = []
        count = 0
        for page in reader.pages:
            content = (page.extract_text() or "").replace("\x00", "").strip()
            count += len(content)
            if count > 200_000:
                raise ValueError("extracted size")
            pages.append(content)
        print(json.dumps(pages))
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
