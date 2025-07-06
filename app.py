import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import pandas as pd

# --- Channel Configuration ---
channels = [
    {
        "name": "Drain Water Level (10 min)",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field1",
        "color": "red",
        "apply_rolling_mean": True,
        "is_water_level": True
    },
    {
        "name": "Rainfall Sensor (30 sec)",
        "channel_id": "2991850",
        "api_key": "UK4DMEZEVVJB711E",
        "field": "field2",
        "color": "blue",
        "apply_rolling_mean": False,
        "is_water_level": False
    }
]

# --- Sidebar Controls ---
st.sidebar.title("🔧 Dashboard Controls")

# Date selection
today = datetime.now()
default_start = today - timedelta(days=1)
start_date = st.sidebar.date_input("Start Date", default_start.date())
end_date = st.sidebar.date_input("End Date", today.date())

# Auto-refresh
refresh_interval = st.sidebar.selectbox("Auto Refresh Interval (min)", [None, 1, 2, 5], index=2)
if refresh_interval:
    st_autorefresh = st.experimental_rerun
    st.experimental_set_query_params(updated=datetime.now().isoformat())
    st.experimental_rerun = lambda: st_autorefresh()

# Water level threshold
default_threshold = 100
custom_threshold = st.sidebar.number_input("🚨 Water Level Alert Threshold", min_value=0.0, value=float(default_threshold))

st.sidebar.caption("If water level falls below the threshold, an alert will show.")

# --- Time window processing ---
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Title ---
st.title("🌧️ Urban Drainage Insight Server")
st.write(f"Showing data from **{start_date}** to **{end_date}**")

# --- Plot ---
fig = go.Figure()

# --- Fetch & plot data ---
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
            st.warning(f"No data in the selected range for {ch['name']}")
            continue

        # Timezone conversion
        ist = pytz.timezone('Asia/Kolkata')
        times = [datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(ist) for entry in feeds]
        values = [float(entry.get(ch["field"], 0)) for entry in feeds]

        df = pd.DataFrame({"time": times, "value": values})

        # Apply rolling mean (if enabled)
        if ch["apply_rolling_mean"]:
            df["rolling_mean"] = df["value"].rolling(window=5, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=df["time"],
                y=df["rolling_mean"],
                mode="lines+markers",
                name=f"{ch['name']} (Rolling Mean)",
                line=dict(color="orange", dash='dot')
            ))

        # Plot raw data
        fig.add_trace(go.Scatter(
            x=df["time"],
            y=df["value"],
            mode="lines+markers",
            name=ch["name"],
            line=dict(color=ch["color"])
        ))

        # --- Alert Logic for Water Level ---
        if ch.get("is_water_level"):
            below_threshold = df[df["value"] < custom_threshold]
            if not below_threshold.empty:
                alert_time = below_threshold.iloc[-1]["time"].strftime("%Y-%m-%d %H:%M:%S")
                alert_value = below_threshold.iloc[-1]["value"]
                st.error(f"🚨 ALERT: Water level dropped to **{alert_value:.2f}** at **{alert_time}** (below threshold of {custom_threshold})")
            
            # Add horizontal threshold line
            fig.add_hline(y=custom_threshold, line=dict(color="red", dash="dash"),
                          annotation_text=f"Threshold: {custom_threshold}", annotation_position="top left")

        st.success(f"{ch['name']}: Loaded {len(df)} data points.")

    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

# --- Final Plot Layout ---
fig.update_layout(
    title="📈 Sensor Readings",
    xaxis_title="Time (IST)",
    yaxis_title="Sensor Value",
    legend_title="Sensor Source",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)
