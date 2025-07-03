
from neo4j import GraphDatabase
import pandas as pd, numpy as np
from tqdm.auto import tqdm
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app import config


USER = config.NEO4J_USER
PWD = config.NEO4J_PASSWORD
BOLT_URI = config.NEO4J_URI
#CSV_FILE = "acled_data_Georgia.csv"
#BATCH     = 500

# Load the graph including the event-severity-scores
def load_graph_with_scores(uri=BOLT_URI, user=USER, pwd=PWD, acled_df=None):
    df = acled_df.copy()
    BOLT_URI = uri
    USER, PWD = user, pwd

    df["event_date"] = pd.to_datetime(df["event_date"])
    df["year"] = df["event_date"].dt.year.astype(int)
    df["month"] = df["event_date"].dt.month.astype(int)
    df["day"] = df["event_date"].dt.day.astype(int)
    df["date_int"] = df["event_date"].dt.strftime("%Y%m%d").astype(int)

    def nz(v): return None if pd.isna(v) else str(v).strip()

    def to_dict(r):
        return dict(
            id=r.event_id_cnty,
            date_str=r.event_date.strftime("%Y-%m-%d"),
            year=int(r.year),
            month=int(r.month),
            day=int(r.day),
            date_int=int(r.date_int),
            fatalities=0 if pd.isna(r.fatalities) else int(r.fatalities),
            notes=nz(r.notes) or "",
            admin1=nz(r.admin1),
            country=nz(r.country),
            lat=None if pd.isna(r.latitude) else float(r.latitude),
            lon=None if pd.isna(r.longitude) else float(r.longitude),
            etype=nz(r.event_type),
            actor1=nz(r.actor1),
            inter1=nz(r.inter1),
            actor2=nz(r.actor2),
            inter2=nz(r.inter2),
            severity_score=float(r.severity_score) if 'severity_score' in df.columns and pd.notna(r.severity_score) else None,
            regional_severity=float(r.regional_severity) if 'regional_severity' in df.columns and pd.notna(r.regional_severity) else None
        )

    driver = GraphDatabase.driver(BOLT_URI, auth=(USER, PWD))
    with driver.session() as s:
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Actor) REQUIRE a.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (g:ActorGroup) REQUIRE g.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:EventType) REQUIRE t.code IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.admin1 IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (y:Year) REQUIRE y.value IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Month) REQUIRE (m.year, m.value) IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Day) REQUIRE d.date_int IS UNIQUE")

        for row in df[["admin1", "country", "latitude", "longitude"]].drop_duplicates().itertuples(index=False):
            s.run("""
                MERGE (st:State {admin1:$a})
                ON CREATE SET st.lat=$lat, st.lon=$lon, st.country=$c
                SET st.country = $c
            """, a=row.admin1, lat=row.latitude, lon=row.longitude, c=row.country)

        for et in df["event_type"].dropna().unique():
            s.run("MERGE (:EventType {code:$c})", c=et)

        for grp in pd.unique(df[["inter1", "inter2"]].values.ravel()):
            if pd.notna(grp) and grp:
                s.run("MERGE (:ActorGroup {name:$n})", n=grp)

        BATCH = 5000
        cypher = """
        UNWIND $rows AS row
        MERGE (y:Year {value:row.year})
        MERGE (m:Month {year:row.year, value:row.month})
        MERGE (y)-[:HAS_MONTH]->(m)
        MERGE (d:Day {year:row.year, month:row.month, value:row.day, date_int:row.date_int})
        MERGE (m)-[:HAS_DAY]->(d)

        MERGE (e:Event {id:row.id})
          ON CREATE SET
            e.date = date(row.date_str),
            e.year = row.year,
            e.month = row.month,
            e.day = row.day,
            e.date_int = row.date_int,
            e.fatalities = row.fatalities,
            e.notes = row.notes,
            e.lat = row.lat,
            e.lon = row.lon,
            e.country = row.country,
            e.severity_score = row.severity_score,
            e.regional_severity = row.regional_severity

        MERGE (e)-[:IN_YEAR]->(y)
        MERGE (e)-[:ON_MONTH]->(m)
        MERGE (e)-[:ON_DAY]->(d)

        WITH e, row
        MATCH (s:State {admin1:row.admin1})
        MERGE (e)-[:IN_STATE]->(s)

        WITH e, row
        MATCH (t:EventType {code:row.etype})
        MERGE (e)-[:TYPE]->(t)

        WITH e, row
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
            batch = [to_dict(r) for r in df.iloc[start:start + BATCH].itertuples()]
            s.run(cypher, rows=batch)

    print("\u2705 Graph with severity scores loaded successfully")
    print_graph_info(BOLT_URI, USER, PWD)
    driver.close()



# Load the graph from the acled-structured-CSV file df into Neo4j
def load_graph(uri=BOLT_URI, user=USER, pwd=PWD, acled_df=None):
    df = acled_df.copy()
    BOLT_URI = uri
    USER, PWD = user, pwd

    df["event_date"] = pd.to_datetime(df["event_date"])
    df["year"] = df["event_date"].dt.year.astype(int)
    df["month"] = df["event_date"].dt.month.astype(int)
    df["day"] = df["event_date"].dt.day.astype(int)
    df["date_int"] = df["event_date"].dt.strftime("%Y%m%d").astype(int)

    def nz(v): return None if pd.isna(v) else str(v).strip()

    def to_dict(r):
        return dict(
            id=r.event_id_cnty,
            date_str=r.event_date.strftime("%Y-%m-%d"),
            year=int(r.year),
            month=int(r.month),
            day=int(r.day),
            date_int=int(r.date_int),
            fatalities=0 if pd.isna(r.fatalities) else int(r.fatalities),
            notes=nz(r.notes) or "",
            admin1=nz(r.admin1),
            country=nz(r.country),
            lat=None if pd.isna(r.latitude) else float(r.latitude),
            lon=None if pd.isna(r.longitude) else float(r.longitude),
            etype=nz(r.event_type),
            actor1=nz(r.actor1),
            inter1=nz(r.inter1),
            actor2=nz(r.actor2),
            inter2=nz(r.inter2)
        )

    driver = GraphDatabase.driver(BOLT_URI, auth=(USER, PWD))
    with driver.session() as s:
        # Constraints
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Actor) REQUIRE a.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (g:ActorGroup) REQUIRE g.name IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (t:EventType) REQUIRE t.code IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (s:State) REQUIRE s.admin1 IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (y:Year) REQUIRE y.value IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Month) REQUIRE (m.year, m.value) IS UNIQUE")
        s.run("CREATE CONSTRAINT IF NOT EXISTS FOR (d:Day) REQUIRE d.date_int IS UNIQUE")

        # Static dimension nodes
        for row in df[["admin1", "country", "latitude", "longitude"]].drop_duplicates().itertuples(index=False):
            s.run("""
                MERGE (st:State {admin1:$a})
                ON CREATE SET st.lat=$lat, st.lon=$lon, st.country=$c
                SET st.country = $c
            """, a=row.admin1, lat=row.latitude, lon=row.longitude, c=row.country)

        for et in df["event_type"].dropna().unique():
            s.run("MERGE (:EventType {code:$c})", c=et)

        for grp in pd.unique(df[["inter1", "inter2"]].values.ravel()):
            if pd.notna(grp) and grp:
                s.run("MERGE (:ActorGroup {name:$n})", n=grp)

        # Batch insert
        BATCH = 5000
        cypher = """
        UNWIND $rows AS row
        MERGE (y:Year {value:row.year})
        MERGE (m:Month {year:row.year, value:row.month})
        MERGE (y)-[:HAS_MONTH]->(m)
        MERGE (d:Day {year:row.year, month:row.month, value:row.day, date_int:row.date_int})
        MERGE (m)-[:HAS_DAY]->(d)

        MERGE (e:Event {id:row.id})
          ON CREATE SET
            e.date = date(row.date_str),
            e.year = row.year,
            e.month = row.month,
            e.day = row.day,
            e.date_int = row.date_int,
            e.fatalities = row.fatalities,
            e.notes = row.notes,
            e.lat = row.lat,
            e.lon = row.lon,
            e.country = row.country

        MERGE (e)-[:IN_YEAR]->(y)
        MERGE (e)-[:ON_MONTH]->(m)
        MERGE (e)-[:ON_DAY]->(d)

        WITH e, row
        MATCH (s:State {admin1:row.admin1})
        MERGE (e)-[:IN_STATE]->(s)

        WITH e, row
        MATCH (t:EventType {code:row.etype})
        MERGE (e)-[:TYPE]->(t)

        WITH e, row
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
            batch = [to_dict(r) for r in df.iloc[start:start + BATCH].itertuples()]
            s.run(cypher, rows=batch)

    print("✅ Graph loaded successfully")
    print_graph_info(BOLT_URI, USER, PWD)
    driver.close()
    
