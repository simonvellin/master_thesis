import requests
import json
import re
from jinja2 import Template

PROMPT_TEMPLATE = """You are a political analyst summarizing regional conflict data.

Country: {{ country }}
Region: {{ region }}
Month: {{ month }}

Quantitative:
- Number of events: {{ events }}
- Fatalities: {{ fatalities }}

Qualitative report:
{{ qualitative }}

Instructions:
Generate a short summary (2-3 sentences), a conflict intensity score (0 to 1), and a conflict trend compared to last month (-1 to 1).

Respond ONLY with valid JSON using the following fields:
{
  "summary": "...",
  "score": 0.5,
  "trend": 0.1
}
"""

def build_prompt(data):
    template = Template(PROMPT_TEMPLATE)
    return template.render(**data)

def query_mistral(prompt, model="tinydolphin"):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }
    )

    try:
        response_json = response.json()
    except ValueError:
        raise RuntimeError("Failed to parse response as JSON:\n" + response.text)

    if "response" not in response_json:
        raise RuntimeError("Unexpected response from Ollama:\n" + json.dumps(response_json, indent=2))

    return response_json["response"]

def summarize_region(country, region, month, events, fatalities, qualitative_text):
    context = {
        "country": country,
        "region": region,
        "month": month,
        "events": events,
        "fatalities": fatalities,
        "qualitative": qualitative_text
    }

    prompt = build_prompt(context)
    response_text = query_mistral(prompt)

    try:
        # Extract first JSON object from response using regex
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in response")

        response_json = json.loads(match.group())

        summary = response_json.get("summary", "")
        score = response_json.get("score", response_json.get("conflict_intensity", 0.0))
        trend = response_json.get("trend", response_json.get("conflict_trend", 0.0))

        return {
            "summary": summary,
            "score": float(score),
            "trend": float(trend)
        }

    except Exception as e:
        print("Could not decode response as JSON:")
        print(response_text)
        return None