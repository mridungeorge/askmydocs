"""
Two ways to run:

    CLI:   python main.py
    API:   uvicorn main:app --reload
           POST http://localhost:8000/research/run
           {"topic": "agentic RAG systems for academic research"}
"""

import asyncio

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from pydantic import BaseModel

from state import initial_state
from graph import build_graph

app = FastAPI(title="Research Conductor")
_graph = build_graph()


class ResearchRequest(BaseModel):
    topic: str
    paper_paths: list[str] = []


@app.post("/research/run")
async def run_research(req: ResearchRequest):
    state = initial_state(req.topic, req.paper_paths)
    result = await _graph.ainvoke(state)
    return result


async def _cli_main():
    topic = "Agentic RAG systems for academic research"
    print(f"\nStarting research on: {topic}\n")
    print("-" * 60)

    state = initial_state(topic)
    result = await _graph.ainvoke(state)

    print("-" * 60)
    print("\n=== SUMMARY ===")
    print(f"Currency:   {result['currency_verdict']} (score: {result['currency_score']})")
    print(f"Reason:     {result['currency_reason']}")
    print(f"Memory:     {result['memory_context']}")
    print(f"Critic #1:  {result['critic1_notes']}")
    print(f"Rounds:     {result['round_num']} | Final verdict: {result['final_verdict']}")
    print(f"Confidence: {result['confidence']}")

    if result["human_needed"]:
        print("\n[!] HUMAN GATE: Critic could not be satisfied after max rounds.")
        print(f"   Outstanding issues: {result['critic_feedback']}")

    print("\n=== DRAFT ===\n")
    print(result["draft"])


if __name__ == "__main__":
    asyncio.run(_cli_main())
