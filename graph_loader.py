# -------------------------------------------------------------------------
# graph_loader.py  ―― creates a Neo4j graph from ACLED data
# -------------------------------------------------------------------------

#--------------------------------------------------------------------------
# severiy computation 
# -------------------------------------------------------------------------

import pandas as pd

_DISORDER = {
    'Political violence': 0.7,
    'Violence against civilians': 0.9,
    'Strategic developments': 0.8,
    'Demonstrations': 0.5,
    'Political violence; Demonstrations': 1.0,
    'Protests': 0.3,
    'Riots': 0.5,
}
_EVENT = {
    'Violence against civilians': 0.8,
    'Political violence': 0.7,
    'Battles': 0.8,
    'Explosions/Remote violence': 1.0,
    'Protests': 0.4,
    'Riots': 0.6,
    'Strategic developments': 0.9,
    'Peaceful protest': 0.2,
    'Attack': 0.9,
    'Arrests': 0.3,
}
_WEIGHTS = dict(fatalities=0.1,
                disorder_type=0.3,
                civilian_targeting=0.3,
                event_type=0.3)

def add_severity(df: pd.DataFrame) -> pd.DataFrame:
    """Return `df` copy with `severity_score` (0–100) and helpers."""
    df = df.copy()

    max_fat = df['fatalities'].max() or 0
    df['normalized_fatalities'] = df['fatalities'] / max_fat if max_fat else 0

    df['disorder_severity'] = df['disorder_type'].map(_DISORDER).fillna(0.1)
    df['event_severity']    = df['event_type'].map(_EVENT).fillna(0.1)
    df['civilian_targeting_binary'] = df['civilian_targeting'].notna().astype(int)

    df['severity_score'] = 100 * (
        _WEIGHTS['fatalities']           * df['normalized_fatalities'] +
        _WEIGHTS['disorder_type']        * df['disorder_severity']     +
        _WEIGHTS['civilian_targeting']   * df['civilian_targeting_binary'] +
        _WEIGHTS['event_type']           * df['event_severity']
    )
    return df


# ---------------------------------------------------------------
# graph_loader.py 
# -------------------------------------------------------------------------

import pandas as pd
from neo4j import GraphDatabase
from tqdm import tqdm
       # helper that appends severity_score

