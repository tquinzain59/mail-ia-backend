# src/ai/router.py
from dataclasses import dataclass
from typing import List, Tuple, Optional
from loguru import logger
from src.ai.pdf_summarizer import summarize_pdf

@dataclass
class IAResult:
    summary: str
    attachments: List[Tuple[str, bytes, str]]  # (filename, data, mime)

# --- Détection d'intention plus tolérante ---
def _has_summary_intent(instruction: str) -> bool:
    instr = instruction.lower()
    keys = ["résume", "resume", "résumé", "summary", "synthèse", "synthétise"]
    return any(k in instr for k in keys)

def _is_pdf_candidate(tmp_path: str, orig_name: Optional[str]) -> bool:
    """
    Considère comme PDF si :
    - le nom original finit par .pdf, ou
    - le chemin temporaire finit par .pdf (cas où on force le suffixe),
    """
    if orig_name and orig_name.lower().endswith(".pdf"):
        return True
    if tmp_path.lower().endswith(".pdf"):
        return True
    return False

def _wants_pdf_summary(instruction: str, saved_paths: List[Tuple[str, Optional[str]]]) -> bool:
    """
    L'utilisateur veut un résumé ET mentionne 'pdf' OU a joint un PDF.
    """
    instr = instruction.lower()
    if not _has_summary_intent(instr):
        return False
    return ("pdf" in instr) or any(_is_pdf_candidate(p, n) for (p, n) in saved_paths)

async def route_instruction(instruction: str, saved_paths: List[Tuple[str, Optional[str]]]) -> IAResult:
    """
    Décide quel module appeler. MVP: résumé PDF si demandé, sinon stub.
    saved_paths: List[(tmp_path, original_filename)]
    """
    # --- Résumé de PDF ---
    if _wants_pdf_summary(instruction, saved_paths):
        # 1) Chercher une PJ reconnue comme PDF
        pdf = None
        for tmp_path, orig in saved_paths:
            if _is_pdf_candidate(tmp_path, orig):
                pdf = (tmp_path, orig)
                break
        # 2) Fallback : s'il n'y a qu'UNE pièce jointe, tente quand même
        if not pdf and len(saved_paths) == 1:
            pdf = saved_paths[0]

        if not pdf:
            return IAResult(
                summary="Vous avez demandé un résumé PDF mais aucune pièce jointe .pdf n’a été trouvée.",
                attachments=[],
            )

        tmp_path, orig = pdf
        try:
            summary = summarize_pdf(tmp_path)
            data = summary.encode("utf-8")
            return IAResult(
                summary="Résumé généré. Voir ci-dessous et en pièce jointe `resume.txt`.",
                attachments=[("resume.txt", data, "text/plain")],
            )
        except Exception as e:
            logger.exception(e)
            return IAResult(
                summary=f"Erreur lors du résumé du PDF (MVP) : {e}",
                attachments=[],
            )

    # --- Stub par défaut ---
    return IAResult(
        summary="Demande reçue (stub). Essayez : « Résume ce PDF » avec un .pdf en pièce jointe.",
        attachments=[],
    )