import streamlit as st
import requests
import plotly.graph_objects as go

# --- Channel Configuration ---
channels = [
    {
        "name": "Channel 1 - Field 1",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field1",
        "color": "red"
    },
    {
        "name": "Channel 2 - Field 2",
        "channel_id": "2991850",
        "api_key": "UK4DMEZEVVJB711E",
        "field": "field2",
        "color": "blue"
    }
]

st.title("📡 ThingSpeak Multi-Channel Live Dashboard")

fig = go.Figure()

for ch in channels:
    url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
    params = {"api_key": ch["api_key"], "results": 20}
    try:
        res = requests.get(url, params=params).json()
        feeds = res.get("feeds", [])
        times = [entry["created_at"] for entry in feeds]
        values = [float(entry.get(ch["field"], 0)) for entry in feeds]
        fig.add_trace(go.Scatter(x=times, y=values, mode='lines+markers',
                                 name=ch["name"], line=dict(color=ch["color"])))
    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

fig.update_layout(title="Live ThingSpeak Data", xaxis_title="Time", yaxis_title="Value")
st.plotly_chart(fig, use_container_width=True)
