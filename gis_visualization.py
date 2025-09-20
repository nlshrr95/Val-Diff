import streamlit as st
import pandas as pd
import pydeck as pdk
import re

def display_gis_map(data_graph, violating_nodes):
    st.info("Building the map.....")
    try:
        # SPARQL query to extract WKT Pounts from project data
        geo_query = """
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        SELECT ?subject ?wkt
        WHERE {
          ?subject geo:hasGeometry ?geom .
          ?geom geo:asWKT ?wkt .
        }
        """
        qres = data_graph.query(geo_query)
        geo_data = [{"subject": str(r["subject"]), "wkt": str(r["wkt"])} for r in qres]

        if not geo_data:
            st.info("No geometry data (geo:hasGeometry/geo:asWKT) found in the project data file.")
            return

        geo_df = pd.DataFrame(geo_data)

        # Function to parse WKT "POINT(lon lat)"
        def parse_point(wkt_str):
            match = re.search(r"POINT\s*\(\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*\)", wkt_str, re.IGNORECASE)
            if match:
                return pd.Series([float(match.group(1)), float(match.group(2))])
            return pd.Series([None, None])

        geo_df[['lon', 'lat']] = geo_df['wkt'].apply(parse_point)
        geo_df.dropna(subset=['lon', 'lat'], inplace=True)

        if geo_df.empty:
            st.info("Could not find any valid POINT geometries in the project data.")
            return
        
        # Green for conforming, Red for violation
        geo_df['color'] = geo_df['subject'].apply(
            lambda x: [255, 0, 0, 160] if x in violating_nodes else [0, 128, 0, 160]
        )
        geo_df['tooltip_text'] = geo_df.apply(
            lambda row: f"<b>Object:</b> {row['subject']}<br/><b>Status:</b> {'Violation' if row['subject'] in violating_nodes else 'Conforming'}",
            axis=1
        )

         # Set initial view
        initial_view_state = pdk.ViewState(
            latitude=geo_df['lat'].mean(),
            longitude=geo_df['lon'].mean(),
            zoom=12,
            pitch=50
        )

        # OSM tile layer
        tile_layer = pdk.Layer(
            "TileLayer",
            data=None,
            min_zoom=0,
            max_zoom=19,
            tile_size=256,
            get_tile_data=None,
            pickable=False,
            url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        )

        # Scatter plot layer
        points_layer = pdk.Layer(
            'ScatterplotLayer',
            data=geo_df,
            get_position='[lon, lat]',
            get_color='color',
            get_radius=25,
            pickable=True,
            auto_highlight=True
        )

        tooltip = {
            "html": "{tooltip_text}",
            "style": {
                "backgroundColor": "black",
                "color": "white",
                "border": "1px solid white",
                "border-radius": "5px",
                "padding": "10px"
            }
        }

        # Create map with OSM + points
        r = pdk.Deck(
            layers=[tile_layer, points_layer],
            initial_view_state=initial_view_state,
            map_style=None,  # Needed so we can add our own tile layer
            tooltip=tooltip
        )

        st.pydeck_chart(r)

    except Exception as e:
        st.error(f"An error occurred during GIS map generation: {e}")