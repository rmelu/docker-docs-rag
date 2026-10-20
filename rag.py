import logging
import os
import sys

import psycopg
from dotenv import load_dotenv
from fastembed import TextEmbedding
from openai import OpenAI
from pgvector.psycopg import register_vector

from ingest import DSN, MODELLO

load_dotenv()
logger = logging.getLogger("uvicorn.error")

SOGLIA = 0.35   # sotto questa somiglianza il passaggio non e' pertinente
_modello = None

ISTRUZIONI = (
    "You are an assistant for the official Docker documentation. "
    "Answer using ONLY the passages provided. "
    "LANGUAGE RULE: reply in the same language as the user's question "
    "(English question -> English answer; Italian question -> Italian answer), "
    "even though these instructions are in English. "
    "Write plain text: no tables and no markdown symbols (no ** or #); "
    "use at most lists with a dash. "
    "If the passages are not enough to answer, say so clearly without inventing anything. "
    "Cite sources with their number in square brackets, for example [1]."
)

def embed(testo: str):
    global _modello
    if _modello is None:
        _modello = TextEmbedding(MODELLO)
    return next(iter(_modello.embed([testo])))


def cerca(domanda: str, k: int = 4):
    v = embed(domanda)
    with psycopg.connect(DSN) as conn:
        register_vector(conn)
        return conn.execute(
            """
            SELECT source, content, 1 - (embedding <=> %s) AS similarita
            FROM chunks
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (v, v, k),
        ).fetchall()


def chiedi_llm(domanda: str, passaggi) -> str:
    contesto = "\n\n".join(
        f"[{i}] ({source})\n{content}" for i, (source, content, _) in enumerate(passaggi, 1)
    )
    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.getenv("LLM_BASE_URL") or None,
    )
    try:
        risp = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            temperature=0.2,
            messages=[
                {"role": "system", "content": ISTRUZIONI},
                {"role": "user", "content": f"Passages:\n{contesto}\n\nQuestion: {domanda}\n\n(Reply in the same language as the question above.)"},
            ],
        )
    except Exception as e:
        logger.error("Errore LLM: %s", e)
        raise RuntimeError("Errore nel servizio LLM") from e
    return risp.choices[0].message.content


def rispondi(domanda: str, k: int = 4) -> dict:
    passaggi = cerca(domanda, k)
    passaggi = [p for p in passaggi if p[2] >= SOGLIA]
    fonti = [
        {"source": s, "similarita": round(float(sim), 3), "testo": c}
        for s, c, sim in passaggi
    ]
    if not passaggi:
        return {
            "risposta": "Non ho trovato nella documentazione informazioni pertinenti. / "
            "I couldn't find relevant information in the documentation.",
            "fonti": [],
        }
    if not os.getenv("LLM_API_KEY"):
        return {"risposta": None, "nota": "LLM non configurato: mostro solo le fonti.", "fonti": fonti}
    return {"risposta": chiedi_llm(domanda, passaggi), "fonti": fonti}


if __name__ == "__main__":
    domanda = " ".join(sys.argv[1:]) or "Come si definisce un volume in Docker Compose?"
    r = rispondi(domanda)
    print(r["risposta"] or r.get("nota"))
    for f in r["fonti"]:
        print(f"\n[{f['similarita']:.2f}] {f['source']}\n{f['testo'][:200]}")