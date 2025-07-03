# imports
from typing import Optional
import json
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.llm_summarization.llm_conversation import ask_llm
from app.data_ingestion.knowledge_graph import query_events
from app import config

EVENT_TYPES = config.EVENT_TYPES
COUNTRIES = config.COUNTRIES

# Function to build prompt from event data
def build_actor_prompt(bullets, tot_events, tot_fat, uniq_states, actor_name):
    prompt = f"""You are an analyst writing a conflict-early-warning brief.
Summarise key developments involving *{actor_name}* in Mexico, February 2025.

Context
-------
Total events : {tot_events}
Fatalities    : {tot_fat}
States        : {uniq_states}

Key events
----------
{bullets}

Task
----
Provide a concise summary. Cite Event IDs in parentheses.  Do **not** invent facts.
"""
    return prompt

# Function to build prompt to summarize events for a specific country, event type and month
def build_summary_prompt(country="Mexico", event_type="Protests", month=2, year=2025, bullets="", context="", max_words = 500):
    month_dict = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December"
    }

    if bullets == "" and context == "":
        prompt = ""
# ---------------------------------------------------------------------------------------
    elif bullets != "" and context == "":
        prompt   = f"""
You are an analyst writing a conflict-early-warning brief.
Summarise key developments of type {event_type} in {country}, {month_dict[month]} {year}.

Key events
----------
{bullets}

Task
----
Provide a concise summary (under {max_words} words). Cite Event IDs in parentheses. Do **not** invent facts.

Focus on the following aspects:
- Who was involved?
- What happened?
- When and where did it occur?
- What were the outcomes or impacts?

Use bullet points to list the key events and their impacts. Include a brief overview sentence that ties the summary to the broader context of conflict early warning. Ensure the summary is:
1. Accurate and factual: Do **not** invent or speculate about any information.
2. Well-structured: Follow a clear and logical format, using bullet points or short paragraphs.
3. Event-specific: Clearly mention the Event IDs in parentheses when referring to specific events.
"""
# ---------------------------------------------------------------------------------------
    elif bullets == "" and context != "":
        prompt   = f"""You are an analyst writing a conflict-early-warning brief.
Explain that there were no new events of type {event_type} in {country}, {month_dict[month]} {year}, but provide context.

Context
-------
Key developments in previous month : {context}



Task
----
Provide a concise summary (under {max_words} words). Cite Event IDs in parentheses.  Do **not** invent facts.
"""
# ---------------------------------------------------------------------------------------
    else:

        prompt = f"""
You are an analyst writing a conflict-early-warning brief.
Summarise key developments of type {event_type} in {country}, {month_dict[month]} {year}.

Context
-------
Key developments in previous month : {context}

Key events
----------
{bullets}

Task
----
Provide a concise summary (under {max_words} words). Cite Event IDs in parentheses. Do **not** invent facts.

Focus on the following aspects:
- Who was involved?
- What happened?
- When and where did it occur?
- What were the outcomes or impacts?
- How do these events relate to the previous month's context?

Use bullet points to list the key events and their impacts. Include a brief overview sentence that ties the summary to the broader context of conflict early warning. Ensure the summary is:
1. Accurate and factual: Do **not** invent or speculate about any information.
2. Well-structured: Follow a clear and logical format, using bullet points or short paragraphs.
3. Contextually aware: Incorporate relevant information from the previous month's context.
4. Event-specific: Clearly mention the Event IDs in parentheses when referring to specific events.
"""
    return prompt


# Function to summarize events using build_summary_prompt 
def summarize_events(
    uri,
    user,
    pwd,
    llm_provider="mistral",
    country="Mexico",
    state = None,
    event_type=None,
    month=2,
    year=2025,
    max_results=5000,
    context="",
    temperature=0.7,
    max_tokens=1000,
    max_words=500,
    override_prompt=None
):
    """
    Summarize events using a custom or template-based prompt.
    If `override_prompt` is passed, it will be used directly.
    """
    bullets, tot_events = query_events(
        uri=uri,
        user=user,
        pwd=pwd,
        year=year,
        month=month,
        country=country,
        state=state,
        event_type=event_type,
        max_results=max_results
    )

    print("✅ total events found:", tot_events)

    # Prompt logic
 #   prompt = override_prompt or build_summary_prompt(
 #       country=country,
 #       event_type=event_type,
 #       month=month,
 #       year=year,
 #       bullets=bullets,
 #       context=context
 #   )
    if override_prompt:
        prompt = override_prompt.format(
        bullets=bullets,
        context=context,
        country=country,
        state=state,
        event_type=event_type,
        month=month,
        year=year,
        max_words=max_words
    )
    else:
        prompt = build_summary_prompt(
        country=country,
        event_type=event_type,
        month=month,
        year=year,
        bullets=bullets,
        context=context,
        max_words=max_words
    )

    if not prompt.strip():
        return "No events found for the specified filters.", bullets

    # Query the LLM
    summary = ask_llm(
        prompt,
        provider=llm_provider,
        temperature=temperature,
        max_tokens=max_tokens
    )

    return summary, bullets



