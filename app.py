import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime
import pytz

# --- Channel Configuration ---
channels = [
    {
        "name": "Drain Water Level (10 min interval)",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field1",
        "color": "red",
        "expected_interval": "10 min"
    },
    {
        "name": "Rainfall Sensor (30 sec interval)",
        "channel_id": "2991850",
        "api_key": "UK4DMEZEVVJB711E",
        "field": "field2",
        "color": "blue",
        "expected_interval": "30 sec"
    }
]

st.title("Urban Drainage Insight Server")

fig = go.Figure()

for ch in channels:
    url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
    params = {"api_key": ch["api_key"], "results": 100}  # Increase results for better resolution
    try:
        res = requests.get(url, params=params).json()
        feeds = res.get("feeds", [])
        times = [entry["created_at"] for entry in feeds]
        values = [float(entry.get(ch["field"], 0)) for entry in feeds]

        # Convert UTC timestamps to IST (optional)
        ist = pytz.timezone('Asia/Kolkata')
        times_local = [datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(ist) for t in times]

        fig.add_trace(go.Scatter(
            x=times_local,
            y=values,
            mode='lines+markers',
            name=ch["name"],
            line=dict(color=ch["color"])
        ))

        if feeds:
            st.markdown(f"**Latest update from {ch['name']}**: {times_local[-1].strftime('%Y-%m-%d %H:%M:%S')} IST")

    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

fig.update_layout(
    title="Live Sensor Feed from ThingSpeak",
    xaxis_title="Time (IST)",
    yaxis_title="Sensor Value",
    legend_title="Sensor Source",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)
