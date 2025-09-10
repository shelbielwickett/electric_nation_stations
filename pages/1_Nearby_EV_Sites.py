import os
import streamlit as st
import requests
import pandas as pd
from io import StringIO
import folium
from streamlit_folium import st_folium

# --- Helper: get API key from secrets → env → sidebar (required) ---
def get_nrel_api_key() -> str | None:
    # 1) st.secrets; 2) env var; 3) sidebar prompt
    try:
        return st.secrets["NREL_API_KEY"]
    except Exception:
        pass
    k = os.getenv("NREL_API_KEY")
    if k:
        return k
    with st.sidebar:
        return st.text_input(
            "Enter your NREL API key",
            type="password",
            help="Get a free key at https://developer.nrel.gov",
            key="nrel_api_key_input",
        ) or None

# --- Helper Functions ---
def enrich_connector_definitions(df, df2):
    df2['EV Connector Types'] = df2['EV Connector Types'].str.strip()
    connector_map = df2.set_index("EV Connector Types").to_dict(orient="index")

    def map_connectors(cell):
        if pd.isna(cell):
            return pd.Series([None, None, None])
        types = [c.strip() for c in str(cell).split(' ')]
        descriptions, capacities, sources = [], [], []
        for c in types:
            if c in connector_map:
                info = connector_map[c]
                descriptions.append(info.get("Connector Type Description", "N/A"))
                capacities.append(str(info.get("Maximum Charge Capacity", "N/A")))
                sources.append(info.get("Capacity Information Source", "N/A"))
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

def generate_nearby_ev_stations(lat, lon, radius, api_key: str):
    url = "https://developer.nrel.gov/api/alt-fuel-stations/v1/nearest.csv"
    params = {
        "api_key": api_key,
        "fuel_type": "ELEC",
        "latitude": lat,
        "longitude": lon,
        "status": 'E',
        "radius": radius
    }
    response = requests.get(url, params=params, timeout=30)
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

# Geocode that changes address to lat/lon
@st.cache_data(ttl=60*60*24)
def geocode_suggestions(query: str, limit: int = 8):
    """
    Return list of dicts: [{display_name, lat, lon}, ...]
    Uses OpenStreetMap Nominatim. Keep requests modest.
    """
    if not query or len(query.strip()) < 3:
        return []

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query.strip(),
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
    }
    headers = {"User-Agent": "EV-Sites-App/1.0 (contact: shelbied@mtu.edu)"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        results = r.json()

        return [
            {
                "display_name": item.get("display_name", "Unknown"),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            }
            for item in results
            if "lat" in item and "lon" in item
        ]
    except Exception:
        return []

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

# Require API key before proceeding
api_key = get_nrel_api_key()
if not api_key:
    st.warning("Please enter your NREL API key in the sidebar to use this app.\n You can register for an NREL API key [here](https://developer.nrel.gov/signup/).")
    st.stop()

# Choose which type of input
mode = st.radio("Choose input method", ["Address search", "Latitude/Longitude"], horizontal=True)

# Resolve a lat/lon based on mode
resolved_lat = None
resolved_lon = None

if mode == "Address search":
    st.markdown("Start typing an address, city, or landmark, then pick from the dropdown.")
    addr_query = st.text_input(
        "Address or place",
        placeholder="e.g., 1400 Pennsylvania Ave NW, Washington, DC",
        key="addr_query",
    )

    suggestions = geocode_suggestions(addr_query) if addr_query and len(addr_query.strip()) >= 3 else []

    if suggestions:
        labels = [f"{s['display_name']} | ({s['lat']:.6f}, {s['lon']:.6f})" for s in suggestions]
        choice = st.selectbox("Select a match", labels, index=0, key="addr_choice")
        idx = labels.index(choice)
        resolved_lat = suggestions[idx]["lat"]
        resolved_lon = suggestions[idx]["lon"]
    else:
        if addr_query and len(addr_query.strip()) >= 3:
            st.info("No matches yet, try refining your search.")

else:  # Latitude/Longitude
    col_lat, col_lon = st.columns(2)
    with col_lat:
        lat_input = st.text_input("Latitude", "47.1198")
    with col_lon:
        lon_input = st.text_input("Longitude", "-88.5680")

    try:
        resolved_lat = float(lat_input)
        resolved_lon = float(lon_input)
    except Exception:
        resolved_lat, resolved_lon = None, None

# Radius Input
radius_input = st.text_input("Search Radius (miles)", "10")

# Run button
if st.button("Generate"):
    st.session_state.run_query = True

# --- Query + Map ---
if st.session_state.get("run_query"):
    with st.spinner("Querying and filtering stations..."):
        try:
            if resolved_lat is None or resolved_lon is None:
                st.error("Please provide a valid address (and select a result) or valid latitude/longitude.")
            else:
                radius = float(radius_input)
                df = generate_nearby_ev_stations(resolved_lat, resolved_lon, radius, api_key=api_key)

                if not df.empty:
                    st.success(f"Found {len(df)} EV stations within {radius} miles.")
                    st.download_button(
                        "Download CSV",
                        df.to_csv(index=False),
                        file_name=f"ev_stations_within_{radius}_miles_of_query.csv"
                    )
                    st.dataframe(df, use_container_width=True)

                    # --- Map ---
                    m = folium.Map(location=[resolved_lat, resolved_lon], zoom_start=11)
                    folium.Marker([resolved_lat, resolved_lon], popup="Search Center", icon=folium.Icon(color="blue")).add_to(m)
                    folium.Circle(radius=radius * 1609.34, location=[resolved_lat, resolved_lon],
                                  color="blue", fill=True, fill_opacity=0.1).add_to(m)

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
                                selected = st.selectbox(
                                    "Multiple stations at this location. Select one:",
                                    matches["Station Name"]
                                )
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
