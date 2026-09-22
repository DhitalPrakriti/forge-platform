from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError

from forge.api.registry import Limit, Offset, Scope, require_development_registry
from forge.api.tools import Session
from forge.core.errors import DomainError
from forge.knowledge.schemas import DocumentRead, DocumentUpload, SearchOutput, SearchPreview
from forge.knowledge.service import KnowledgeService

router = APIRouter(tags=["knowledge"], dependencies=[Depends(require_development_registry)])


@router.post("/knowledge/documents", response_model=DocumentRead, status_code=201)
async def upload_document(request: Request, scope: Scope, session: Session):
    # Bound the JSON body before decoding base64 or invoking the PDF subprocess.
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 4_010_000:
            raise DomainError("DOCUMENT_TOO_LARGE", "Upload must be at most 3 MB.", 413)
    try:
        payload = DocumentUpload.model_validate_json(body)
    except ValidationError as exc:
        raise DomainError(
            "DOCUMENT_INVALID", "Supply title, filename and base64 file content.", 422
        ) from exc
    return await KnowledgeService(session).upload(scope, payload)


@router.get("/knowledge/documents", response_model=list[DocumentRead])
async def documents(scope: Scope, session: Session, limit: Limit = 100, offset: Offset = 0):
    return await KnowledgeService(session).documents(scope, limit, offset)


@router.get("/knowledge/documents/{document_id}", response_model=DocumentRead)
async def document(document_id: UUID, scope: Scope, session: Session):
    return (await KnowledgeService(session).resolve(scope, [document_id]))[0]


@router.post("/knowledge/search", response_model=SearchOutput)
async def search(payload: SearchPreview, scope: Scope, session: Session):
    return await KnowledgeService(session).search(scope, payload.document_ids, payload.query)
