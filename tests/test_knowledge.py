import asyncio
import base64
import io

import pytest
from pydantic import ValidationError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from forge.core.errors import DomainError
from forge.knowledge.extraction import extract
from forge.knowledge.schemas import DocumentUpload


def upload(content, filename="hours.txt"):
    return {
        "title": "Opening hours",
        "filename": filename,
        "content_base64": base64.b64encode(content).decode(),
    }


def pdf(encrypt=False, blank=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if not blank:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (Restaurant hours: Monday 9am to 5pm.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypt:
        writer.encrypt("secret")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize("filename", ["hours.txt", "hours.md", "hours.pdf"])
def test_extract_formats(filename):
    data = pdf() if filename.endswith("pdf") else b"Restaurant hours: Monday 9am to 5pm."
    result = asyncio.run(extract(DocumentUpload(**upload(data, filename))))
    assert "Monday" in result[-1][0]["text"]
    assert result[-1][0]["page"] == (1 if filename.endswith("pdf") else None)


@pytest.mark.parametrize(
    "data,filename",
    [
        (b"", "x.txt"),
        (b"\xff", "x.txt"),
        (b"hello", "../x.txt"),
        (b"hi", "x.html"),
        (b"not pdf", "x.pdf"),
        (pdf(encrypt=True), "x.pdf"),
        (pdf(blank=True), "x.pdf"),
        (b"a" * 200001, "x.txt"),
    ],
)
def test_invalid_documents(data, filename):
    with pytest.raises((DomainError, ValidationError)):
        asyncio.run(extract(DocumentUpload(**upload(data, filename))))
