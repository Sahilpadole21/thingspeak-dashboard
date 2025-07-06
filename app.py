import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from io import StringIO

# --- Channel Configuration ---
channels = [
    {
        "name": "Drain Water Level (10 min)",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field1",
        "color": "red",
        "apply_rolling_mean": True,
        "is_water_level": True,
        "id": "water"
    },
    {
        "name": "Rainfall Sensor (30 sec)",
        "channel_id": "2991850",
        "api_key": "UK4DMEZEVVJB711E",
        "field": "field2",
        "color": "blue",
        "apply_rolling_mean": False,
        "is_water_level": False,
        "id": "rain"
    }
]

# --- Sidebar Controls ---
st.sidebar.title("🔧 Dashboard Controls")

# Date range
today = datetime.now()
default_start = today - timedelta(days=1)
start_date = st.sidebar.date_input("Start Date", default_start.date())
end_date = st.sidebar.date_input("End Date", today.date())

# Auto-refresh
refresh_interval = st.sidebar.selectbox("Auto Refresh Interval (min)", [None, 1, 2, 5], index=2)
if refresh_interval:
    st_autorefresh(interval=refresh_interval * 60 * 1000, key="autorefresh")

# Water level threshold
custom_threshold = st.sidebar.number_input("🚨 Water Level Alert Threshold", min_value=0.0, value=100.0)

# Rolling mean window for water level
rolling_window = st.sidebar.number_input("📊 Rolling Mean Window (Water Level)", min_value=1, max_value=100, value=5)

st.sidebar.markdown("### 🔍 Sensor Display Options")

# Per-sensor toggles
sensor_display = {}
for ch in channels:
    with st.sidebar.expander(ch["name"]):
        show_raw = st.checkbox(f"Show Raw Data", value=True, key=f"raw_{ch['id']}")
        show_roll = False
        if ch["apply_rolling_mean"]:
            show_roll = st.checkbox(f"Show Rolling Mean", value=True, key=f"roll_{ch['id']}")
        sensor_display[ch["id"]] = {"raw": show_raw, "roll": show_roll}

# --- Time range setup ---
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Title ---
st.title("🌧️ Urban Drainage Insight Server")
st.write(f"Showing data from **{start_date}** to **{end_date}**")

# --- Initialize Plot ---
fig = go.Figure()
download_data = {}

# --- Fetch and Plot Data ---
for ch in channels:
    url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
    params = {"api_key": ch["api_key"], "start": start_str, "end": end_str}

    try:
        res = requests.get(url, params=params)
        data = res.json()
        feeds = data.get("feeds", [])
        if not feeds:
            st.warning(f"No data in selected range for {ch['name']}")
            continue

        # Parse time and values
        ist = pytz.timezone('Asia/Kolkata')
        times = [datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                 .replace(tzinfo=pytz.utc).astimezone(ist) for entry in feeds]
        values = [float(entry.get(ch["field"], 0)) for entry in feeds]
        df = pd.DataFrame({"Time (IST)": times, "Value": values})

        # Rolling mean if enabled
        if ch["apply_rolling_mean"]:
            df["Rolling Mean"] = df["Value"].rolling(window=rolling_window, min_periods=1).mean()
            if sensor_display[ch["id"]]["roll"]:
                fig.add_trace(go.Scatter(
                    x=df["Time (IST)"],
                    y=df["Rolling Mean"],
                    mode="lines+markers",
                    name=f"{ch['name']} (Rolling Mean)",
                    line=dict(color="orange", dash='dot')
                ))

        # Raw data plot if enabled
        if sensor_display[ch["id"]]["raw"]:
            fig.add_trace(go.Scatter(
                x=df["Time (IST)"],
                y=df["Value"],
                mode="lines+markers",
                name=ch["name"],
                line=dict(color=ch["color"])
            ))

        # Alert for water level
        if ch.get("is_water_level"):
            below_threshold = df[df["Value"] < custom_threshold]
            if not below_threshold.empty:
                last_alert = below_threshold.iloc[-1]
                alert_time = last_alert["Time (IST)"].strftime("%Y-%m-%d %H:%M:%S")
                alert_value = last_alert["Value"]
                st.error(f"🚨 ALERT: Water level dropped to **{alert_value:.2f}** at **{alert_time}** (Threshold: {custom_threshold})")

            fig.add_hline(
                y=custom_threshold,
                line=dict(color="red", dash="dash"),
                annotation_text=f"Threshold: {custom_threshold}",
                annotation_position="top left"
            )

        download_data[ch["name"]] = df
        st.success(f"{ch['name']}: Loaded {len(df)} data points.")

    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

# --- Final Graph Layout ---
fig.update_layout(
    title="📈 Sensor Readings",
    xaxis_title="Time (IST)",
    yaxis_title="Sensor Value",
    legend_title="Sensor",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# --- Download CSV ---
st.subheader("📥 Download Sensor Data (CSV)")
for name, df in download_data.items():
    csv = df.to_csv(index=False)
    st.download_button(
        label=f"Download {name} CSV",
        data=csv,
        file_name=f"{name.replace(' ', '_').lower()}_data.csv",
        mime='text/csv'
    )