# Function to print the number of nodes and relationships in the graph
def print_graph_info(uri=BOLT_URI, user=USER, pwd=PWD):
    print("Graph information:")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as session:
        stats = session.run(
            """
            MATCH (n)
            WITH count(n) AS nodes
            MATCH ()-[r]->()
            RETURN nodes, count(r) AS relationships
            """
        )
        #for row in stats:
        row = stats.single()
        if row is None or (row["nodes"] == 0 and row["relationships"] == 0):
            print("The graph is empty.")
            return("The graph is empty.")
        else:
            print(f"Nodes: {row['nodes']}, Relationships: {row['relationships']}")
            return(f"Nodes: {row['nodes']}, Relationships: {row['relationships']}")


# delete the graph and constraints
def delete_graph(uri=BOLT_URI, user=USER, pwd=PWD):
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        for row in session.run("SHOW CONSTRAINTS"):
            session.run(f"DROP CONSTRAINT {row['name']}")
    print("Graph deleted successfully.")
    print_graph_info(uri, user, pwd)
    driver.close()


# Function to get event nodes from the graph
def get_event_nodes(uri=BOLT_URI, user=USER, pwd=PWD, limit=100000):
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as session:
        result = session.run(
            "MATCH (e:Event) "
            "RETURN e.id AS id, e.date AS date, e.notes AS notes "
            "LIMIT $limit",
            limit=limit
        )
        for record in result:
            print(f"Event ID: {record['id']}, Date: {record['date']}, Notes: {record['notes']}")
    driver.close()


