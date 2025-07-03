import geopandas as gpd
import plotly.express as px
import os
import streamlit as st

# route of the admin region boundaries shapefile
SHAPEFILE_PATH = os.path.join("data", "admin1", "ne_10m_admin_1_states_provinces.shp")


@st.cache_data
def load_admin1_gdf():
    """
    Load the global admin1 shapefile once.
    """
    return gpd.read_file(SHAPEFILE_PATH)

@st.cache_data
def filter_and_merge_severity(df, country_name):
    """
    Filter admin1 shapes by country and merge with severity scores.
    Includes ACLED → Natural Earth name mapping for DRC.
    """
    gdf = load_admin1_gdf()

    # Filter to the selected country
    country_gdf = gdf[gdf["admin"] == country_name].copy()

    # Clean and normalize fields
    df = df[df["country"] == country_name].copy()
    df["admin1_clean"] = df["admin1"].str.lower().str.replace("-", " ").str.strip()
    country_gdf["shape_clean"] = country_gdf["name"].str.lower().str.replace("-", " ").str.strip()

    # Mapping for DRC only
    acled_to_ne = {
        "maniema": "maniema",
        "nord kivu": "nord kivu",
        "sud kivu": "sud kivu",
        "bas uele": "orientale",
        "haut uele": "orientale",
        "ituri": "orientale",
        "tshopo": "orientale",
        "haut lomami": "katanga",
        "haut katanga": "katanga",
        "lualaba": "katanga",
        "tanganyika": "katanga",
        "kasai": "kasaï occidental",
        "kasai central": "kasaï occidental",
        "kasai oriental": "kasaï oriental",
        "lomami": "kasaï oriental",
        "sankuru": "kasaï oriental",
        "kinshasa": "kinshasa city",
        "kongo central": "bas congo",
        "kwilu": "bandundu",
        "kwango": "bandundu",
        "mai ndombe": "bandundu",
        "sud ubangi": "équateur",
        "nord ubangi": "équateur",
        "mongala": "équateur"
    }

    if country_name == "Democratic Republic of Congo":
        df["admin1_mapped"] = df["admin1_clean"].map(acled_to_ne).fillna(df["admin1_clean"])
        merge_key = "admin1_mapped"
    else:
        merge_key = "admin1_clean"

    # Merge severity data into GeoDataFrame
    merged = country_gdf.merge(
        df[[merge_key, "regional_severity"]],
        left_on="shape_clean",
        right_on=merge_key,
        how="left"
    )

    # Fill missing severity with 0
    merged["regional_severity"] = merged["regional_severity"].fillna(0)

    return merged

# plot function to show grouped events limited and render map with severity colors
def plot_admin1_severity_map(df, country_name, show_events=False, max_events_per_point=5):
    """
    Plot choropleth for the selected country's admin1 regions with optional event points.
    If multiple events occur at the same coordinates, group them and show up to `max_events_per_point`.
    """
    merged = filter_and_merge_severity(df, country_name)

    # Filter event points
    events_df = df[
        (df["country"] == country_name) & df["latitude"].notna() & df["longitude"].notna()
    ].copy()

    # Group events by (lat, lon)
    if show_events and not events_df.empty:
        grouped = (
            events_df.groupby(["latitude", "longitude"], group_keys=False, sort=False)
            .apply(lambda g: g.head(max_events_per_point))  # limit per group
            .reset_index(drop=True)
        )

        # Build hover label
        grouped["hover_label"] = (
            "ID: " + grouped["event_id_cnty"].astype(str) +
            "<br>Note: " + grouped["notes"].fillna("N/A")
        )

    # Plot base choropleth
    fig = px.choropleth(
        merged,
        geojson=merged.geometry.__geo_interface__,
        locations=merged.index,
        color="regional_severity",
        hover_name="name",
        color_continuous_scale="YlOrRd",
        range_color=(0, 100),
        title=f"{country_name} – Regional Conflict Severity (Last month)",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_traces(marker_line_width=0.5, marker_line_color="gray")

    # Add event markers
    if show_events and not events_df.empty:
        fig.add_scattergeo(
            lon=grouped["longitude"],
            lat=grouped["latitude"],
            mode="markers",
            hovertext=grouped["hover_label"],
            hoverinfo="text",
            marker=dict(size=6, color="black", opacity=0.7),
            name="Event IDs"
        )

    fig.update_layout(margin={"r": 0, "t": 40, "l": 0, "b": 0})
    return fig


def get_color(score):
    if score >= 80:
        return "#800026"  # dark red
    elif score >= 60:
        return "#BD0026"  # red
    elif score >= 40:
        return "#E31A1C"  # reddish-orange
    elif score >= 20:
        return "#FC4E2A"  # orange
    elif score > 0:
        return "#FD8D3C"  # light orange
    else:
        return "#f0f0f0"  # grey for no data