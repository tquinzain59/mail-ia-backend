# src/ai/pdf_summarizer.py
import os
from typing import List
from loguru import logger
from pypdf import PdfReader

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False

MAX_CHARS = 12000  # pour éviter d'envoyer des pavés trop gros au LLM
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    chunks = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt:
            chunks.append(txt.strip())
    text = "\n\n".join(chunks).strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[...tronqué pour le MVP...]"
    return text

def _summarize_text_locally(text: str) -> str:
    # Fallback simple quand pas d’API : on renvoie un TL;DR naïf (premiers paragraphes)
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    head = "\n".join(paragraphs[:8])
    return (
        "Résumé (heuristique locale, sans LLM) :\n"
        + head[:1500]
        + ("\n\n[Résumé local tronqué]" if len(head) > 1500 else "")
    )

def _summarize_with_openai(text: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not _HAS_OPENAI:
        logger.warning("OPENAI_API_KEY manquant ou bibliothèque indisponible — fallback local.")
        return _summarize_text_locally(text)

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "Tu es un assistant qui produit des résumés clairs, structurés et concis.\n"
        "Règles:\n"
        "- 6 à 10 puces maximum\n"
        "- Mots simples, pas de jargon\n"
        "- Extrais chiffres clés s'il y en a\n"
        "- Conclus par 1 phrase 'À retenir'\n"
    )
    user_prompt = f"Voici le texte extrait d'un PDF. Fais un résumé conforme aux règles ci-dessus.\n\n=== TEXTE ===\n{text}\n=== FIN ==="

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()

def summarize_pdf(path: str) -> str:
    text = _extract_text_from_pdf(path)
    if not text:
        return "Le PDF ne contient pas de texte extractible (scanné/image ?) pour ce MVP."
    return _summarize_with_openai(text)