# Function to query events by year, month, and country and state and type optionally
def query_events(uri=BOLT_URI, user=USER, pwd=PWD, year=None, month=None, country=None, event_type=None, state=None, max_results=5000):
    """
    Query events by year, month, country, and optionally state and event type.
    Returns a bullet-point summary of the top events, sorted by fatalities and date.
    """
    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    cypher = """
    MATCH (e:Event)-[:TYPE]->(t:EventType),
          (e)-[:IN_STATE]->(s:State)
    WHERE e.year = $yr AND e.month = $mo
      AND s.country = $country
      {state_filter}
      {event_type_filter}
    RETURN e.id AS id, toString(e.date) AS date,
           s.admin1 AS state, t.code AS type,
           e.fatalities AS fat, e.notes AS note
    ORDER BY fat DESC, date ASC
    LIMIT $limit
    """

    # Add dynamic filter blocks
    event_type_filter = "AND t.code = $etype" if event_type else ""
    state_filter = "AND s.admin1 = $state" if state else ""

    # Inject dynamic Cypher
    final_query = cypher.replace("{event_type_filter}", event_type_filter)
    final_query = final_query.replace("{state_filter}", state_filter)

    with driver.session() as session:
        params = {
            "yr": year,
            "mo": month,
            "country": country,
            "limit": max_results
        }
        if event_type:
            params["etype"] = event_type
        if state:
            params["state"] = state

        rows = session.run(final_query, **params).data()

    driver.close()

    if not rows:
        filter_info = f"{event_type or 'any type'}"
        if state:
            filter_info += f" in {state}"
        return "", 0

    df = pd.DataFrame(rows)

    bullets = "\n".join(
        f"- ({r.id}) {r.date}, {r.state}: {r.type.lower()} – {r.fat} fat. {r.note}"
        for r in df.itertuples()
    )

    return bullets, len(df)