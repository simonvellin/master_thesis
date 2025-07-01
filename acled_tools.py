# acled_tools.py  ── self-contained utility set
# Author: you                    Last edit: 2025-06-29
# ----------------------------------------------------------------------
import re, requests, ollama, pandas as pd
from textwrap import dedent
from neo4j import GraphDatabase

# ══════════════════════════════════════════════════════════════════════
# 1. ask_llm  – unified wrapper for Mistral API and local Ollama
# ══════════════════════════════════════════════════════════════════════
def ask_llm(prompt,
            provider="mistral",
            mistral_model="mistral-small-latest",
            ollama_model="tinydolphin",
            temperature=0.7,
            max_tokens=800,
            api_key="1jwUcSzw7IwGdusNjHmnmKfMuWpf4qg3",
            base_url="https://api.mistral.ai/v1/chat/completions",
            previous_messages=None):
    """Send `prompt` to either Mistral or local Ollama and return the reply."""
    messages = previous_messages[:] if previous_messages else []
    messages.append({"role": "user", "content": prompt})

    if provider == "ollama":
        resp = ollama.chat(model=ollama_model,
                           messages=messages,
                           options={"temperature": temperature})
        return resp["message"]["content"]

    if provider == "mistral":
        if not api_key:
            raise ValueError("Mistral provider requires api_key")
        payload = {
            "model": mistral_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        headers = {"Authorization": f"Bearer {api_key}",
                   "Content-Type": "application/json"}
        r = requests.post(base_url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    raise ValueError("provider must be 'mistral' or 'ollama'")


# ══════════════════════════════════════════════════════════════════════
# 2. month_metrics  – headline numbers for one slice
# ══════════════════════════════════════════════════════════════════════
def month_metrics(year, month, event_type, *,
                  country="Mexico",
                  uri, user, pwd):
    """Return (#events, fatalities, severity_sum) for a month/country/type."""
    q = """
    MATCH (e:Event)-[:TYPE]->(t:EventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year=$yr AND e.month=$mo
      AND s.country=$cty
      AND t.code=$etype
    RETURN count(e) AS n, coalesce(sum(e.fatalities),0) AS fat,
           coalesce(sum(e.severity_score),0) AS sev
    """
    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as s:
        rec = s.run(q, yr=year, mo=month, cty=country,
                    etype=event_type).single()
    return rec["n"], rec["fat"], rec["sev"]


# ══════════════════════════════════════════════════════════════════════
# 3. query_events  – fetch slice + build bullet list
# ══════════════════════════════════════════════════════════════════════
def query_events(uri, user, pwd,
                 year, month, country,
                 *, event_type=None, state=None,
                 max_results=500):
    """
    Return bullets (str), n_events, sev_by_state, sev_by_type, top10 DataFrames.
    Bullets format: one line per event, tagged as ID=XXXX for robust citation.
    """
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    ev_filt = "AND t.code = $etype" if event_type else ""
    st_filt = "AND s.admin1 = $state" if state else ""

    with driver.session() as s:
        # full rows (limited)
       
        q_events = f"""
        MATCH (e:Event)-[:TYPE]->(t:EventType),
            (e)-[:SUBTYPE]->(se:SubEventType),    // ← pull sub‐type
            (e)-[:IN_STATE]->(s:State)
        WHERE e.year=$yr AND e.month=$mo
        AND s.country=$cty {ev_filt} {st_filt}
        RETURN e.id          AS id,
            toString(e.date) AS date,
            s.admin1       AS state,
            se.code        AS subtype,          // ← new column
            t.code         AS type,
            e.fatalities   AS fat,
            e.severity_score AS sev,
            e.notes        AS note
        ORDER BY fat DESC, date ASC
        LIMIT $lim
        """
        df_events = pd.DataFrame(
            s.run(q_events, yr=year, mo=month, cty=country,
                  etype=event_type, state=state, lim=max_results).data()
        )

        # severity by state
        q_state = f"""
        MATCH (e:Event)-[:IN_STATE]->(s:State),
              (e)-[:TYPE]->(t:EventType)
        WHERE e.year=$yr AND e.month=$mo
          AND s.country=$cty {ev_filt} {st_filt}
        RETURN s.admin1 AS state,
               round(sum(e.severity_score),2) AS total_severity
        ORDER BY total_severity DESC
        """
        sev_by_state = pd.DataFrame(
            s.run(q_state, yr=year, mo=month, cty=country,
                  etype=event_type, state=state).data()
        )

        # severity by type
        q_type = q_state.replace("s.admin1 AS state", "t.code AS type")
        sev_by_type = pd.DataFrame(
            s.run(q_type, yr=year, mo=month, cty=country,
                  etype=event_type, state=state).data()
        )

        # top-10 most severe events
        q_top10 = q_events.replace("ORDER BY fat DESC, date ASC",
                                   "ORDER BY sev DESC")
        top10 = pd.DataFrame(
            s.run(q_top10, yr=year, mo=month, cty=country,
                  etype=event_type, state=state, lim=10).data()
        )

    driver.close()

    bullets = "\n".join(
        f"- ID: {r.id} | {r.state} | {r.subtype} | {r.note}"
        for r in df_events.itertuples()
    )
    return bullets, len(df_events), sev_by_state, sev_by_type, top10


# ══════════════════════════════════════════════════════════════════════
# 4. build_summary_prompt – assemble prompt from template
# ══════════════════════════════════════════════════════════════════════
# ───── overwrite PROMPT_TEMPLATES completely ───────────────────────
from textwrap import dedent

PROMPT_TEMPLATES = {           # ← new dict, old one is discarded

    "etype_general": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on {event_type} incidents
        across {country}.

        USER
        Using ONLY the events below and last month’s summary as context, write a
        concise brief that explains

        • The overall developments of {event_type} this month  
        • Key actors involved and their roles
        • Hotspot areas 
        • How this month compares with last month

        DATA (this month)
        -----------------
        {events_block}

        PREVIOUS-MONTH SUMMARY 
        --------------------------------
        {context_block}

        GUIDELINES
        * Organise logically.
        * Cite Event IDs for every claim you make;  (e.g., MEX102349).
        * Only cite IDs that appear in the DATA block.
        * Do not invent facts; if you cannot find a fact in the data, do not mention it.
    

        BEGIN BRIEF →
    """).lstrip(),

    "etype_contextfirst": dedent("""
        SYSTEM
        You are a conflict-analysis assistant.  The audience is humanitarian
        protection officers and security analysts tracking {event_type} incidents
        across {country}.

        USER
        Using ONLY the material below, write a concise brief that explains

        • The overall pattern of {event_type} this month  
        • Key actors and any changes in tactics or targets  
        • Hotspot areas and how they compare with last month  
        • Indicators that matter for early warning  

        PREVIOUS-MONTH SUMMARY (if any)
        --------------------------------
        {context_block}

        DATA (this month)
        -----------------
        {events_block}

        GUIDELINES
        * Focus on patterns specific to {event_type}; mention single events only
          when illustrative.  
        * Organise logically.  
        * Cite Event IDs in parentheses for every claim; do **not** invent facts.

        BEGIN BRIEF →
    """).lstrip(),

"etype": dedent("""
        SYSTEM
        You are a conflict-analysis assistant.  Your task is to brief humanitarian
        protection officers and security analysts on **{event_type}** in **{country}**.

        USER
        Using ONLY the information provided below, produce a concise, well-structured
        brief that answers four questions:

        1.  **What happened?**  – overall scale and salient developments this month
        2.  **Who was involved?**  – main perpetrator / target groups and any shift in
            tactics
        3.  **Where?**  – hotspot states or municipalities and how they compare with
            last month
        4.  **So what?**  – early-warning signals or implications for the next month

        PREVIOUS-MONTH SUMMARY  (read for trend comparison – do not cite its IDs)
        -----------------------------------------------------------------------
        {context_block}

        HEADLINE METRICS  (current month)
        ---------------------------------
        {metrics_block}
            # examples: “Events 524 | Fatalities 572 | Severity 39 708.6 | Δ +8 % vs Mar”

        EVENT LOG  (current month – each line is one event)
        ---------------------------------------------------
        {events_block}
            # format:  “ID: MEX102349 | 2025-04-14 | Guanajuato | 5 fat | violence against civilians | note ...”

        GUIDELINES
        * Organise logically.
        * Cite Event IDs for every claim you make; (e.g., MEX102349).
        * Only cite IDs that appear in the DATA block.
        * Do not invent facts; if you cannot find a fact in the data, do not mention it.
    

        BEGIN BRIEF →
    """).lstrip(),

    "etype2": dedent("""
        SYSTEM
        You are an analyst who writes concise, factual situation briefs.

        USER
        Using only the material below, produce a brief that

        • summarises the overall situation this month  
        • highlights the key developments (actors, themes, locations)  
        • explains clearly how this month differs from last month  
        • compare to last nonth anchors any trend statements to the headline figures provided

        Cite Event IDs in parentheses when you reference a specific incident.  
        Do **not** invent information.

        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}
            # e.g. “Events 524 | Fatalities 572 | Severity 39 708.6 | Δ +8 % vs Mar”

        LAST-MONTH RECAP
        ----------------
        {context_block}

        EVENT LOG  – current month
        --------------------------
        {events_block}

        BEGIN BRIEF →
    """).lstrip(),

    "etype_no_context": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on {event_type} incidents
        across {country}.


        USER
        Using only the material below, produce a concise brief that

        • summarises the overall situation this month  
        • highlights the key developments (actors, themes, locations)  

        Cite Event IDs in parentheses to support all claims made.  
        Do **not** invent information.

        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}
            # e.g. “Events 524 | Fatalities 572 | Severity 39 708.6 | Δ +8 % vs Mar”


        EVENT LOG  – current month
        --------------------------
        {events_block}

        BEGIN BRIEF →
    """).lstrip(),

# Event-type specific templates, NO CONTEXT  ──────────────────────────────

    "vac" : dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on the section **Violence against civilians** across {country}.

        USER
        Using only the material below, produce a concise brief that

        • summarises the overall pattern of violence against civilians this month  
        • highlights key developments (actors, tactics, locations)  
        • goes into more detail on the **sub-event types**  
        – Sexual violence  
        – Attack  
        – Abduction/forced disappearance  
        when they are significant this month

        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}

        EVENT LOG  – current month
        --------------------------
        {events_block}

        GUIDELINES
        * Focus on trends and patterns; mention individual events only when illustrative.  
        * Cite Event IDs in parentheses to support all claims.  
        * Do **not** invent information.

        BEGIN BRIEF →
    """).lstrip(),

    "protests": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on the section **Protests** across {country}.

        USER
        Using only the material below, produce a concise brief that

        • summarises the overall protest situation this month  
        • highlights the key developments (themes, groups, locations)
        • goes into more detail on the **non-peaceful** sub-types (Protest with intervention & Excessive force against protesters) if there are any this month


        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}

        EVENT LOG  – current month
        --------------------------
        {events_block}
    
        GUIDELINES
        * Focus on summarising the events, do not make any broader context interpretations.
        * Cite Event IDs in parentheses to support all claims made. 
        * Do **not** invent information.

        BEGIN BRIEF →
    """).lstrip(),

    "strategic": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on the section **Strategic developments** across {country} .

        USER
        Using only the material below, produce a concise briefing that:
        • Summarises the overall strategic-developments this month  
        • goes into more detail on the different types of strategic developments depending on their significance this month
                        
        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}

        EVENT LOG  – current month
        --------------------------
        {events_block}
        
        GUIDELINES
        * Focus on summarising the events, do not make any broader context interpretations.
        * Cite Event IDs in parentheses to support all claims made. 
        * Do **not** invent information.
        

        BEGIN BRIEF →
    """).lstrip(),

    "riots": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on the section **Riots** across {country}.

        USER
        Using only the material below, produce a concise brief that

        • summarises the overall riot situation this month  
        • highlights the key developments (themes, groups, locations)  
        • goes into more detail on the sub-types (Violent demonstration & Mob violence) 

        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}

        EVENT LOG  – current month
        --------------------------
        {events_block}
                
        GUIDELINES
        * Focus on summarising the events, do not make any broader context interpretations.
        * Cite Event IDs in parentheses to support all claims made. 
        * Do **not** invent information.

        BEGIN BRIEF →
    """).lstrip(),

    "battles": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict-early-warning brief on the section **Battles** across {country}.

        USER
        Using only the material below, produce a concise brief that

        • summarises the overall battles situation this month  
        • highlights the key developments (themes, groups, locations) 
        

        HEADLINE FIGURES  – current month
        ---------------------------------
        {metrics_block}

        EVENT LOG  – current month
        --------------------------
        {events_block}
        
        GUIDELINES
        * Focus on summarising the events, do not make any broader context interpretations.
        * Cite Event IDs in parentheses to support all claims made. 
        * Do **not** invent information.


        BEGIN BRIEF →
    """).lstrip(),

# Event-type specific templates, WITH CONTEXT ──────────────────────────

    "vac_with_context": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict‐early‐warning brief on the section **Violence against civilians** across {country}.

        USER
        Using ONLY the events from this month and last month’s summary as context, write a concise brief that:

        • Summarises the overall pattern of violence against civilians this month  
        • Highlights notable hanges since last month (trends, increases/decreases, new hotspots) (if any)
        • Profiles the three sub‐types (Sexual violence, Attack, Abduction/forced disappearance) and notes significant shifts (if any)
    

        PREVIOUS‐MONTH SUMMARY
        ----------------------
        {context_block}

        DATA (this month)
        -----------------
        {events_block}

        GUIDELINES
        * Cite Event IDs in parentheses for every specific claim.
        * Do NOT invent facts; stick strictly to the provided material.

        BEGIN BRIEF →
    """).lstrip(),

    "protests_with_context": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict‐early‐warning brief on the section **Protests** across {country}.

        USER
        Using ONLY the events from this month and last month’s summary as context, write a concise brief that:

        • Summarises the overall protest landscape this month  
        • highlights the key developments (themes, groups, locations) and notes any significant changes since last month ( if any)
        • Dives deeper into the non‐peaceful sub‐types (Protest with intervention & Excessive force against protesters) and notes significant shifts (if any) 
        

        PREVIOUS‐MONTH SUMMARY
        ----------------------
        {context_block}

        DATA (this month)
        -----------------
        {events_block}

        GUIDELINES
        * Cite Event IDs in parentheses for every specific claim made.
        * Do NOT invent or extrapolate beyond the data.

        BEGIN BRIEF →
    """).lstrip(),

    "riots_with_context": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict‐early‐warning brief on the section **Riots** across {country}.

        USER
        Using ONLY this month’s events and last month’s summary as context, write a concise brief that:

        • Summarises the overall riot situation this month  
        • highlights the key developments (themes, groups, locations) and notes any significant changes since last month (if any) 
        • goes into more detail on the sub-types (Violent demonstration & Mob violence) and notes significant shifts (if any) 

        PREVIOUS‐MONTH SUMMARY
        ----------------------
        {context_block}

        DATA (this month)
        -----------------
        {events_block}

        GUIDELINES
        * Cite Event IDs in parentheses for every specific claim made.
        * Do NOT invent or extrapolate beyond the data.

        BEGIN BRIEF →
    """).lstrip(),

    "battles_with_context": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict‐early‐warning brief on the section **Battles** across {country}.

        USER
        Using ONLY this month’s events and last month’s summary as context, write a concise brief that:

       • summarises the overall battles situation this month and notes any significant changes since last month (if any) 
       • highlights the key developments (themes, groups, locations) and notes significant shifts (if any) 
        

        PREVIOUS‐MONTH SUMMARY
        ----------------------
        {context_block}

        DATA (this month)
        -----------------
        {events_block}

        GUIDELINES
        * Cite Event IDs in parentheses for all specific claims made.
        * Do NOT invent or extrapolate beyond the data.

        BEGIN BRIEF →
    """).lstrip(),

    "strategic_with_context": dedent("""
        SYSTEM
        You are an analyst in a foreign agency writing a conflict‐early‐warning brief on **Strategic developments** across {country}.

        USER
        Using ONLY this month’s events and last month’s summary as context, write a concise brief that:

        • Summarises the overall strategic developments this month and notes any significant changes since last month (if any)
        • goes into more detail on the different types of strategic developments depending on their significance this month

        PREVIOUS‐MONTH SUMMARY
        ----------------------
        {context_block}

        DATA (this month)
        -----------------
        {events_block}

        GUIDELINES
        * Cite Event IDs in parentheses for all specific claims made.
        * Do NOT invent or extrapolate beyond the data.

        BEGIN BRIEF →
    """).lstrip(),

# state-specific templates, WITH CONTEXT ──────────────────────────────

    "overview_general": dedent("""
        SYSTEM
        You are a conflict-analysis assistant. Your audience is humanitarian
        planners, diplomats and journalists who need a quick sense of the
        nation-wide situation.

        USER
        Use ONLY the events listed below and (if present) last month’s summary.
        Write a concise brief that explains
        • The general security situation in {country} this month
        • Which actors or regions stand out and why
        • How this month compares with last month
        • Themes or patterns relevant for early warning

        DATA (this month)
        -----------------
        {events_block}

        PREVIOUS-MONTH SUMMARY (if any)
        --------------------------------
        {context_block}

        GUIDELINES
        * Focus on trends; mention single events only when illustrative.
        * Organise logically (format is your choice).
        * Cite Event IDs in parentheses; do **not** invent facts.

        BEGIN BRIEF →
    """).lstrip(),

    "state_general": dedent("""
        SYSTEM
        You are a conflict-analysis assistant. Audience: field teams and regional
        analysts in {state}, {country}.

        USER
        Using ONLY the events below and (if present) last month’s summaries,
        write a concise brief that explains
        • The security situation in {state} this month
        • Main local actors and their behaviour
        • How {state} compares with the national picture and last month
        • Themes or patterns that matter for early warning in this state

        DATA (this month)
        -----------------
        {events_block}

        PREVIOUS-MONTH CONTEXT (may include national overview)
        -------------------------------------------------------
        {context_block}

        GUIDELINES
        * Emphasise state-level trends.
        * Mention single events only when illustrative.
        * Cite Event IDs in parentheses; do **not** invent facts.

        BEGIN BRIEF →
    """).lstrip()
}

def build_summary_prompt(country, event_type, month, year,
                         *, bullets="", context="", metrics_block="",
                         state=None, style="etype_contextfirst",
                         template=None):
    """Return the prompt string ready for LLM."""
    month_name = ["January","February","March","April","May","June",
                  "July","August","September","October","November","December"][month-1]
    loc_line = f"{state}, {country}" if state else country
    tpl = template or PROMPT_TEMPLATES[style]
    return tpl.format(
        country= country,
        event_type=event_type or "all events",
        loc_line=loc_line,
        month_name=month_name,
        year=year,
        context_block=context or "N/A",
        metrics_block=metrics_block or "N/A",
        events_block=bullets or "N/A"
    )


# ══════════════════════════════════════════════════════════════════════
# 5. summarize_events – high-level orchestrator
# ══════════════════════════════════════════════════════════════════════
def summarize_events(uri, user, pwd,
                     *, country, month, year,
                     event_type=None, state=None,
                     context="", metrics_block="",
                     style="etype_contextfirst",
                     llm_provider="mistral",
                     temperature=0.4, max_tokens=800,
                     max_results=400):
    """Generate summary + return bullet list."""
    bullets, _, *_ = query_events(
        uri, user, pwd,
        year, month, country,
        event_type=event_type, state=state,
        max_results=max_results
    )
    prompt = build_summary_prompt(
        country, event_type, month, year,
        bullets=bullets, context=context,
        metrics_block=metrics_block,
        state=state, style=style
    )
    summary = ask_llm(prompt, provider=llm_provider,
                      temperature=temperature, max_tokens=max_tokens)
    return summary, bullets


# ══════════════════════════════════════════════════════════════════════
# 6. verify_citations – existence check (optional type / state filters)
# ══════════════════════════════════════════════════════════════════════
_ID_RX = re.compile(r'\b([A-Z]{2,}[0-9]{2,})\b')

def verify_citations(summary_text, uri, user, pwd,
                     *, year, month, country,
                     event_type: str | None = None,
                     state: str | None = None):
    """
    Check that every Event-ID cited in `summary_text` exists in the Neo4j slice
    defined by (year, month, country [, event_type] [, state]).

    Parameters
    ----------
    summary_text : str
        LLM output containing citations like `ID=MEX102349` or `(MEX102349)`.
    uri, user, pwd : Neo4j credentials
    year, month, country : int, int, str  – slice key
    event_type : str  – optional ACLED event_type filter
    state      : str  – optional admin1 filter

    Returns
    -------
    list[str]  – IDs that were cited but not found in the slice.

    Note
    ----
    IDs that appear **only** in the “PREVIOUS-MONTH SUMMARY” block are skipped.
    """
    # -- 1. ignore context block to avoid previous-month IDs --
    if "DATA (this month)" in summary_text:
        summary_text = summary_text.split("DATA (this month)", 1)[1]

    cited_ids = set(_ID_RX.findall(summary_text))

    # -- 2. build Cypher filters --
    et_filter = "AND t.code = $etype"   if event_type else ""
    st_filter = "AND s.admin1 = $state" if state      else ""

    cypher = f"""
    MATCH (e:Event)-[:TYPE]->(t:EventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year=$yr AND e.month=$mo
      AND s.country=$cty
      {et_filter} {st_filter}
    RETURN toString(e.id) AS id
    """

    params = {"yr": year, "mo": month, "cty": country}
    if event_type: params["etype"] = event_type
    if state:      params["state"] = state

    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as sess:
        valid_ids = {rec["id"] for rec in sess.run(cypher, **params)}

    missing = sorted(cited_ids - valid_ids)
    print(f"Cited IDs : {len(cited_ids)}  •  Matched : {len(cited_ids)-len(missing)}")
    if missing:
        print("⚠️  missing IDs ➜", ", ".join(missing))
    else:
        print("✅ all cited IDs present in slice.")
    return missing


# ══════════════════════════════════════════════════════════════════════
# 7. id_month – debug utility
# ══════════════════════════════════════════════════════════════════════
def id_month(uri, user, pwd, event_id):
    """Return (year, month) for a given Event ID, or None."""
    q = "MATCH (e:Event {id:$eid}) RETURN e.year AS y, e.month AS m"
    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as s:
        rec = s.run(q, eid=str(event_id)).single()
        return (rec["y"], rec["m"]) if rec else None


# ----------------------------------------------------------------------
__all__ = [
    "ask_llm", "month_metrics", "query_events", "build_summary_prompt",
    "summarize_events", "verify_citations", "id_month"
]
## ----------------------------------------------------------------------
def protest_metrics(uri, user, pwd, year, month, country):
    """
    Returns a tuple:
       total_events, total_fatalities,
       n_peaceful, n_intervention, n_excessive
    for Protests in the given year/month/country.
    """
    q = """
    MATCH (e:Event)-[:TYPE]->(t:EventType),
          (e)-[:SUBTYPE]->(se:SubEventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year  = $yr
      AND e.month = $mo
      AND s.country = $cty
      AND t.code   = 'Protests'
    RETURN se.code       AS subtype,
           count(e)       AS cnt,
           sum(e.fatalities) AS fat
    """
    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as sess:
        recs = sess.run(q, yr=year, mo=month, cty=country).data()

    # aggregate
    total_events     = 0
    total_fatalities = 0
    counts = {"Peaceful protest": 0,
              "Protest with intervention": 0,
              "Excessive force against protesters": 0}

    for r in recs:
        subtype = r["subtype"]
        cnt     = r["cnt"] or 0
        fat     = r["fat"] or 0
        total_events     += cnt
        total_fatalities += fat
        if subtype in counts:
            counts[subtype] = cnt

    n_peaceful     = counts["Peaceful protest"]
    n_intervention = counts["Protest with intervention"]
    n_excessive    = counts["Excessive force against protesters"]

    return total_events, total_fatalities, n_peaceful, n_intervention, n_excessive

# ══════════════════════════════════════════════════════════════════════
def riot_metrics(uri: str, user: str, pwd: str,
                 year: int, month: int, country: str):
    """
    Compute headline metrics for the 'Riots' event type in a given slice.

    Returns:
        total_events (int): Total number of Riots events.
        events_by_subtype (dict): { sub_event_type: count }
        fatalities_by_subtype (dict): { sub_event_type: total_fatalities }
    """
    cypher = """
    MATCH (e:Event)-[:TYPE]->(t:EventType {code:"Riots"}),
          (e)-[:SUBTYPE]->(se:SubEventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year   = $yr
      AND e.month  = $mo
      AND s.country= $cty
    RETURN se.code            AS subtype,
           count(e)           AS cnt,
           coalesce(sum(e.fatalities), 0) AS fat
    """
    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as sess:
        records = sess.run(cypher, yr=year, mo=month, cty=country).data()

    total_events = 0
    events_by_subtype = {}
    fatalities_by_subtype = {}

    for rec in records:
        st = rec["subtype"]
        cnt = rec["cnt"] or 0
        fat = rec["fat"] or 0
        total_events += cnt
        events_by_subtype[st] = cnt
        fatalities_by_subtype[st] = fat

    return total_events, events_by_subtype, fatalities_by_subtype

# ══════════════════════════════════════════════════════════════════════
def battle_metrics(uri: str, user: str, pwd: str,
                   year: int, month: int, country: str):
    """
    Returns:
      total_events (int),
      events_by_subtype (dict: subtype → count),
      fatalities_by_subtype (dict: subtype → sum of fatalities)
    for Battles in the given slice.
    """
    cypher = """
    MATCH (e:Event)-[:TYPE]->(t:EventType {code:"Battles"}),
          (e)-[:SUBTYPE]->(se:SubEventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year   = $yr
      AND e.month  = $mo
      AND s.country= $cty
    RETURN se.code            AS subtype,
           count(e)           AS cnt,
           coalesce(sum(e.fatalities),0) AS fat
    """
    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as sess:
        recs = sess.run(cypher, yr=year, mo=month, cty=country).data()

    total = sum(r["cnt"] for r in recs)
    by_cnt = {r["subtype"]: r["cnt"] for r in recs}
    by_fat = {r["subtype"]: r["fat"] for r in recs}
    # ensure all three subtypes are present
    for st in ("Armed clash", "Government regains territory", "Non-state actor overtakes territory"):
        by_cnt.setdefault(st, 0)
        by_fat.setdefault(st, 0)

    return total, by_cnt, by_fat

# ══════════════════════════════════════════════════════════════════════
def vac_metrics(
    uri: str,
    user: str,
    pwd: str,
    year: int,
    month: int,
    country: str
) -> tuple[int, int, dict[str,int], dict[str,int]]:
    """
    Compute headline metrics for the 'Violence against civilians' event type.

    Returns:
      total_events (int),
      total_fatalities (int),
      events_by_subtype (dict: subtype → count),
      fatalities_by_subtype (dict: subtype → sum of fatalities)
    for the given year/month/country slice.
    """
    cypher = """
    MATCH (e:Event)-[:TYPE]->(t:EventType {code:"Violence against civilians"}),
          (e)-[:SUBTYPE]->(se:SubEventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year   = $yr
      AND e.month  = $mo
      AND s.country= $cty
    RETURN se.code           AS subtype,
           count(e)          AS cnt,
           coalesce(sum(e.fatalities), 0) AS fat
    """
    with GraphDatabase.driver(uri, auth=(user, pwd)).session() as sess:
        recs = sess.run(cypher, yr=year, mo=month, cty=country).data()

    total_events = 0
    total_fatalities = 0
    events_by_subtype = {}
    

    for r in recs:
        st = r["subtype"]
        cnt = r["cnt"] or 0
        fat = r["fat"] or 0
        total_events += cnt
        total_fatalities += fat
        events_by_subtype[st] = cnt
        

    # ensure all known subtypes appear, even if zero
    for st in ("Sexual violence", "Attack", "Abduction/forced disappearance"):
        events_by_subtype.setdefault(st, 0)
        

    return total_events, total_fatalities, events_by_subtype

# ─────────────────────────────────────────────────────────────────────
# 8. wrapper functions for each event‐type
# ─────────────────────────────────────────────────────────────────────

def summarize_riots(
    uri: str, user: str, pwd: str,
    country: str, year: int, month: int,
    context: str = "",
    check_citations: bool = False,
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 800,
    max_results: int = 400
):
    """
    Generate a RIOTS brief + optional citation check. Automatically picks
    the context‐aware template if you passed a non‐empty context.
    """
    # pick the style based on whether context was provided:
    style_key = "riots_with_context" if context else "riots"

    # get metrics for the given slice
    total, ev_by_sub, fat_by_sub = riot_metrics(uri, user, pwd, year, month, country)

    metrics = (
        f"Total riots: {total}  |  "
        f"Violent demonstration: {ev_by_sub.get('Violent demonstration',0)} "
        f"({fat_by_sub.get('Violent demonstration',0)} fat.)  |  "
        f"Mob violence: {ev_by_sub.get('Mob violence',0)} "
        f"({fat_by_sub.get('Mob violence',0)} fat.)"
    )

    summary, bullets = summarize_events(
        uri, user, pwd,
        country=country, month=month, year=year,
        event_type="Riots", context=context,
        metrics_block=metrics, style=style_key,
        llm_provider=llm_provider,
        temperature=temperature, max_tokens=max_tokens,
        max_results=max_results
    )

    missing = []
    if check_citations:
        missing = verify_citations(
            summary_text=summary,
            uri=uri, user=user, pwd=pwd,
            year=year, month=month,
            country=country, event_type="Riots"
        )
    return summary, bullets, missing


def summarize_protests(
    uri: str, user: str, pwd: str,
    country: str, year: int, month: int,
    context: str = "",
    check_citations: bool = False,
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 800,
    max_results: int = 400
):
    """Generate a PROTESTS brief + optional citation check.
    Automatically picks the context-aware template if you passed a non-empty context.
    """
    # pick the style based on whether context was provided:
    style_key= "protests_with_context" if context else "protests"
    
    # get metrics for the given slice
    total, fatalities, n_peace, n_inter, n_excess = protest_metrics(
        uri, user, pwd, year, month, country
    )
    metrics = (
        f"Total protests: {total}  |  "
        f"Peaceful: {n_peace}  |  "
        f"Intervention: {n_inter}  |  "
        f"Excessive force: {n_excess}  |  "
        f"Fatalities: {fatalities}"
    )

    summary, bullets = summarize_events(
        uri, user, pwd,
        country=country, month=month, year=year,
        event_type="Protests", context=context,
        metrics_block=metrics, style=style_key,
        llm_provider=llm_provider,
        temperature=temperature, max_tokens=max_tokens,
        max_results=max_results
    )

    missing = []
    if check_citations:
        missing = verify_citations(
            summary_text=summary,
            uri=uri, user=user, pwd=pwd,
            year=year, month=month,
            country=country, event_type="Protests"
        )
    return summary, bullets, missing


def summarize_battles(
    uri: str, user: str, pwd: str,
    country: str, year: int, month: int,
    context: str = "",
    check_citations: bool = False,
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 800,
    max_results: int = 400
):
    """ Generate a BATTLES brief + optional citation check.
    Automatically picks the context-aware template if you passed a non-empty context.
    """
    # pick the style based on whether context was provided:
    style_key = "battles_with_context" if context else "battles"

    # get metrics for the given slice
    total, ev_by_sub, fat_by_sub = battle_metrics(
        uri, user, pwd, year, month, country
    )
    # build a simple metrics line
    parts = [f"{st}: {cnt} ({fat_by_sub[st]} fat.)" for st, cnt in ev_by_sub.items()]
    metrics = f"Total battles: {total}  |  " + "  |  ".join(parts)

    summary, bullets = summarize_events(
        uri, user, pwd,
        country=country, month=month, year=year,
        event_type="Battles", context=context,
        metrics_block=metrics, style=style_key,
        llm_provider=llm_provider,
        temperature=temperature, max_tokens=max_tokens,
        max_results=max_results
    )

    missing = []
    if check_citations:
        missing = verify_citations(
            summary_text=summary,
            uri=uri, user=user, pwd=pwd,
            year=year, month=month,
            country=country, event_type="Battles"
        )
    return summary, bullets, missing


def summarize_strategic(
    uri: str, user: str, pwd: str,
    country: str, year: int, month: int,
    context: str = "",
    check_citations: bool = False,
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 800,
    max_results: int = 400
):
    """Generate a STRATEGIC DEVELOPMENTS brief + optional citation check.
    Automatically picks the context-aware template if you passed a non-empty context.
    """

    # pick the style based on whether context was provided:
    style_key = "strategic_with_context" if context else "strategic"

    # reuse query_events to get bullets, then aggregate subtypes manually
    bullets, n, sev_by_state, sev_by_type, top10 = query_events(
        uri, user, pwd,
        year, month, country,
        event_type="Strategic developments", max_results=max_results
    )
    # subtype totals from sev_by_type (renamed for strategic)
    parts = [f"{row['type']}: {int(row['total_severity'])}" for _, row in sev_by_type.iterrows()]
    metrics = f"Total events: {n}  |  " + "  |  ".join(parts)

    summary, _ = summarize_events(
        uri, user, pwd,
        country=country, month=month, year=year,
        event_type="Strategic developments", context=context,
        metrics_block=metrics, style=style_key,
        llm_provider=llm_provider,
        temperature=temperature, max_tokens=max_tokens,
        max_results=max_results
    )

    missing = []
    if check_citations:
        missing = verify_citations(
            summary_text=summary,
            uri=uri, user=user, pwd=pwd,
            year=year, month=month,
            country=country, event_type="Strategic developments"
        )
    return summary, bullets, missing

def summarize_vac(
    uri: str, user: str, pwd: str,
    country: str, year: int, month: int,
    context: str = "",
    check_citations: bool = False,
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 800,
    max_results: int = 400
):
    """Generate a VIOLENCE AGAINST CIVILIANS brief + optional citation check.
    Automatically picks the context-aware template if you passed a non-empty context.
    """

    # pick the style based on whether context was provided:
    style_key = "vac_with_context" if context else "vac"
    
    # 1) compute detailed VAC metrics
    n, fat, ev_by_sub = vac_metrics(
        uri, user, pwd, year, month, country
    )

    # 2) format the metrics line
    metrics = (
        f"Total events: {n}  |  "
        f"Fatalities: {fat}  |  "
        f"Sexual violence: {ev_by_sub['Sexual violence']}  |  "
        f"Attack: {ev_by_sub['Attack']}  |  "
        f"Abduction/forced disappearance: {ev_by_sub['Abduction/forced disappearance']} "
        
    )

    # 3) call the generic summarizer
    summary, bullets = summarize_events(
        uri, user, pwd,
        country        = country,
        year           = year,
        month          = month,
        event_type     = "Violence against civilians",
        context        = context,
        metrics_block  = metrics,
        style          = style_key,
        llm_provider   = llm_provider,
        temperature    = temperature,
        max_tokens     = max_tokens,
        max_results    = max_results
    )

    # 4) optional citation check
    missing = []
    if check_citations:
        missing = verify_citations(
            summary_text = summary,
            uri          = uri,
            user         = user,
            pwd          = pwd,
            year         = year,
            month        = month,
            country      = country,
            event_type   = "Violence against civilians"
        )

    return summary, bullets, missing

# ══════════════════════════════════════════════════════════════════════
def summarize_overview(
    uri: str, user: str, pwd: str,
    sub_reports: dict[str, str],
    country: str, year: int, month: int,
    prev_overview: str = "",
    check_citations: bool = False,
    llm_provider: str = "mistral",
    temperature: float = 0.4,
    max_tokens: int = 600
) -> tuple[str, list[str]]:
    """
    Weave event-type briefs into a single country overview.
    Returns (overview_text, missing_ids).
    """
    # 1) build the “inbox” of sub-reports with headings
    order = [
        "Violence against civilians",
        "Protests",
        "Riots",
        "Battles",
        "Strategic developments"
    ]
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
* Keep it under 300 words.
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

    missing = []
    if check_citations:
        # We verify against the full country slice
        missing = verify_citations(
            summary_text=overview,
            uri=uri, user=user, pwd=pwd,
            year=year, month=month, country=country
        )

    return overview, missing

# ─────────────────────────────────────────────────────────────────────
#  master_monthly_briefs  – one call → five event-type briefs (+ overview)
# ─────────────────────────────────────────────────────────────────────
from typing import Optional

def master_monthly_briefs(
    *,                                           # ← all args are keyword-only
    uri: str,
    user: str,
    pwd: str,
    country: str,
    year: int,
    month: int,
    # --- behaviour toggles ------------------------------------------------
    include_context: bool = False,               # pass previous-month briefs
    check_citations: bool = False,               # run verify_citations()
    temperature: float = 0.3,
    max_tokens_et: int = 1000,                    # per-event-type
    max_tokens_ov: int = 800,                    # overview
    # --- if you *do* want context, provide the two stores below ------------
    prev_event_briefs: Optional[dict[str, str]] = None,
    prev_overview: str = ""
):
    """
    Generate the five standard event-type summaries **and** the country overview
    for the requested slice → return them in a single dict.

    Returns
    -------
    {
        "Violence against civilians":  summary_text,
        "Protests":                    summary_text,
        "Riots":                       summary_text,
        "Battles":                     summary_text,
        "Strategic developments":      summary_text,
        "_overview":                   overview_text
    }
    (If `check_citations=True`, each item is a tuple
       (summary_text, missing_ids_list) instead.)
    """
    # ------------------------------------------------------------------ #
    # 1) decide which context (if any) to pass into each event-type call
    # ------------------------------------------------------------------ #
    ctx_map = prev_event_briefs or {}
    get_ctx = (lambda et: ctx_map.get(et, "")) if include_context else (lambda _ : "")

    # ------------------------------------------------------------------ #
    # 2) generate the five event-type briefs
    # ------------------------------------------------------------------ #
    summaries   = {}
    wrappers = [
        ("Violence against civilians", summarize_vac),
        ("Protests",                   summarize_protests),
        ("Riots",                      summarize_riots),
        ("Battles",                    summarize_battles),
        ("Strategic developments",     summarize_strategic),
    ]

    for et, fn in wrappers:
        summ, _, missing = fn(
            uri=uri, user=user, pwd=pwd,
            country=country, year=year, month=month,
            context=get_ctx(et),
            check_citations=check_citations,
            temperature=temperature, max_tokens=max_tokens_et
        )
        summaries[et] = (summ, missing) if check_citations else summ

    # ------------------------------------------------------------------ #
    # 3) build the overview
    # ------------------------------------------------------------------ #
    ov, missing_ov = summarize_overview(
        uri=uri, user=user, pwd=pwd,
        sub_reports={k: (v[0] if check_citations else v)
                     for k, v in summaries.items()},
        country=country, year=year, month=month,
        prev_overview=prev_overview if include_context else "",
        check_citations=check_citations,
        temperature=temperature, max_tokens=max_tokens_ov
    )
    summaries["_overview"] = (ov, missing_ov) if check_citations else ov

    return summaries

    # Example: Mexico, March 2025 – with previous context & citation checks
    # prev_briefs   = {...}       # ← dict from February if you have it
    # prev_overview = "..."       # ← February overview

    #bundle = at.master_monthly_briefs(
    #uri=URI, user=USER, pwd=PWD,
    #country="Mexico", year=2025, month=3,
    #include_context=True,
    #check_citations=True, 
    #prev_event_briefs=prev_briefs, # default: None
    #prev_overview=prev_overview,    # default: ""
    #)

    # Access items
    #vac_summary, vac_missing = bundle["Violence against civilians"]
    #overview,  ov_missing    = bundle["_overview"]

# ══════════════════════════════════════════════════════════════════════
# Evaluation functions
# ══════════════════════════════════════════════════════════════════════

# Hallucination #

# Function to create multiple-choice questions from a summary
def create_questions_from_summary(summary, num_questions=10, previous_questions=None):
    """
    Generate multiple-choice questions and answers in structured JSON format from a summary.
    
    Args:
        summary (str): The input summary to generate questions from.
        num_questions (int): Number of questions to generate.
        previous_questions (list): Optional list of previously asked questions to avoid repetition.

    Returns:
        list: Parsed list of new questions (or error info).
    """
    previous_prompt = ""
    if previous_questions:
        previous_q_texts = [q["question"] for q in previous_questions if "question" in q]
        formatted_previous = "\n".join(f"- {q}" for q in previous_q_texts)
        previous_prompt = f"""
The following questions have already been asked and MUST NOT be repeated:

{formatted_previous}
"""

    prompt = f"""
You are a multiple-choice question generation AI.

{previous_prompt}

Based on the following summary, generate exactly {num_questions} multiple choice questions in JSON format.
Each question should be clear, concise, and test comprehension of the summary content.

Each question object must include:
- "question": the question text
- "options": a list of 4 plausible answers (strings)
- "correct_answer": one of the 4 options, marked as the correct one

The output must be a valid JSON object preceded by a "json" tag.
Output format:
json[
  {{
    "question": "...",
    "options": ["...", "...", "...", "..."],
    "correct_answer": "..."
  }},
  ...
]

Summary:
{summary}
"""

    try:
        response = ask_llm(prompt, provider="mistral", temperature=0.7, max_tokens=1500)
        questions = read_json(response)
        return questions
    except Exception as e:
        return {"error": str(e), "raw_output": response}

# Function to create a total number of questions in batches
def create_total_questions(summary, total_questions=40, batch_size=10):
    """
    Generate a specified total number of multiple-choice questions from a summary,
    using create_questions_from_summary in batches to avoid repetition.

    Args:
        summary (str): The input summary to generate questions from.
        total_questions (int): Total number of questions desired.
        batch_size (int): Number of questions to generate per batch (default: 10).

    Returns:
        list: A combined list of all generated questions.
    """
    all_questions = []

    while len(all_questions) < total_questions:
        step = len(all_questions) + 1
        remaining = total_questions - len(all_questions)
        current_batch_size = min(batch_size, remaining)

        new_questions = create_questions_from_summary(
            summary,
            num_questions=current_batch_size,
            previous_questions=all_questions
        )

        # Handle error or unexpected output. If error then the questions are retrieved again
        if isinstance(new_questions, dict) and "error" in new_questions:
          #  return new_questions  # Return the error info directly
            print( f"Error found. Retrying to generate questions at step {step}.")
        else: 

            all_questions.extend(new_questions)

    return all_questions



def read_json(response: str):
    import json

    """
    Extracts and parses the JSON content from a response string 
    that starts with 'json[' and ends with ']'.

    Parameters:
    - response (str): The full string containing the 'json[' block.

    Returns:
    - List[dict]: Parsed JSON list of dictionaries.
    """
    start = response.find("json[")
    if start == -1:
        raise ValueError("No 'json[' tag found in response")

    json_start = start + len("json")
    response = response[json_start:].strip()

    if not (response.startswith('[') and response.endswith(']')):
        raise ValueError("JSON block not formatted correctly")

    return json.loads(response)

# evaluate questions. Avoid biasing results including answers in same request!! Use fewshot and tags
def evaluate_questions(questions_json, test_corpus, manual=False):
    """
    Evaluate the generated json questions against a test corpus.
    Returns the evaluation result.
    """
    questions_only = [
    {
        "question": item["question"],
        "options": item["options"]
    }
    for item in questions_json
    ]    
    solutions_only = [
    {
        "question": item["question"],
        "correct_answer": item["correct_answer"]
    }
    for item in questions_json
    ]
    responder_prompt = f"""   
    You are taking a multiple-choice test based on a corpus of text.
    Your task is to answer each of the questions to the best of your ability.
    Your output must be a valid JSON object preceded by a "json" tag, with
    your answer to each question.

    Output format:
    json[
      {{
        "question": "...",
        "options": ["...", "...", "...", "..."],
        "answer": "..."
      }},
      ...
    ]

    Corpus text: {test_corpus}
    Questions: {questions_only}
    """
    try:
        # Ask the LLM to answer the questions
        answers = ask_llm(responder_prompt, provider="mistral", temperature=0.2, max_tokens=1500)
        answers_json = read_json(answers)
        #print("Test answered successfully by LLM.")
    except Exception as e:
        return {"error": str(e), "raw_output": answers}
    
    answers_json = [
    {
        "question": item["question"],
        "answer": item["answer"]
    }
    for item in answers_json
    ]

    evaluator_prompt = f"""
    You are evaluating multiple-choice test answers.
    Your task is to assess the correctness of each answer based on the provided solutions.
    Your output must be the total number of correct answers, preceded by a "result" tag.

    Output format:
    result <number_of_correct_answers>

    Example of output format:
    result 5
    
    Answers: {answers_json}
    Solutions: {solutions_only}
    """
    # If manual evaluation is requested, skip LLM evaluation
    if manual==False:

        try:
            # Ask the LLM to evaluate the answers
            result = ask_llm(evaluator_prompt, provider="mistral", temperature=0.2, max_tokens=5)
            # Extract the number of correct answers from the result
            result = int(result.split("result ")[1].strip())
            #print("Test evaluated successfully by LLM. Result: ", result)
        except Exception as e:
            return {"error": str(e), "raw_output": result}
    else:
    
        # manually compare answers from answers_json and solutions_only
        correct_count = 0
        for answer in answers_json:
            for solution in solutions_only:
                if answer["question"] == solution["question"]:
                    if answer["answer"] == solution["correct_answer"]:
                        correct_count += 1
        result = correct_count
        #print("Test evaluated successfully manually. Result: ", result)




    return result



from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Function to evaluate hallucination rate in a summary with respect to a corpus
def evaluate_hallucination(summary, test_corpus, num_questions=-1, manual=False, iterations=1):
    """
    Evaluate hallucination in a summary by generating multiple-choice questions
    and testing them against a trusted corpus.

    Args:
        summary (str): The summary to evaluate.
        test_corpus (str): The trusted reference notes.
        num_questions (int): Total number of questions to generate. Default is the max amount given the size.
        manual (bool): If True, evaluate manually instead of using LLM.
        iterations (int): Number of times each batch of questions is answered.

    Returns:
        dict: Hallucination rate and related stats.
    """
    
    # Step 1: Estimate how many questions are appropriate
    num_sentences = summary.count('.') + summary.count('!') + summary.count('?') + summary.count(',') + 1
    if num_sentences < num_questions:
        num_questions = num_sentences
    
    # Deal with the number of questions
    if num_questions < 0:
        num_questions = num_sentences

    # Step 2: Round to nearest multiple of 10
    if num_questions % 10 != 0:
        if num_questions % 10 >= 5:
            num_questions = (num_questions // 10 + 1) * 10
        else:
            num_questions = (num_questions // 10) * 10

    # Step 3: Generate the questions
    questions_json = create_total_questions(summary, total_questions=num_questions, batch_size=10)

    if isinstance(questions_json, dict) and "error" in questions_json:
        return questions_json  # Early exit on generation failure

    # Step 4: Stack into batches of 10
    stacked_questions = [questions_json[i:i+10] for i in range(0, len(questions_json), 10)]

    # Step 5: Evaluate each batch multiple times
    total_questions = 0
    total_correct = 0
    failed_batches = 0

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(evaluate_questions, batch, test_corpus, manual=manual)
            for _ in range(iterations)
            for batch in stacked_questions
        ]

        for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating"):
            try:
                result = future.result()
                if isinstance(result, dict) and "error" in result:
                    failed_batches += 1
                    continue
                total_correct += result
                total_questions += 10  # Each batch is 10 questions
            except Exception:
                failed_batches += 1
                continue

    hallucination_rate = 1 - (total_correct / total_questions) if total_questions > 0 else None

    print("Hallucination rate:", hallucination_rate)    


    return {
        "hallucination_rate": hallucination_rate,
        "total_questions": total_questions,
        "correct_answers": total_correct,
        "incorrect_answers": total_questions - total_correct,
        "failed_batches": failed_batches,
        "iterations_per_batch": iterations,
        "total_batches": len(stacked_questions)
    }