"""
hallucination_eval.py  –  MC-question approach to sanity-check summaries
=======================================================================
• Uses the *new* Mistral SDK (≥ 1.8, single `Mistral` class)
• Response format set to JSON → no fragile regex parsing
• One retry per batch; otherwise raises
"""

from __future__ import annotations

import json, time
from typing import List, Dict, Any

from mistralai import Mistral          # new unified client

# ──────────────────────────────────────────
# 0.  Global Mistral client (hard-coded key)
#     (replace with os.getenv if you prefer)
# ──────────────────────────────────────────
_API_KEY = "1jwUcSzw7IwGdusNjHmnmKfMuWpf4qg3"
_CLIENT  = Mistral(api_key=_API_KEY)


# ────────────────────────────────────
# 1.  Low-level JSON call helper
# ────────────────────────────────────
def _call_mistral_json(prompt: str,
                       model: str = "mistral-small-latest",
                       temperature: float = 0.0,
                       max_tokens: int = 1200) -> Any:
    """
    Send one prompt to Mistral Cloud with JSON output mode.
    Retries up to 3 times on server errors (e.g., 429s or 5XXs).
    """
    for attempt in range(3):
        try:
            resp = _CLIENT.chat.complete(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content

            # Try parsing JSON
            return json.loads(raw)

        except Exception as e:
            err_text = str(e)

            # Catch known rate limit / server capacity errors
            if "429" in err_text or "5XX" in err_text or "capacity exceeded" in err_text:
                wait_time = 2 ** attempt
                print(f"[WARN] API capacity error on attempt {attempt+1}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue  # retry
            else:
                print(f"[ERROR] Non-retryable error: {e}")
                raise RuntimeError(f"Mistral call failed: {e}")

    # If all attempts fail:
    raise RuntimeError("Mistral API failed after 3 attempts (likely due to rate limits or server issues)")

# ────────────────────────────────────
# 2.  Question-generation utilities
# ────────────────────────────────────
def _mcq_prompt(summary: str, n: int, asked: List[str]) -> str:
    omit = "\n".join(f"- {q}" for q in asked) if asked else "None"
    return f"""
You are an assistant that writes **multiple-choice questions (MCQ)**.

**Already asked – do NOT repeat**
{omit}

**TASK**
Write **exactly {n} new MCQs** about the *content* of the summary below.

**Output STRICTLY as a JSON array**.  
Each item must have:

{{
    "question": "...",
    "options": {{
      "A": "option-text",
      "B": "option-text",
      "C": "option-text",
      "D": "option-text"
    }},
    "correct": "A"
  }}


**SUMMARY**
\"\"\"{summary}\"\"\"
""".strip()


def generate_mcq(summary: str,
                 total_q: int = 20,
                 batch: int = 10,
                 temp: float = 0.0) -> List[Dict]:
    """
    Generate `total_q` non-repeating MCQs. One retry per batch.
    """
    all_q: List[Dict] = []
    while len(all_q) < total_q:
        need = min(batch, total_q - len(all_q))
        tried = False
        while True:
            prompt = _mcq_prompt(summary, need,
                                 [q["question"] for q in all_q])
            try:
                new = _call_mistral_json(prompt, temperature=temp)
                if not isinstance(new, list):
                    raise ValueError("Model did not return a list")
                all_q.extend(new)
                break
            except Exception as e:
                if tried:
                    raise RuntimeError("MCQ generation failed twice") from e
                tried = True
                time.sleep(1)
    return all_q


# ────────────────────────────────────
# 3.  Answer + score utilities
# ────────────────────────────────────
def _answer_mcq(questions: List[Dict],
                corpus: str,
                temp: float = 0.0,
                n: int = 3) -> List[str]:
    """
    Ask Mistral to answer MCQs based ONLY on `corpus`.
    Returns a list of answers in order.
    """
    q_only = [{"q": q["question"], "opt": q["options"]}
              for q in questions]

    prompt = f"""
You are answering multiple-choice questions.  
Base ALL answers solely on the corpus text.

**CORPUS**
\"\"\"{corpus}\"\"\"

Return a JSON array (same order) with answers, e.g.:
["A","B","C",...] only the letters are valid answers.

**QUESTIONS**
{json.dumps(q_only, ensure_ascii=False)}
""".strip()

    return _call_mistral_json(prompt, temperature=temp)


def _score_mcq(questions: List[Dict], answers: List[str]) -> int:
    return sum(1 for q, a in zip(questions, answers)
               if a == q["correct"])


# ────────────────────────────────────
# 4.  Public API
# ────────────────────────────────────
def evaluate_hallucination(summary: str,
                           corpus: str,
                           *,
                           total_q: int = 20,
                           iterations: int = 3,
                           temp_q: float = 0.0,
                           temp_a: float = 0.0) -> Dict[str, Any]:
    """
    MCQ-based hallucination check.

    Hallucination rate = 1 - (avg_correct / total_q)
    """
    # 1) generate once
    questions = generate_mcq(summary, total_q, temp=temp_q)

    # 2) answer N times
    total_correct = 0
    for _ in range(iterations):
        ans = _answer_mcq(questions, corpus, temp=temp_a)
        total_correct += _score_mcq(questions, ans)

    avg_correct = total_correct / iterations
    hall_rate   = 1 - (avg_correct / total_q)

    return {
        "hallucination_rate": hall_rate,
        "questions": total_q,
        "avg_correct": avg_correct,
        "iterations": iterations,
    }


# ────────────────────────────────────
# 5.  Convenience one-shot helper
# ────────────────────────────────────
def quick_hallucination(summary: str,
                         corpus: str,
                         q: int = 10) -> float:
    """Single generation + single answer pass."""
    res = evaluate_hallucination(summary, corpus,
                                 total_q=q, iterations=1)
    return res["hallucination_rate"]