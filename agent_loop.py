"""ReAct-Agent-Loop: ein echtes LLM (via LiteLLM) entscheidet, welche MCP-Tools aufgerufen werden.

Ablauf pro Schritt:  Thought (LLM-Text)  ->  Action (tool_call)  ->  Observation (MCP-Ergebnis)
Der Loop endet, sobald das LLM keinen Tool-Call mehr macht (= finale Antwort).
"""
import asyncio
import json
import os
import time
import sys
from datetime import datetime
from pathlib import Path

import litellm
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Modell und Endpoint sind per Umgebungsvariable änderbar:
#  - direkt Gemini:      LLM_MODEL=gemini/gemini-flash-latest  + GEMINI_API_KEY
#  - LiteLLM-Proxy:      LLM_MODEL=openai/<alias> + LLM_API_BASE=http://localhost:4000 + LLM_API_KEY
MODEL = os.getenv("LLM_MODEL", "gemini/gemini-flash-latest")
API_BASE = os.getenv("LLM_API_BASE") or None
API_KEY = os.getenv("LLM_API_KEY") or None
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
LOG_FILE = BASE_DIR / "execution_log.txt"

SYSTEM_PROMPT = (
    "You are a sales assistant for a small IT & media freelancer. You work with the ReAct pattern: "
    "before EVERY tool call write one short sentence starting with 'Thought:' that explains what you "
    "need next and why. Use the available tools to get real data, never invent prices, stock or "
    "discounts. When you have computed a quotation, write an audit event with the audit tool. "
    "Finish with a short final answer in the language of the user."
)

DEFAULT_TASK = (
    "Ein Kunde möchte 6 Wedding Video Packages. Prüfe, ob genug auf Lager ist, berechne den "
    "Gesamtpreis inklusive Mengenrabatt und protokolliere die Kalkulation im Audit-Log."
)


def log(text: str = "") -> None:
    """Auf Konsole ausgeben und in execution_log.txt mitschreiben (Abgabe-Beleg)."""
    print(text, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def mcp_to_openai_tools(mcp_tools) -> list[dict]:
    """MCP-Tool-Beschreibungen ins OpenAI/LiteLLM-Function-Calling-Format übersetzen."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": getattr(t, "inputSchema", None) or t.input_schema,  # mcp 1.x / 2.x
            },
        }
        for t in mcp_tools
    ]


LLM_RETRIES = int(os.getenv("LLM_RETRIES", "4"))                       # Wiederholungen pro Modell (mit Backoff)
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "90"))                        # Sekunden pro Anfrage
FALLBACKS = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
TEMPERATURE = os.getenv("LLM_TEMPERATURE")                              # leer = Modell-Default (Gemini 3 empfiehlt das)
litellm.suppress_debug_info = True


def llm_call(messages, tools):
    """LLM-Anfrage mit eigenem Retry (503/429/Timeouts) und optionalen Fallback-Modellen.
    Bewusst ohne litellm-num_retries, denn das braucht das Zusatzpaket 'tenacity'."""
    retryable = (litellm.ServiceUnavailableError, litellm.RateLimitError, litellm.InternalServerError,
                 litellm.Timeout, litellm.APIConnectionError)
    last_error = None
    for model in [MODEL, *FALLBACKS]:
        for attempt in range(1, LLM_RETRIES + 1):
            try:
                kwargs = dict(model=model, messages=messages, api_base=API_BASE, api_key=API_KEY, timeout=LLM_TIMEOUT)
                if tools:
                    kwargs.update(tools=tools, tool_choice="auto")
                if TEMPERATURE:
                    kwargs["temperature"] = float(TEMPERATURE)
                return litellm.completion(**kwargs)
            except retryable as e:
                last_error = e
                print(f"[LLM] {model}: {type(e).__name__} (Versuch {attempt}/{LLM_RETRIES})", flush=True)
                if attempt < LLM_RETRIES:
                    time.sleep(min(2 ** attempt, 20))
        print(f"[LLM] {model} nicht verfuegbar - versuche naechstes Modell", flush=True)
    raise RuntimeError(f"LLM nicht erreichbar (Modelle {[MODEL, *FALLBACKS]}): {last_error}")


async def run_agent(task: str) -> str:
    log(f"\n===== Run {datetime.now():%Y-%m-%d %H:%M:%S} | model={MODEL} =====")
    log(f"[User] {task}\n")

    # sys.executable: derselbe Python-Interpreter wie der Agent (kein hartcodierter Pfad)
    server_params = StdioServerParameters(
        command=sys.executable, args=[str(BASE_DIR / "mcp_server.py")]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            log(f"Connected! Discovered MCP tools: {[t.name for t in mcp_tools]}\n")
            tools = mcp_to_openai_tools(mcp_tools)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]
            for step in range(1, MAX_STEPS + 1):
                response = await asyncio.to_thread(llm_call, messages, tools)
                msg = response.choices[0].message
                messages.append(msg.model_dump(exclude_none=True))

                if msg.content:
                    log(f"[Reasoning #{step}] {msg.content.strip()}")

                if not msg.tool_calls:  # keine Aktion mehr -> finale Antwort
                    log("\n=== Final Synthesis Result ===")
                    log((msg.content or "").strip())
                    return msg.content or ""

                for call in msg.tool_calls:
                    args = json.loads(call.function.arguments or "{}")
                    log(f"[Action #{step}] MCP tool '{call.function.name}' with {args}")
                    result = await session.call_tool(call.function.name, arguments=args)
                    text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                    log(f"[Observation #{step}] {text}\n")
                    messages.append(
                        {"role": "tool", "tool_call_id": call.id, "name": call.function.name, "content": text}
                    )

            log("Abbruch: MAX_STEPS erreicht ohne finale Antwort.")
            return ""


if __name__ == "__main__":
    asyncio.run(run_agent(" ".join(sys.argv[1:]) or DEFAULT_TASK))
