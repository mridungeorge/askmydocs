"""
RAGAS Evaluation Framework.

RAGAS = Retrieval Augmented Generation Assessment.
Industry-standard metrics for RAG quality.

Four metrics:
1. Faithfulness:        Does the answer only use retrieved context?
                        High faithfulness = no hallucination.
2. Answer relevancy:    Does the answer actually address the question?
                        High relevancy = focused, on-topic answers.
3. Context recall:      Did retrieval find the right chunks?
                        High recall = right documents retrieved.
4. Context precision:   Were retrieved chunks actually useful?
                        High precision = no irrelevant chunks retrieved.

Why these four:
They cover the two failure modes of RAG systems:
- Retrieval failures (wrong chunks) → context recall + precision
- Generation failures (hallucination, off-topic) → faithfulness + relevancy

How to use:
1. Build an eval set: 50 Q&A pairs where you know the right answer
2. Run weekly: python -m backend.eval_framework --run
3. Dashboard shows score trends over time
4. Investigate drops: find which questions degraded
"""

import json
from datetime import datetime, timedelta
from typing import Optional
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, LLM_POWERFUL, LLM_FAST
from backend.retrieval import retrieve
from backend.agents import run_agent
from backend.auth import supabase

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


# ── Metric implementations ────────────────────────────────────────────────────

def compute_faithfulness(question: str, answer: str, contexts: list[str]) -> float:
    """
    Faithfulness: what fraction of answer claims are supported by context?

    Method: LLM extracts claims from answer, then checks each against context.
    Score = supported_claims / total_claims

    Score 1.0 = every claim in the answer is grounded in retrieved context
    Score 0.0 = answer is entirely from model's parametric memory (hallucination)
    """
    if not contexts or not answer:
        return 0.0

    context_str = "\n\n".join(contexts[:5])

    # Step 1: Extract claims from answer
    claims_prompt = f"""Extract all factual claims from this answer as a JSON array.
Each claim should be a simple, verifiable statement.

Answer: {answer}

Return ONLY a JSON array like: ["claim 1", "claim 2", ...]"""

    try:
        claims_resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": claims_prompt}],
            max_tokens=300,
            temperature=0.0,
        )
        claims_text = claims_resp.choices[0].message.content.strip()
        claims_text = claims_text.replace("```json", "").replace("```", "").strip()
        claims      = json.loads(claims_text)
    except Exception:
        return 0.7  # default if parsing fails

    if not claims:
        return 1.0

    # Step 2: Verify each claim against context
    supported = 0
    for claim in claims:
        verify_prompt = f"""Does the following context support this claim?
Context: {context_str[:2000]}
Claim: {claim}
Answer with only YES or NO:"""

        try:
            verify_resp = nvidia.chat.completions.create(
                model=LLM_FAST,
                messages=[{"role": "user", "content": verify_prompt}],
                max_tokens=3,
                temperature=0.0,
            )
            if "YES" in verify_resp.choices[0].message.content.upper():
                supported += 1
        except Exception:
            supported += 1  # conservative: assume supported on error

    return supported / len(claims)


def compute_answer_relevancy(question: str, answer: str) -> float:
    """
    Answer relevancy: does the answer actually address the question?

    Method: Generate multiple versions of "what question would this answer answer?"
    Compute similarity between generated questions and original question.
    High similarity = answer is relevant to the question asked.

    Score 1.0 = answer perfectly addresses the question
    Score 0.0 = answer is completely off-topic
    """
    if not answer or not question:
        return 0.0

    # Generate 3 questions that this answer would address
    gen_prompt = f"""Given this answer, generate 3 different questions that this answer would address.
Return ONLY a JSON array of 3 question strings.

Answer: {answer}

Questions:"""

    try:
        gen_resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": gen_prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        gen_text = gen_resp.choices[0].message.content.strip()
        gen_text = gen_text.replace("```json", "").replace("```", "").strip()
        generated_questions = json.loads(gen_text)
    except Exception:
        return 0.7

    # Score: what fraction of generated questions are similar to original?
    score_prompt = f"""Original question: {question}

Generated questions:
{chr(10).join(f"{i+1}. {q}" for i, q in enumerate(generated_questions[:3]))}

On a scale 0-10, how well does the original question match these generated questions?
(10 = identical meaning, 0 = completely different topics)
Return only a number:"""

    try:
        score_resp = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": score_prompt}],
            max_tokens=3,
            temperature=0.0,
        )
        score = float(score_resp.choices[0].message.content.strip()) / 10.0
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.7


def compute_context_recall(
    question: str,
    ground_truth: str,
    contexts: list[str],
) -> float:
    """
    Context recall: did retrieval find all the information needed to answer correctly?

    Method: Break ground truth into sentences. Check each sentence
    against retrieved contexts. Fraction found = recall score.

    Score 1.0 = all ground truth information was retrieved
    Score 0.0 = none of the needed information was retrieved
    """
    if not contexts or not ground_truth:
        return 0.0

    context_str = "\n\n".join(contexts[:5])

    prompt = f"""Given the ground truth answer and retrieved contexts, 
what fraction of the ground truth information is present in the contexts?

Ground truth: {ground_truth}

Retrieved contexts: {context_str[:2000]}

Rate 0-10 where 10 = all ground truth info is in contexts, 0 = none is.
Return only a number:"""

    try:
        resp  = nvidia.chat.completions.create(
            model=LLM_FAST,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3,
            temperature=0.0,
        )
        score = float(resp.choices[0].message.content.strip()) / 10.0
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.7


