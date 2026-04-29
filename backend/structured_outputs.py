"""
Structured outputs — LLM returns JSON for rich UI rendering.

Why structured outputs:
Plain text answers work but miss UI opportunities.
"The revenue was $2.4M in Q3" as plain text = boring.
As structured output = rendered as a highlighted metric card.

Query type → output format:
  factual      → standard answer + key facts sidebar
  comparison   → structured comparison table
  list         → bulleted list with expandable details
  metric       → highlighted number with context
  timeline     → chronological sequence
  explanation  → step-by-step breakdown

The frontend reads "output_type" and renders accordingly.
"""

import json
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_FAST, LLM_POWERFUL

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def detect_output_type(query: str) -> str:
    """Classify what type of structured output this query needs."""
    query_lower = query.lower()

    if any(s in query_lower for s in ["compare", "difference", "vs", "versus", "contrast"]):
        return "comparison"
    if any(s in query_lower for s in ["list", "enumerate", "what are all", "give me all"]):
        return "list"
    if any(s in query_lower for s in ["how many", "percentage", "rate", "score", "number of", "$", "revenue"]):
        return "metric"
    if any(s in query_lower for s in ["timeline", "chronological", "history", "when did", "sequence of"]):
        return "timeline"
    if any(s in query_lower for s in ["how does", "explain how", "step by step", "walk me through"]):
        return "explanation"

    return "standard"


def generate_structured_answer(
    query:       str,
    context:     str,
    output_type: str,
    history:     list[dict] = None,
) -> dict:
    """
    Generate a structured answer based on the detected output type.
    Returns a dict that the frontend renders into rich UI components.
    """
    history = history or []

    if output_type == "comparison":
        return _generate_comparison(query, context)
    elif output_type == "list":
        return _generate_list(query, context)
    elif output_type == "metric":
        return _generate_metric(query, context)
    elif output_type == "timeline":
        return _generate_timeline(query, context)
    elif output_type == "explanation":
        return _generate_explanation(query, context)
    else:
        return _generate_standard(query, context, history)


def _generate_comparison(query: str, context: str) -> dict:
    prompt = f"""Answer this comparison question using only the context.
Return ONLY valid JSON with this structure:
{{
  "answer": "brief narrative answer",
  "items": [
    {{
      "name": "Item A",
      "attributes": [
        {{"label": "attribute", "value": "value"}}
      ]
    }},
    {{
      "name": "Item B", 
      "attributes": [
        {{"label": "attribute", "value": "value"}}
      ]
    }}
  ],
  "key_differences": ["difference 1", "difference 2"],
  "citations": ["[Source 1]", "[Source 2]"]
}}

Context: {context[:3000]}
Question: {query}

JSON:"""

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_POWERFUL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.1,
        )
        raw  = resp.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["output_type"] = "comparison"
        return data
    except Exception:
        return _generate_standard(query, context, [])


def _generate_list(query: str, context: str) -> dict:
    prompt = f"""Answer this list question using only the context.
Return ONLY valid JSON:
{{
  "answer": "brief intro sentence",
  "items": [
    {{"title": "item name", "description": "detail", "citation": "[Source N]"}}
  ]
}}

Context: {context[:3000]}
Question: {query}
JSON:"""

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
        )
        raw  = resp.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["output_type"] = "list"
        return data
    except Exception:
        return _generate_standard(query, context, [])


def _generate_metric(query: str, context: str) -> dict:
    prompt = f"""Extract the key metric/number from the context for this question.
Return ONLY valid JSON:
{{
  "answer": "full explanation",
  "metric_value": "2.4M",
  "metric_label": "Q3 Revenue",
  "metric_context": "up 15% from Q2",
  "citation": "[Source N]"
}}

Context: {context[:3000]}
Question: {query}
JSON:"""

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.0,
        )
        raw  = resp.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["output_type"] = "metric"
        return data
    except Exception:
        return _generate_standard(query, context, [])


def _generate_timeline(query: str, context: str) -> dict:
    prompt = f"""Create a timeline answer from the context.
Return ONLY valid JSON:
{{
  "answer": "brief overview",
  "events": [
    {{"date": "2018", "event": "what happened", "citation": "[Source N]"}}
  ]
}}

Context: {context[:3000]}
Question: {query}
JSON:"""

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.1,
        )
        raw  = resp.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["output_type"] = "timeline"
        return data
    except Exception:
        return _generate_standard(query, context, [])


def _generate_explanation(query: str, context: str) -> dict:
    prompt = f"""Explain this step by step using only the context.
Return ONLY valid JSON:
{{
  "answer": "brief overview",
  "steps": [
    {{"number": 1, "title": "step name", "detail": "explanation", "citation": "[Source N]"}}
  ]
}}

Context: {context[:3000]}
Question: {query}
JSON:"""

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
        )
        raw  = resp.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        data["output_type"] = "explanation"
        return data
    except Exception:
        return _generate_standard(query, context, [])


def _generate_standard(query: str, context: str, history: list) -> dict:
    """Fallback to standard text answer."""
    history_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-4:]
        if m["role"] in ("user", "assistant")
    ]

    messages = (
        [{"role": "system", "content":
            "Answer using ONLY the provided context. Cite as [Source N]. "
            "If insufficient, state what's missing."}]
        + history_messages
        + [{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}]
    )

    try:
        resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=messages,
            max_tokens=600,
            temperature=0.2,
        )
        return {
            "output_type": "standard",
            "answer":      resp.choices[0].message.content,
        }
    except Exception:
        return {"output_type": "standard", "answer": "Unable to generate answer."}
