# Homework 1A – Custom MCP Math & Database Tool Server

MCP-Server in Python (FastMCP) mit **3 Tools**, angebunden an einen **ReAct-Agent-Loop mit echtem LLM (LiteLLM)**.

| Tool | Zweck |
|---|---|
| `query_inventory` | SQL-Lookup (sqlite3) im Produktinventar (Bestand, Preis) |
| `calculate_tiered_discount` | Formel-Engine: gestaffelter Mengenrabatt (ab 5 → 5 %, ab 20 → 15 %, ab 50 → 20 %) |
| `log_audit_event` | Hängt Audit-Events mit Zeitstempel an `audit_log.txt` an |

## Architektur
```
agent_loop.py (MCP-Client + ReAct-Loop)  --stdio-->  mcp_server.py (3 Tools, SQLite, Logfile)
        |
        +--> LiteLLM --> Gemini (oder LiteLLM-Proxy)
```
Ablauf: Das LLM schreibt einen *Thought*, wählt eine *Action* (Tool-Call), der MCP-Server liefert die *Observation*;
das wiederholt sich, bis das LLM ohne Tool-Call antwortet (finale Antwort). Der Loop startet den Server selbst als Subprozess.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env .env                                     # GEMINI_API_KEY eintragen (kostenlos: https://aistudio.google.com/apikey)
```

## Ausführen
```bash
python agent_loop.py                                     # Standardaufgabe (6 Wedding Video Packages)
python agent_loop.py "Wie viele NAS 4TB HDD sind auf Lager und was kosten 25 Stück mit Rabatt?"
```
Die Ausgabe (Reasoning / Action / Observation / Final) wird zusätzlich in `execution_log.txt` geschrieben.
`inventory.db` wird beim ersten Start automatisch angelegt.

### Optional: LiteLLM-Proxy statt direktem Gemini
```bash
litellm --model gemini/gemini-2.0-flash --port 4000     # GEMINI_API_KEY muss gesetzt sein
# .env:  LLM_MODEL=openai/gemini/gemini-2.0-flash   LLM_API_BASE=http://localhost:4000   LLM_API_KEY=anything
```

### Verkabelungstest ohne API-Key
`python tests/stub_test.py` ersetzt nur den LLM-Aufruf durch ein skriptiertes Stub-Modell und prüft MCP-Verbindung,
Tool-Discovery und alle drei Tool-Aufrufe. Für die Abgabe-Logs bitte den echten LLM-Lauf verwenden.

## Dateien
`mcp_server.py` · `agent_loop.py` · `requirements.txt` · `.env` · `execution_log.txt` (nach dem Lauf) · `tests/stub_test.py`
