import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- Channel Configuration ---
channels = [
    {
        "name": "Drain Water Level (10 min)",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field1",
        "color": "red"
    },
    {
        "name": "Rainfall Sensor (30 sec)",
        "channel_id": "2991850",
        "api_key": "UK4DMEZEVVJB711E",
        "field": "field2",
        "color": "blue"
    }
]

st.title("Urban Drainage Insight Server (Last 24 Hours)")

fig = go.Figure()

# Time range: last 24 hours
now_utc = datetime.utcnow()
start_time = now_utc - timedelta(hours=24)
start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

for ch in channels:
    url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
    params = {
        "api_key": ch["api_key"],
        "start": start_str,
        "end": end_str
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        feeds = data.get("feeds", [])
        if not feeds:
            st.warning(f"No data found in the last 24h for {ch['name']}")
            continue

        # Convert UTC to IST
        ist = pytz.timezone('Asia/Kolkata')
        times = [datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(ist)
                 for entry in feeds]
        values = [float(entry.get(ch["field"], 0)) for entry in feeds]

        fig.add_trace(go.Scatter(
            x=times,
            y=values,
            mode='lines+markers',
            name=ch["name"],
            line=dict(color=ch["color"])
        ))

        st.success(f"Fetched {len(values)} points for {ch['name']}")

    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

fig.update_layout(
    title="Live ThingSpeak Sensor Data (Last 24 Hours)",
    xaxis_title="Time (IST)",
    yaxis_title="Sensor Value",
    legend_title="Sensor",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)