# Especific summarizer for overview type
def summarize_overview(
    sub_reports: dict[str, str],
    country: str, year: int, month: int,
    prev_overview: str = "",
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 600,
    max_words: int = 300
):
    """
    Weave event-type briefs into a single country overview.
    Returns (overview_text, missing_ids).
    """
    # 1) build the “inbox” of sub-reports with headings
    #order = [
    #    "Violence against civilians",
    #    "Protests",
    #    "Riots",
    #    "Battles",
    #   "Strategic developments"
    #]
    order = [et for et in EVENT_TYPES if et != "Overview"]
    block = "\n\n".join(
        f"### {et} ###\n{sub_reports[et].strip()}"
        for et in order if et in sub_reports
    )

    # 2) compose the meta‐prompt
    prompt = f"""SYSTEM
You are an analyst in a foreign agency writing a country-level conflict-early-warning brief.

USER
Below are five monthly summaries for {country} ({year}-{month:02d}), by event type:
{block}

PREVIOUS OVERVIEW (if any)
--------------------------
{prev_overview or 'N/A'}

TASK
----
Based solely on those five sections, write a concise **nation-wide** overview:
• Highlight cross-cutting themes and emerging risks.
• Do not restate each section heading—synthesise across them.
• Draw only on these summaries; do not introduce new facts.

GUIDELINES
* Keep it under {max_words} words.
* Structure it logically (e.g. by theme or phase).
* Cite any Event IDs you mention, using the same `ID=...` format.

BEGIN OVERVIEW →
"""

    # 3) call the LLM
    overview = ask_llm(
        prompt       = prompt,
        provider     = llm_provider,
        temperature  = temperature,
        max_tokens   = max_tokens
    )

 

    return overview

# Function to produce all summaries (types, overview) for a given country,month pair
def master_monthly_briefs(
    uri: str,
    user: str,
    pwd: str,
    country: str,
    year: int,
    month: int,
    include_context: bool = False,
    temperature: float = 0.3,
    max_tokens_et: int = 1000,
    max_tokens_ov: int = 800,
    max_words_ov: int = 300,
    max_words_et: int = 500,
    prev_event_briefs: Optional[dict[str, str]] = None,
    prev_overview: str = "",
    llm_provider: str = "mistral",
    max_results: int = 5000
) -> dict[str, str]:
    """
    Generate event-type summaries and an overview for a given country/month.
    
    Returns
    -------
    {
        "Violence against civilians":  ...,
        "Protests":                    ...,
        "Riots":                       ...,
        "Battles":                     ...,
        "Strategic developments":      ...,
        "Overview":                   ...
    }
    """
    event_types = [et for et in EVENT_TYPES if et != "Overview"]

    ctx_map = prev_event_briefs or {}
    get_ctx = (lambda et: ctx_map.get(et, "")) if include_context else (lambda _: "")

    summaries = {}

    for event_type in event_types:
        context = get_ctx(event_type)
        summary_text, _ = summarize_events(
            uri=uri,
            user=user,
            pwd=pwd,
            llm_provider=llm_provider,
            country=country,
            event_type=event_type,
            year=year,
            month=month,
            context=context,
            temperature=temperature,
            max_tokens=max_tokens_et,
            max_words=max_words_et,
            max_results=max_results
        )
        summaries[event_type] = summary_text

    overview = summarize_overview(
        sub_reports=summaries,
        country=country,
        year=year,
        month=month,
        prev_overview=prev_overview if include_context else "",
        llm_provider=llm_provider,
        temperature=temperature,
        max_tokens=max_tokens_ov,
        max_words=max_words_ov
    )

    summaries["Overview"] = overview
    return summaries


# global updater for a month (saves json to outputdir)
def update_all_summaries(
    uri: str,
    user: str,
    pwd: str,
    year: int,
    month: int,
    output_dir: str,
    include_context: bool = False,
    prev_context_map: Optional[dict[str, dict[str, str]]] = None,
    prev_overviews: Optional[dict[str, str]] = None,
    temperature: float = 0.3,
    max_tokens_et: int = 1000,
    max_tokens_ov: int = 800,
    max_words_ov: int = 300,
    max_words_et: int = 500,
    llm_provider: str = "mistral",
    progress=None,
    status_text=None,
    max_results_events: int = 5000
) -> dict[str, dict[str, str]]:
    """
    Generate summaries for all config.COUNTRIES for a given month and save them as a JSON file.
    Optionally displays Streamlit progress UI if `progress` and `status_text` are passed in.
    """
    results = {}
    COUNTRIES = config.COUNTRIES
    total = len(COUNTRIES)

    for i, country in enumerate(COUNTRIES):
        # Update status text
        if status_text:
            status_text.text(f"📡 Generating summaries for {country}...")

        country_prev_context = prev_context_map.get(country, {}) if prev_context_map else {}
        country_prev_overview = prev_overviews.get(country, "") if prev_overviews else ""

        try:
            summaries = master_monthly_briefs(
                uri=uri,
                user=user,
                pwd=pwd,
                country=country,
                year=year,
                month=month,
                include_context=include_context,
                prev_event_briefs=country_prev_context,
                prev_overview=country_prev_overview,
                temperature=temperature,
                max_tokens_et=max_tokens_et,
                max_tokens_ov=max_tokens_ov,
                max_words_et=max_words_et,
                max_words_ov=max_words_ov,
                llm_provider=llm_provider,
                max_results=max_results_events
            )
            results[country] = summaries
        except Exception as e:
            results[country] = {"error": str(e)}
            if status_text:
                status_text.text(f"❌ Failed to summarize {country}: {e}")
            else:
                print(f"❌ Failed to summarize {country}: {e}")

        # Update progress bar
        if progress:
            progress.progress((i + 1) / total)

    # Save to file
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"summaries_{year}_{month:02d}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if status_text:
        status_text.text(f"✅ Summaries saved to {output_path}")
    else:
        print(f"✅ Summaries saved to {output_path}")

    return results