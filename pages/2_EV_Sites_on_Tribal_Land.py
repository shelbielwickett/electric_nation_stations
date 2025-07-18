# streamlit_app.py

import streamlit as st
import requests
import pandas as pd
from io import StringIO
import geopandas as gpd
from shapely.geometry import Point

st.set_page_config(page_title="EV Stations on Tribal Lands", layout="wide")

st.title("EV Stations on Tribal Lands")
st.markdown("Enter U.S. state abbreviations (e.g., MI, WI, SD) to filter EV stations on tribal land.")

def generate_ev_station_data(state_names):
    # API request
    url = "https://developer.nrel.gov/api/alt-fuel-stations/v1.csv"
    params = {
        "api_key": 'MMnlHTRA1FIWpFCH5JJAlLUFK16QmhzGiPQICAem',
        "fuel_type": "ELEC",
        "state": ",".join(state_names),
        "status": 'E',
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    df = pd.read_csv(StringIO(response.text), low_memory=False)

    # Convert to GeoDataFrame
    df['geometry'] = df.apply(lambda row: Point(row['Longitude'], row['Latitude']), axis=1)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

    # Load shapefiles (adjust to relative path or absolute path)
    states = gpd.read_file('data/cb_2018_us_state_500k.shp').to_crs('EPSG:4326')
    tribal = gpd.read_file('data/tl_2024_us_aiannh.shp').to_crs('EPSG:4326')
    tribal = tribal[tribal['AIANNHCE'].notna()].rename(columns={'NAME': 'Tribal Nation'})

    # Filter by state
    target_states = states[states['STUSPS'].isin(state_names)]
    gdf = gpd.sjoin(gdf, target_states, how='inner', predicate='within')
    if 'index_right' in gdf.columns:
        gdf = gdf.drop(columns='index_right')

    # Filter by tribal land
    on_tribal_land = gpd.sjoin(gdf, tribal, how='left', predicate='within')
    on_tribal_land['on_tribal_land'] = on_tribal_land['AIANNHCE'].notna()
    inside_tribal_land = on_tribal_land[on_tribal_land['on_tribal_land']]

    # Select columns
    cols = [
        'ID', 'Station Name', 'Street Address', 'City', 'State', 'Latitude', 'Longitude',
        'Open Date', 'Owner Type Code', 'Date Last Confirmed', 'Updated At',
        'EV Network', 'EV Network Web', 'EV Pricing', 'Access Days Time',
        'EV DC Fast Count', 'EV Connector Types', 'EV Other Info',
        'EV Level2 EVSE Num', 'EV Level1 EVSE Num', 'Tribal Nation'
    ]

    return inside_tribal_land[cols] if not inside_tribal_land.empty else pd.DataFrame(columns=cols)

# --- Streamlit Interface ---
state_input = st.text_input("State Abbreviations", "ND,SD,MN,MI,WI")

if st.button("Generate"):
    state_list = [s.strip().upper() for s in state_input.split(",") if s.strip()]
    with st.spinner("Querying and filtering stations..."):
        try:
            df = generate_ev_station_data(state_list)
            if not df.empty:
                st.success(f"Found {len(df)} EV stations on tribal land.")
                st.download_button("Download CSV", df.to_csv(index=False), file_name="ev_stations_on_tribal_land.csv")
                st.dataframe(df)
            else:
                st.warning("No EV stations found on tribal land for the selected states.")
        except Exception as e:
            st.error(f"Error: {e}")
