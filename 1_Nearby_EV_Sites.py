import streamlit as st
import requests
import pandas as pd
from io import StringIO
import geopandas as gpd
from shapely.geometry import Point
from math import radians, cos, sin, asin, sqrt
import folium
from streamlit_folium import st_folium

def generate_nearby_ev_stations(lat, lon, radius):
    # API request to CSV endpoint
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

    # Read CSV response
    df = pd.read_csv(StringIO(response.text), low_memory=False)

    # Select your desired columns
    cols = [
        'ID',
        'Station Name',
        'Street Address',
        'City',
        'State',
        'Latitude',
        'Longitude',
        'Open Date',
        'Owner Type Code',
        'Date Last Confirmed',
        'Updated At',
        'EV Network',
        'EV Network Web',
        'EV Pricing',
        'Access Days Time',
        'EV DC Fast Count',
        'EV Connector Types',
        'EV Other Info',
        'EV Level2 EVSE Num',
        'EV Level1 EVSE Num'
    ]
    return df[cols] if not df.empty else pd.DataFrame(columns=cols)

# --- Streamlit Interface ---
st.set_page_config(page_title="Nearby EV Charging Stations", layout="wide")

st.title("Nearby EV Charging Stations")
st.markdown("Enter coordinates and search radius to locate stations.")

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
                st.download_button("Download CSV", df.to_csv(index=False), file_name=f"ev_stations_within_{radius_input}_miles_of_query.csv")
                st.dataframe(df)

                # Create map
                m = folium.Map(location=[lat, lon], zoom_start=11)
                folium.Marker([lat, lon], popup="Search Center", icon=folium.Icon(color="blue")).add_to(m)
                folium.Circle(radius=radius * 1609.34, location=[lat, lon], color="blue", fill=True, fill_opacity=0.1).add_to(m)

                for _, row in df.iterrows():
                    folium.Marker(
                        location=[row['Latitude'], row['Longitude']],
                        popup=f"{row['Station Name']} ({row['City']}, {row['State']})",
                        icon=folium.Icon(color="green", icon="bolt", prefix="fa")
                    ).add_to(m)

                # Layout: Map (left), Station Details (right)
                col1, col2 = st.columns([2, 1])  # 2:1 width ratio

                with col1:
                    st.subheader("Map of EV Stations")
                    map_data = st_folium(m, width=800, height=500, returned_objects=["last_object_clicked"])

                with col2:
                    st.subheader("Station Details")

                    clicked = map_data.get("last_object_clicked")
                    if clicked:
                        lat_clicked = clicked["lat"]
                        lon_clicked = clicked["lng"]

                        # Match clicked point to row
                        tolerance = 0.0001
                        match = df[
                            (df["Latitude"].sub(lat_clicked).abs() < tolerance) &
                            (df["Longitude"].sub(lon_clicked).abs() < tolerance)
                        ]

                        if not match.empty:
                            row = match.iloc[0]
                            for colname in match.columns:
                                st.markdown(f"**{colname}:** {row[colname]}")
                        else:
                            st.info("Station not found in data.")
                    else:
                        st.info("Click a station marker on the map to see its details.")

            else:
                st.warning("No EV stations found within the given radius.")
        except Exception as e:
            st.error(f"Error: {e}")
