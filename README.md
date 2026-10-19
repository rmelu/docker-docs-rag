# Docker Docs RAG

API che risponde in italiano a domande sulla documentazione ufficiale di Docker
(sezioni Compose ed Engine), usando RAG (Retrieval-Augmented Generation): recupera
i passaggi più rilevanti e li passa a un LLM, che scrive una risposta citando le fonti.

## Come funziona

1. **Ingestione** (`ingest.py`): i file Markdown della documentazione vengono puliti,
   divisi in pezzi da massimo 500 caratteri (con 80 di sovrapposizione), trasformati
   in embedding con `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensioni, funziona
   anche con domande in italiano) e salvati in PostgreSQL con l'estensione pgvector.
2. **Ricerca** (`rag.py`): la domanda diventa un embedding e si cercano i `k` pezzi
   più simili (similarità coseno, indice HNSW). Sotto la soglia di 0.35 il sistema
   risponde "Non ho trovato..." senza chiamare l'LLM.
3. **Risposta** (`main.py`): i pezzi trovati vengono passati a un LLM (Groq,
   `openai/gpt-oss-20b`) che risponde in italiano con riferimenti `[1]`, `[2]`...
   corrispondenti alle fonti restituite.

Se la chiave dell'LLM non è configurata, l'API restituisce comunque le fonti con una nota.

## Stack

Python, FastAPI, PostgreSQL + pgvector, fastembed, API compatibile OpenAI (Groq), Docker Compose.

## Requisiti

- Python 3.10+
- Docker e Docker Compose
- Una chiave API Groq (console.groq.com)
- La documentazione Docker in `data/docker-docs/` (repository `docker/docs`)

## Avvio

```bash
git clone <url-del-repository>
cd Progetto_RAG

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d                      # avvia PostgreSQL con pgvector e crea tabella e indice

git clone --depth 1 https://github.com/docker/docs data/docker-docs   # scarica la documentazione


cp .env.example .env                      # poi inserisci la tua chiave in .env
python ingest.py                          # calcola gli embedding (solo la prima volta)
uvicorn main:app --reload --port 8005
```

Documentazione interattiva: http://localhost:8005/docs

## Configurazione

Le variabili stanno in `.env`, che non va mai su GitHub (è nel `.gitignore`).
`.env.example` contiene solo i nomi:

| Variabile      | Descrizione                                   |
|----------------|-----------------------------------------------|
| `LLM_API_KEY`  | Chiave API del provider                       |
| `LLM_BASE_URL` | Endpoint compatibile OpenAI                   |
| `LLM_MODEL`    | Nome del modello                              |

Esempio: `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-20b`.
Il `.env` viene letto solo all'avvio: dopo ogni modifica riavvia il server.

## Uso

`POST /ask`

```bash
curl -X POST http://localhost:8005/ask \
  -H "Content-Type: application/json" \
  -d '{"domanda": "come limito la memoria di un container", "k": 4}'
```

- `domanda`: testo di almeno 3 caratteri
- `k`: numero di pezzi da recuperare (1-10, default 4)

Risposte possibili: `200` con risposta e fonti, `422` se i parametri non sono validi,
`502` se il servizio LLM non risponde.

## Esempi

**Domanda sulla documentazione:** "come limito la memoria di un container"
→ risposta in italiano con `docker run --memory="512m"` per il limite hard e
`--memory-reservation` per il limite soft, con riferimenti a
`engine/containers/resource_constraints.md`.

**Domanda fuori tema:** "qual è la capitale della Francia?"
→ `"Non ho trovato nella documentazione informazioni pertinenti."` (nessuna fonte,
nessuna chiamata all'LLM).

## Limiti noti

- Le risposte dipendono dai pezzi recuperati: una domanda formulata in modo diverso
  dalla documentazione può pescare passaggi poco pertinenti (per esempio, una domanda
  sui volumi in Compose può restituire pagine sui volumi di Engine).
- I pezzi sono limitati a 500 caratteri perché il modello di embedding legge circa
  128 token: tabelle e blocchi di codice lunghi vengono spezzati.
- La documentazione è una copia statica: per aggiornarla, aggiorna `data/docker-docs`
  e rilancia `ingest.py`.
- Nessuna autenticazione e credenziali del database di esempio (`rag:rag`): pensato
  solo per uso locale, non esporre le porte su internet.

## Possibili sviluppi

- Reranking dei risultati per migliorare la pertinenza
- Interfaccia web
- Valutazione automatica della qualità delle risposte