# .........................................................................
def load_graph(uri, user, pwd, df):
    """
    Push an ACLED DataFrame into Neo4j, including `severity_score`
    and `SubEventType` nodes.
    """
    # ────────────────────────────────── 1. enrich DataFrame ──────────────
    df = df.copy()
    if "severity_score" not in df.columns:
        df = add_severity(df)

    df["event_date"] = pd.to_datetime(df["event_date"])
    df["year"]      = df["event_date"].dt.year.astype(int)
    df["month"]     = df["event_date"].dt.month.astype(int)
    df["day"]       = df["event_date"].dt.day.astype(int)
    df["date_int"]  = df["event_date"].dt.strftime("%Y%m%d").astype(int)

    # ────────────────────────────────── helpers ──────────────────────────
    def nz(v): return None if pd.isna(v) else str(v).strip()

    def to_dict(r):
        return dict(
            id            = r.event_id_cnty,
            date_str      = r.event_date.strftime("%Y-%m-%d"),
            year          = int(r.year),
            month         = int(r.month),
            day           = int(r.day),
            date_int      = int(r.date_int),
            fatalities    = 0 if pd.isna(r.fatalities) else int(r.fatalities),
            notes         = nz(r.notes) or "",
            admin1        = nz(r.admin1),
            country       = nz(r.country),
            lat           = None if pd.isna(r.latitude)  else float(r.latitude),
            lon           = None if pd.isna(r.longitude) else float(r.longitude),
            etype         = nz(r.event_type),
            sub_etype     = nz(r.sub_event_type),        # ← NEW
            actor1        = nz(r.actor1),
            inter1        = nz(r.inter1),
            actor2        = nz(r.actor2),
            inter2        = nz(r.inter2),
            severity_score = float(r.severity_score)
        )

    # ────────────────────────────────── 3. Neo4j load ───────────────────
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:

        # ---- constraints ------------------------------------------------
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event)        REQUIRE e.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Actor)        REQUIRE a.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (g:ActorGroup)   REQUIRE g.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:EventType)    REQUIRE t.code IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (se:SubEventType) REQUIRE se.code IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:State)        REQUIRE s.admin1 IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (y:Year)         REQUIRE y.value IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Month) REQUIRE (m.year,m.value) IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Day)   REQUIRE d.date_int IS UNIQUE")

        # ---- static nodes ----------------------------------------------
        for row in df[["admin1", "country", "latitude", "longitude"]].drop_duplicates().itertuples(False):
            s.run("""
                MERGE (st:State {admin1:$a})
                ON CREATE SET st.lat=$lat, st.lon=$lon, st.country=$c
                SET st.country = $c
            """, a=row.admin1, lat=row.latitude, lon=row.longitude, c=row.country)

        for code in df["event_type"].dropna().unique():
            s.run("MERGE (:EventType {code:$c})", c=code)

        for sub in df["sub_event_type"].dropna().unique():
            s.run("MERGE (:SubEventType {code:$c})", c=sub)

        for grp in pd.unique(df[["inter1", "inter2"]].values.ravel()):
            if pd.notna(grp) and grp:
                s.run("MERGE (:ActorGroup {name:$n})", n=grp)

        # ---- batch insert ----------------------------------------------
        BATCH = 5000
        cypher = """
        UNWIND $rows AS row

        // Time hierarchy
        MERGE (y:Year  {value:row.year})
        MERGE (m:Month {year:row.year, value:row.month})
        MERGE (y)-[:HAS_MONTH]->(m)
        MERGE (d:Day {year:row.year, month:row.month, value:row.day,
                      date_int:row.date_int})
        MERGE (m)-[:HAS_DAY]->(d)

        // Event node
        MERGE (e:Event {id:row.id})
          ON CREATE SET
            e.date           = date(row.date_str),
            e.year           = row.year,
            e.month          = row.month,
            e.day            = row.day,
            e.date_int       = row.date_int,
            e.fatalities     = row.fatalities,
            e.notes          = row.notes,
            e.lat            = row.lat,
            e.lon            = row.lon,
            e.country        = row.country,
            e.severity_score = row.severity_score

        MERGE (e)-[:IN_YEAR]->(y)
        MERGE (e)-[:ON_MONTH]->(m)
        MERGE (e)-[:ON_DAY]->(d)

        WITH e, row                                    // ── sep #1

        // Spatial
        MATCH (s:State {admin1:row.admin1})
        MERGE (e)-[:IN_STATE]->(s)

        WITH e, row                                    // ── sep #2

        // EventType
        MATCH (t:EventType {code:row.etype})
        MERGE (e)-[:TYPE]->(t)

        WITH e, t, row                                 // ── NEW sep #3

        // SubEventType
        MATCH (se:SubEventType {code:row.sub_etype})
        MERGE (e)-[:SUBTYPE]->(se)
        MERGE (t)-[:HAS_SUBTYPE]->(se)

        WITH e, row                                    // ── sep #4

        // Actors
        FOREACH (_ IN CASE WHEN row.actor1 IS NOT NULL THEN [1] ELSE [] END |
            MERGE (a1:Actor {name:row.actor1})
            MERGE (e)-[:INVOLVES {role:'actor1'}]->(a1)
            FOREACH (_ IN CASE WHEN row.inter1 IS NOT NULL THEN [1] ELSE [] END |
                MERGE (g1:ActorGroup {name:row.inter1})
                MERGE (a1)-[:BELONGS_TO]->(g1)
            )
        )
        FOREACH (_ IN CASE WHEN row.actor2 IS NOT NULL THEN [1] ELSE [] END |
            MERGE (a2:Actor {name:row.actor2})
            MERGE (e)-[:INVOLVES {role:'actor2'}]->(a2)
            FOREACH (_ IN CASE WHEN row.inter2 IS NOT NULL THEN [1] ELSE [] END |
                MERGE (g2:ActorGroup {name:row.inter2})
                MERGE (a2)-[:BELONGS_TO]->(g2)
            )
        )
        """

        for start in tqdm(range(0, len(df), BATCH), desc="Loading events"):
            chunk = [to_dict(r) for r in df.iloc[start:start+BATCH].itertuples()]
            s.run(cypher, rows=chunk)

    print("✅ Graph loaded successfully")
    driver.close()