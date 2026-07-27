import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from innovation_governance_hub.config import Settings, get_settings
from innovation_governance_hub.exceptions import ValidationError
from innovation_governance_hub.persistence.models import Initiative, InitiativeDocument

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"}
MAX_SIZE_BYTES = 10 * 1024 * 1024


class DocumentService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def save(
        self,
        initiative_id: int,
        original_filename: str,
        content: bytes,
        document_type: str,
        description: str,
        actor: str,
    ) -> InitiativeDocument:
        if not self.session.get(Initiative, initiative_id):
            raise ValidationError("Iniciativa não encontrada.")
        safe_original = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(original_filename).name).strip()
        suffix = Path(safe_original).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValidationError("Extensão de documento não permitida.")
        if not content or len(content) > MAX_SIZE_BYTES:
            raise ValidationError("O documento deve possuir entre 1 byte e 10 MB.")
        upload_dir = self.settings.upload_dir.resolve()
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored = f"{uuid4().hex}{suffix}"
        target = (upload_dir / stored).resolve()
        if upload_dir not in target.parents:
            raise ValidationError("Caminho de documento inválido.")
        target.write_bytes(content)
        workspace = Path.cwd().resolve()
        stored_path = (
            str(target.relative_to(workspace)) if workspace in target.parents else str(target)
        )
        document = InitiativeDocument(
            initiative_id=initiative_id,
            document_type=document_type.strip() or "Outros",
            original_filename=safe_original,
            stored_filename=stored,
            relative_path=stored_path,
            description=description.strip(),
            uploaded_by=actor,
        )
        self.session.add(document)
        self.session.flush()
        return document

    def delete(self, document_id: int) -> None:
        document = self.session.get(InitiativeDocument, document_id)
        if not document:
            raise ValidationError("Documento não encontrado.")
        upload_dir = self.settings.upload_dir.resolve()
        target = Path(document.relative_path).resolve()
        if upload_dir not in target.parents:
            raise ValidationError("O arquivo não pertence ao diretório de uploads.")
        if target.exists():
            target.unlink()
        self.session.delete(document)
