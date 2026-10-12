"""Workout-plan document upload and processing (pending -> processing -> completed | failed)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ValidationFailed
from app.models import Document, PlannedExercise, User, WorkoutPlan, WorkoutPlanDay
from app.services.plan_parser import PlanDraft, parse_plan_text
from app.services.storage import get_storage

log = logging.getLogger(__name__)


# Strict-mode schema for OpenAI Structured Outputs (every key required, nullable, no defaults).
class _LLMExercise(BaseModel):
    exercise_name: str
    sets: int | None
    target_reps: int | None
    rep_range: str | None
    target_weight: float | None
    duration_seconds: int | None


class _LLMDay(BaseModel):
    day_number: int
    name: str
    description: str | None
    exercises: list[_LLMExercise]


class _LLMPlan(BaseModel):
    name: str
    days: list[_LLMDay]

ALLOWED = {"pdf": "application/pdf", "txt": "text/plain"}
MIN_TEXT_CHARS = 15


def extract_pdf_text(data: bytes) -> str:
    import fitz  # PyMuPDF

    parts: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[-100:]
    return base or "upload"


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def validate(self, file_name: str, data: bytes) -> str:
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext not in ALLOWED:
            raise ValidationFailed("Only PDF and TXT workout plans are supported.")
        max_bytes = get_settings().max_upload_mb * 1024 * 1024
        if not data:
            raise ValidationFailed("The file is empty.")
        if len(data) > max_bytes:
            raise ValidationFailed(f"File is larger than {get_settings().max_upload_mb} MB.")
        if ext == "pdf" and not data.startswith(b"%PDF"):
            raise ValidationFailed("This file is not a valid PDF.")
        if ext == "txt" and b"\x00" in data[:2048] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
            raise ValidationFailed("This file does not look like plain text.")
        return ext

    def create(self, user: User, file_name: str, data: bytes) -> Document:
        ext = self.validate(file_name, data)
        doc_id = uuid.uuid4()
        path = f"{user.id}/{doc_id}/{_safe_name(file_name)}"
        get_storage().save(path, data, ALLOWED[ext])
        doc = Document(id=doc_id, user_id=user.id, file_name=file_name[:255], file_type=ext, storage_path=path,
                       processing_status="pending")
        self.db.add(doc)
        self.db.flush()
        return doc

    # ------------------------------------------------------------------ processing
    def process(self, doc_id: uuid.UUID) -> None:
        """Run in a background task with its own session. Never raises."""
        doc = self.db.get(Document, doc_id)
        if doc is None:
            return
        doc.processing_status = "processing"
        self.db.commit()
        try:
            data = get_storage().load(doc.storage_path)
            text = extract_pdf_text(data) if doc.file_type == "pdf" else decode_text(data)
            text = text.replace("\x00", "")
            doc.extracted_text = text[:200_000]
            if len(text.strip()) < MIN_TEXT_CHARS:
                raise ValueError("No readable text found. Scanned PDFs need OCR — try a text PDF or a .txt file.")
            default_name = re.sub(r"\.(pdf|txt)$", "", doc.file_name, flags=re.I) or "My Workout Plan"
            draft = parse_plan_text(text, default_name=default_name)
            if draft.exercise_count == 0 and get_settings().ai_enabled:
                draft = self._llm_parse(text, default_name) or draft
            if draft.exercise_count == 0:
                raise ValueError("Couldn't find any exercises (expected lines like 'Bench Press 4x8').")
            self._save_plan(doc, draft)
            doc.processing_status = "completed"
            doc.error_message = None
        except Exception as exc:
            self.db.rollback()
            doc = self.db.get(Document, doc_id)
            if doc is None:
                return
            log.warning("Document %s failed: %s", doc_id, exc)
            doc.processing_status = "failed"
            doc.error_message = str(exc)[:500] if isinstance(exc, ValueError) else "Processing failed."
        doc.processed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _save_plan(self, doc: Document, draft: PlanDraft) -> WorkoutPlan:
        # The newly imported plan becomes the active one.
        self.db.execute(update(WorkoutPlan).where(WorkoutPlan.user_id == doc.user_id).values(is_active=False))
        plan = WorkoutPlan(user_id=doc.user_id, name=draft.name[:160], source_document_id=doc.id, is_active=True)
        for d in draft.days:
            day = WorkoutPlanDay(day_number=d.day_number, name=d.name, description=d.description)
            day.exercises = [
                PlannedExercise(exercise_name=e.exercise_name, sets=e.sets, target_reps=e.target_reps, rep_range=e.rep_range,
                                target_weight=e.target_weight, duration_seconds=e.duration_seconds, order_index=i)
                for i, e in enumerate(d.exercises)
            ]
            plan.days.append(day)
        self.db.add(plan)
        self.db.flush()
        return plan

    def _llm_parse(self, text: str, default_name: str) -> PlanDraft | None:
        """Fallback for unusual layouts: LLM extracts structure only; still validated by Pydantic."""
        try:
            from openai import OpenAI

            s = get_settings()
            client = OpenAI(api_key=s.openai_api_key, timeout=60)
            completion = client.chat.completions.parse(
                model=s.openai_model,
                temperature=0,
                response_format=_LLMPlan,
                messages=[
                    {"role": "system", "content": "Extract the workout plan into the schema. Only include exercises "
                     "present in the text; use null for anything not stated. Do not invent sets, reps or weights."},
                    {"role": "user", "content": text[:30_000]},
                ],
            )
            draft = completion.choices[0].message.parsed
            if draft is None:
                return None
            draft = PlanDraft.model_validate(draft.model_dump())
            if draft.name == "My Workout Plan":
                draft.name = default_name
            return draft
        except Exception as exc:
            log.warning("LLM plan parse failed: %s", type(exc).__name__)
            return None


def process_document_task(doc_id: uuid.UUID) -> None:
    from app.db.session import session_factory

    db = session_factory()()
    try:
        DocumentService(db).process(doc_id)
    finally:
        db.close()