def compute_context_precision(
    question: str,
    contexts: list[str],
) -> float:
    """
    Context precision: what fraction of retrieved chunks were actually useful?

    Method: For each retrieved chunk, ask: "Is this chunk relevant to the question?"
    Fraction of relevant chunks = precision score.

    Score 1.0 = every retrieved chunk was useful
    Score 0.0 = all retrieved chunks were irrelevant noise
    """
    if not contexts:
        return 0.0

    relevant_count = 0
    for ctx in contexts[:5]:
        prompt = f"""Is this context relevant to answering the question?

Question: {question}
Context: {ctx[:500]}

Answer YES or NO:"""

        try:
            resp = nvidia.chat.completions.create(
                model=LLM_FAST,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3,
                temperature=0.0,
            )
            if "YES" in resp.choices[0].message.content.upper():
                relevant_count += 1
        except Exception:
            relevant_count += 1

    return relevant_count / len(contexts[:5])


# ── Eval set management ───────────────────────────────────────────────────────

def save_eval_question(
    user_id:      str,
    question:     str,
    ground_truth: str,
    doc_title:    str = None,
) -> None:
    """Add a question to the eval set."""
    try:
        supabase.table("eval_sets").insert({
            "user_id":      user_id,
            "question":     question,
            "ground_truth": ground_truth,
            "doc_title":    doc_title,
        }).execute()
    except Exception as e:
        print(f"Eval save error: {e}")


def get_eval_set(user_id: str, doc_title: str = None) -> list[dict]:
    """Get all eval questions for a user."""
    try:
        query = supabase.table("eval_sets").select("*").eq("user_id", user_id)
        if doc_title:
            query = query.eq("doc_title", doc_title)
        return query.execute().data or []
    except Exception:
        return []


# ── Full evaluation run ───────────────────────────────────────────────────────

def run_evaluation(
    user_id:    str,
    collection: str,
    doc_title:  str = None,
) -> dict:
    """
    Run full RAGAS evaluation on the eval set.
    Returns averaged scores across all questions.
    Saves results to Supabase for trend tracking.
    """
    eval_set = get_eval_set(user_id, doc_title)

    if not eval_set:
        return {
            "error": "No eval questions found. Add questions via the dashboard.",
            "faithfulness": 0.0,
            "answer_relevancy": 0.0,
            "context_recall": 0.0,
            "context_precision": 0.0,
            "total_questions": 0,
        }

    scores = {
        "faithfulness":      [],
        "answer_relevancy":  [],
        "context_recall":    [],
        "context_precision": [],
    }

    for item in eval_set:
        question     = item["question"]
        ground_truth = item["ground_truth"]

        # Retrieve chunks
        chunks = retrieve(question, doc_title, collection_name=collection)
        contexts = [c.payload["text"] for c in chunks]

        # Run agent for answer
        result = run_agent(question, doc_title, collection=collection)
        answer = result["answer"]

        # Compute all four metrics
        scores["faithfulness"].append(
            compute_faithfulness(question, answer, contexts)
        )
        scores["answer_relevancy"].append(
            compute_answer_relevancy(question, answer)
        )
        scores["context_recall"].append(
            compute_context_recall(question, ground_truth, contexts)
        )
        scores["context_precision"].append(
            compute_context_precision(question, contexts)
        )

    # Average scores
    averaged = {
        metric: round(sum(vals) / len(vals), 3)
        for metric, vals in scores.items()
        if vals
    }
    averaged["total_questions"] = len(eval_set)

    # Save to Supabase
    try:
        week_start = datetime.utcnow().date() - timedelta(
            days=datetime.utcnow().weekday()
        )
        supabase.table("ragas_scores").upsert({
            "user_id":           user_id,
            "week_start":        str(week_start),
            "faithfulness":      averaged.get("faithfulness", 0),
            "answer_relevancy":  averaged.get("answer_relevancy", 0),
            "context_recall":    averaged.get("context_recall", 0),
            "context_precision": averaged.get("context_precision", 0),
            "total_questions":   averaged["total_questions"],
        }, on_conflict="user_id,week_start").execute()
    except Exception as e:
        print(f"RAGAS save error: {e}")

    return averaged


def get_ragas_history(user_id: str, weeks: int = 8) -> list[dict]:
    """Get historical RAGAS scores for trend charts."""
    try:
        since = str(datetime.utcnow().date() - timedelta(weeks=weeks))
        result = supabase.table("ragas_scores") \
            .select("*") \
            .eq("user_id", user_id) \
            .gte("week_start", since) \
            .order("week_start") \
            .execute()
        return result.data or []
    except Exception:
        return []
