from fastapi import FastAPI
from pydantic import BaseModel, Field

from rag import cerca

app = FastAPI(title="Docker Docs RAG")


class Domanda(BaseModel):
    domanda: str = Field(min_length=3)
    k: int = Field(default=4, ge=1, le=10)


@app.post("/ask")
def ask(body: Domanda):
    risultati = cerca(body.domanda, body.k)
    return {
        "domanda": body.domanda,
        "fonti": [
            {"source": s, "similarita": round(float(sim), 3), "testo": c}
            for s, c, sim in risultati
        ],
    }