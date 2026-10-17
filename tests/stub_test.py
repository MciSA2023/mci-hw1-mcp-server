"""Verkabelungstest ohne API-Key: ersetzt NUR den LLM-Aufruf durch ein skriptiertes Stub-Modell.
Die MCP-Verbindung, Tool-Discovery, Tool-Aufrufe und Message-Handling laufen echt."""
import asyncio, json, sys
from types import SimpleNamespace as NS
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_loop

def tc(i, name, args):
    return NS(id=f"c{i}", function=NS(name=name, arguments=json.dumps(args)))

def fake_llm(messages, tools):
    assert {t["function"]["name"] for t in tools} == {"query_inventory", "calculate_tiered_discount", "log_audit_event"}
    n_obs = sum(1 for m in messages if m["role"] == "tool")
    obs = [m["content"] for m in messages if m["role"] == "tool"]
    if n_obs == 0:
        content, calls = "Thought: Ich brauche Preis und Lagerbestand.", [tc(1, "query_inventory", {"product_name": "Wedding Video"})]
    elif n_obs == 1:
        content, calls = "Thought: Jetzt den Rabatt für 6 Stück.", [tc(2, "calculate_tiered_discount", {"unit_price": 1250.0, "volume": 6})]
    elif n_obs == 2:
        content, calls = "Thought: Kalkulation protokollieren.", [tc(3, "log_audit_event", {"event_description": "Stub: Kalkulation 6x Wedding Video"})]
    else:
        content, calls = f"Final (Stub): {obs[1]}", None
    msg = NS(content=content, tool_calls=calls, model_dump=lambda exclude_none=True: {
        "role": "assistant", "content": content,
        **({"tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]} if calls else {})})
    return NS(choices=[NS(message=msg)])

agent_loop.llm_call = fake_llm
agent_loop.LOG_FILE = Path("/tmp/stub_exec.log")
out = asyncio.run(agent_loop.run_agent(agent_loop.DEFAULT_TASK))
assert "7125.00" in out, out
print("\nSTUB TEST OK")
