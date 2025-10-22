# src/webhooks/mailgun.py
import tempfile
from typing import List, Tuple, Optional

from fastapi import APIRouter, Request, BackgroundTasks, UploadFile
from loguru import logger
from src.ai.router import route_instruction
from src.mail.sender import send_email

router = APIRouter()

@router.post("/inbound")
async def inbound(request: Request, background_tasks: BackgroundTasks):
    """
    Parse générique du multipart form-data envoyé par Mailgun (ou simulé via curl).
    Tolérant aux variations de clés (body-plain/body_plain, attachment-count, etc.)
    et robuste si attachment-count est absent/inexact.
    """
    form = await request.form()

    # DEBUG: affiche les clés vraiment reçues
    keys = list(form.keys())
    logger.info(f"FORM KEYS: {keys}")

    # Core fields (avec alias tolérants)
    sender = (form.get("sender") or form.get("from") or "unknown@example.com")
    subject = form.get("subject") or ""
    body_plain = (
        form.get("body-plain")
        or form.get("body_plain")
        or form.get("stripped-text")
        or ""
    )
    body_html = (
        form.get("body-html")
        or form.get("body_html")
        or form.get("stripped-html")
        or ""
    )

    # attachment-count peut manquer : on le dérive si besoin
    raw_count = form.get("attachment-count") or form.get("attachment_count") or "0"
    try:
        attachment_count = int(raw_count)
    except Exception:
        attachment_count = 0

    # Collecte des UploadFile : d'abord via attachment-count, sinon par scan des clés
    upload_files: List[UploadFile] = []

    # 1) Si attachment-count > 0, récupère attachment-1..N
    if attachment_count > 0:
        for i in range(1, attachment_count + 1):
            val = form.get(f"attachment-{i}")
            if isinstance(val, UploadFile):
                upload_files.append(val)

    # 2) Fallback : si rien trouvé, scanne toutes les clés 'attachment-*'
    if not upload_files:
        for k in keys:
            if k.startswith("attachment-"):
                val = form.get(k)
                if isinstance(val, UploadFile):
                    upload_files.append(val)

    # DEBUG: log des attachments détectés
    for idx, f in enumerate(upload_files, start=1):
        logger.info(
            f"ATT[{idx}] filename={getattr(f, 'filename', None)} "
            f"ctype={getattr(f, 'content_type', None)}"
        )

    logger.info(f"Inbound email from={sender} subject={subject} attachments_detected={len(upload_files)}")

    # Sauvegarde temporaire
    saved_paths: List[Tuple[str, Optional[str]]] = []
    for f in upload_files:
        # Détermine l'extension de sauvegarde
        ctype = (getattr(f, "content_type", "") or "").lower()
        if "pdf" in ctype:
            suffix = "pdf"
        else:
            fname = (getattr(f, "filename", "") or "")
            suffix = fname.split(".")[-1].lower() if "." in fname else "bin"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}")
        data = await f.read()
        tmp.write(data)
        tmp.close()

        saved_paths.append((tmp.name, getattr(f, "filename", None)))
        logger.info(
            f"Saved attachment to {tmp.name} "
            f"(orig={getattr(f, 'filename', None)}, {len(data)} bytes, ctype={ctype})"
        )

    content = body_plain or body_html
    instruction = f"{subject}\n\n{content}".strip()

    background_tasks.add_task(process_and_reply, sender, subject, instruction, saved_paths)
    return {"status": "accepted"}


def build_reply_subject(original_subject: str) -> str:
    if original_subject.lower().startswith("re:"):
        return original_subject
    return f"Re: {original_subject}" if original_subject else "Re: Votre demande IA"


def infer_recipient(sender_email: str) -> str:
    return sender_email


async def process_and_reply(sender: str, subject: str, instruction: str, saved_paths):
    try:
        logger.info("Processing instruction...")
        result = await route_instruction(instruction, saved_paths)
        body = (
            "✅ Voici le résultat de votre demande.\n\n"
            f"Résumé:\n{result.summary}\n\n"
            "Fichiers générés en pièce jointe si applicable."
        )
        attachments = result.attachments  # List[(filename, bytes, mime)]

        await send_email(
            to=infer_recipient(sender),
            subject=build_reply_subject(subject),
            text=body,
            attachments=attachments,
        )
        logger.info("Reply sent.")
    except Exception as e:
        logger.exception(e)
        await send_email(
            to=infer_recipient(sender),
            subject=build_reply_subject(subject),
            text=(
                "❗ Une erreur est survenue lors du traitement de votre demande (MVP).\n"
                "Merci de réessayer avec un fichier plus léger ou une instruction plus simple."
            ),
            attachments=[],
        )