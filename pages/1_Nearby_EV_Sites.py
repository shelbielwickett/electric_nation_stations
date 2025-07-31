import streamlit as st
import requests
import pandas as pd
from io import StringIO
import folium
from streamlit_folium import st_folium

# --- Helper Functions ---
def enrich_connector_definitions(df, df2):
    df2['EV Connector Types'] = df2['EV Connector Types'].str.strip()
    connector_map = df2.set_index("EV Connector Types").to_dict(orient="index")

    def map_connectors(cell):
        if pd.isna(cell):
            return pd.Series([None, None, None])
        types = [c.strip() for c in cell.split(' ')]
        descriptions, capacities, sources = [], [], []
        for c in types:
            if c in connector_map:
                info = connector_map[c]
                descriptions.append(info["Connector Type Description"])
                capacities.append(str(info["Maximum Charge Capacity"]))
                sources.append(info["Capacity Information Source"])
            else:
                descriptions.append("N/A")
                capacities.append("N/A")
                sources.append("N/A")
        return pd.Series([
            "; ".join(descriptions),
            "; ".join(capacities),
            "; ".join(sources)
        ])

    df[["Connector Type Description", "Maximum Charge Capacity", "Capacity Information Source"]] = df["EV Connector Types"].apply(map_connectors)
    return df

def generate_nearby_ev_stations(lat, lon, radius):
    url = "https://developer.nrel.gov/api/alt-fuel-stations/v1/nearest.csv"
    params = {
        "api_key": 'MMnlHTRA1FIWpFCH5JJAlLUFK16QmhzGiPQICAem',
        "fuel_type": "ELEC",
        "latitude": lat,
        "longitude": lon,
        "status": 'E',
        "radius": radius
    }
    response = requests.get(url, params=params)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text), low_memory=False)

    cols = [
        'ID', 'Station Name', 'Street Address', 'City', 'State', 'Latitude', 'Longitude',
        'Open Date', 'Owner Type Code', 'Date Last Confirmed', 'Updated At',
        'EV Network', 'EV Network Web', 'EV Pricing', 'Access Days Time',
        'EV DC Fast Count', 'EV Connector Types', 'EV Other Info',
        'EV Level2 EVSE Num', 'EV Level1 EVSE Num'
    ]
    df2 = pd.read_csv('data/EV Connectors vs Charge Capacities.csv', low_memory=False)
    df = enrich_connector_definitions(df, df2)

    extra_cols = [
        'Connector Type Description',
        'Maximum Charge Capacity',
        'Capacity Information Source'
    ]
    all_cols = cols + extra_cols
    return df[all_cols] if not df.empty else pd.DataFrame(columns=all_cols)

# --- Streamlit App ---
st.set_page_config(page_title="Nearby EV Charging Stations", layout="wide")

# Header with logo
with open("images/logo_base64.txt") as f:
    logo_base64 = f.read()

col1, col2 = st.columns([6, 1])
with col1:
    st.title("Nearby EV Charging Stations")
with col2:
    st.markdown(
        f"""<div style="text-align: right; padding-top: 0.5rem;">
                <img src="data:image/png;base64,{logo_base64}" width="120">
            </div>""",
        unsafe_allow_html=True
    )

st.markdown("*All EV station data is from the Alternative Fuels Data Center https://afdc.energy.gov/*")
st.markdown("Enter coordinates and search radius to locate stations.")

# --- Input Form ---
lat_input = st.text_input("Latitude", "47.1198")
lon_input = st.text_input("Longitude", "-88.5680")
radius_input = st.text_input("Search Radius (miles)", "10")

if st.button("Generate"):
    st.session_state.run_query = True

if st.session_state.get("run_query"):
    with st.spinner("Querying and filtering stations..."):
        try:
            lat = float(lat_input)
            lon = float(lon_input)
            radius = float(radius_input)
            df = generate_nearby_ev_stations(lat, lon, radius)

            if not df.empty:
                st.success(f"Found {len(df)} EV stations within {radius} miles.")
                st.download_button("Download CSV", df.to_csv(index=False), file_name=f"ev_stations_within_{radius}_miles_of_query.csv")
                st.dataframe(df)

                # --- Map ---
                m = folium.Map(location=[lat, lon], zoom_start=11)
                folium.Marker([lat, lon], popup="Search Center", icon=folium.Icon(color="blue")).add_to(m)
                folium.Circle(radius=radius * 1609.34, location=[lat, lon], color="blue", fill=True, fill_opacity=0.1).add_to(m)

                for _, row in df.iterrows():
                    popup_html = f"""
                    <b>Station ID:</b> {row['ID']}<br>
                    <b>Name:</b> {row['Station Name']}<br>
                    <b>Location:</b> {row['City']}, {row['State']}
                    """
                    folium.Marker(
                        location=[row['Latitude'], row['Longitude']],
                        popup=popup_html,
                        icon=folium.Icon(color="green", icon="bolt", prefix="fa")
                    ).add_to(m)

                # Layout
                col_map, col_info = st.columns([2, 1])
                with col_map:
                    st.subheader("Map of EV Stations")
                    map_data = st_folium(m, width=800, height=500, returned_objects=["last_object_clicked"])

                with col_info:
                    st.subheader("Station Details")
                    clicked = map_data.get("last_object_clicked")
                    if clicked:
                        lat_clicked = clicked["lat"]
                        lon_clicked = clicked["lng"]
                        tolerance = 0.0001
                        matches = df[
                            (df["Latitude"].sub(lat_clicked).abs() < tolerance) &
                            (df["Longitude"].sub(lon_clicked).abs() < tolerance)
                        ]
                        if len(matches) == 1:
                            row = matches.iloc[0]
                            for col in matches.columns:
                                st.markdown(f"**{col}:** {row[col]}")
                        elif len(matches) > 1:
                            selected = st.selectbox("Multiple stations at this location. Select one:", matches["Station Name"])
                            row = matches[matches["Station Name"] == selected].iloc[0]
                            for col in matches.columns:
                                st.markdown(f"**{col}:** {row[col]}")
                        else:
                            st.info("Station not found in data.")
                    else:
                        st.info("Click a station marker on the map to see its details.")
            else:
                st.warning("No EV stations found within the given radius.")
        except Exception as e:
            st.error(f"Error: {e}")
