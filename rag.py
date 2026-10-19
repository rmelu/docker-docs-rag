import sys

import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

from ingest import DSN, MODELLO   # riuso la stessa configurazione

_modello = None


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


if __name__ == "__main__":
    domanda = " ".join(sys.argv[1:]) or "Come si definisce un volume in Docker Compose?"
    for source, content, sim in cerca(domanda):
        print(f"\n[{sim:.2f}] {source}\n{content[:300]}")