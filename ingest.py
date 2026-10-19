import re
from pathlib import Path

import psycopg
from fastembed import TextEmbedding
from pgvector.psycopg import register_vector

BASE = Path("data/docker-docs/content/manuals")
SEZIONI = ["compose", "engine"]
MODELLO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DSN = "postgresql://rag:rag@localhost:5433/ragdb"
MAX_CHARS = 500   # il modello legge ~128 token: pezzi piu' lunghi verrebbero tagliati
OVERLAP = 80      # ultimi caratteri del pezzo precedente, per non perdere il filo


def pulisci(testo: str) -> str:
    # toglie il front matter iniziale (--- ... ---)
    return re.sub(r"\A---\n.*?\n---\n", "", testo, flags=re.DOTALL).strip()


def spezza(testo: str) -> list[str]:
    pezzi = []
    for p in testo.split("\n\n"):
        p = p.strip()
        while len(p) > MAX_CHARS:          # paragrafi lunghi (es. blocchi di codice)
            pezzi.append(p[:MAX_CHARS])
            p = p[MAX_CHARS:]
        if p:
            pezzi.append(p)

    chunks, corrente = [], ""
    for p in pezzi:
        if corrente and len(corrente) + len(p) + 2 > MAX_CHARS:
            chunks.append(corrente)
            corrente = corrente[-OVERLAP:] + "\n\n" + p
        else:
            corrente = corrente + "\n\n" + p if corrente else p
    if corrente:
        chunks.append(corrente)
    return chunks


def main():
    file_md = [f for s in SEZIONI for f in (BASE / s).rglob("*.md")]
    righe = []
    for f in file_md:
        testo = pulisci(f.read_text(encoding="utf-8"))
        origine = str(f.relative_to(BASE))
        for c in spezza(testo):
            righe.append((origine, c))
    print(f"{len(file_md)} file -> {len(righe)} chunk")

    print("Calcolo gli embedding (la prima volta scarica il modello)...")
    modello = TextEmbedding(MODELLO)
    vettori = list(modello.embed([c for _, c in righe]))

    with psycopg.connect(DSN) as conn:
        register_vector(conn)
        conn.execute("DELETE FROM chunks")   # cosi' si può rilanciare lo script
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (source, content, embedding) VALUES (%s, %s, %s)",
                [(s, c, v) for (s, c), v in zip(righe, vettori)],
            )
        conn.commit()
    print("Fatto.")


if __name__ == "__main__":
    main()