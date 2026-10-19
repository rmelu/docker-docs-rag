from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag import rispondi

app = FastAPI(title="Docker Docs RAG")


class Domanda(BaseModel):
    domanda: str = Field(min_length=3)
    k: int = Field(default=4, ge=1, le=10)


@app.post("/ask")
def ask(body: Domanda):
    try:
        return rispondi(body.domanda, body.k)
    except RuntimeError:
        raise HTTPException(status_code=502, detail="Il servizio LLM non ha risposto")