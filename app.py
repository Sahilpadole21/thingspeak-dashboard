import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# --- Password Setup ---
PASSWORD = "Sahil@9573"
authenticated = st.session_state.get("authenticated", False)

st.set_page_config(page_title="Urban Drainage Dashboard", layout="wide")

# --- Sidebar: Public Controls ---
st.sidebar.title("🔧 Visualization Controls")

today = datetime.now()
default_start = today - timedelta(days=1)
start_date = st.sidebar.date_input("🗕️ Start Date", default_start.date())
end_date = st.sidebar.date_input("🗕️ End Date", today.date())

refresh_interval = st.sidebar.selectbox("🔁 Auto Refresh Interval (min)", [None, 1, 2, 5], index=2)
if refresh_interval:
    st_autorefresh(interval=refresh_interval * 60 * 1000, key="autorefresh")

# --- Password Section ---
st.sidebar.markdown("### 🔐 Advanced Settings")
pw_attempt = st.sidebar.text_input("Enter Password", type="password")
if pw_attempt == PASSWORD:
    st.sidebar.success("Unlocked ✅")
    authenticated = True
    st.session_state.authenticated = True

# --- Threshold & Rolling Mean (only editable if authenticated) ---
if authenticated:
    threshold = st.sidebar.number_input("🚨 Water Level Threshold (cm)", min_value=0.0, value=100.0)
    rolling_window = st.sidebar.number_input("📊 Rolling Mean Window", min_value=1, max_value=100, value=5)
else:
    threshold = 100.0
    rolling_window = 3
    st.sidebar.info("🔒 Threshold & Rolling Mean are locked (enter password to edit)")

# --- Channels Config ---
channels = [
    {
        "name": "Drain Water Fill Level (cm)",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field1",
        "color": "red",
        "apply_rolling_mean": authenticated,  # Rolling mean only if authenticated
        "is_water_level": True,
        "id": "water"
    },
    {
        "name": "Rainfall Sensor (mm)",
        "channel_id": "2991850",
        "api_key": "UK4DMEZEVVJB711E",
        "field": "field2",
        "color": "blue",
        "apply_rolling_mean": False,
        "is_water_level": False,
        "id": "rain"
    },
    {
        "name": "Temperature Sensor (°C)",
        "channel_id": "2997622",
        "api_key": "P8X877UO7IHF2HI4",
        "field": "field2",
        "color": "green",
        "apply_rolling_mean": authenticated,  # Rolling mean only if authenticated
        "is_water_level": False,
        "id": "temp"
    }
]

# --- Channel API Config (if authenticated) ---
if authenticated:
    for ch in channels:
        with st.sidebar.expander(f"🔌 Edit {ch['name']}"):
            ch["channel_id"] = st.text_input("Channel ID", value=ch["channel_id"], key=f"id_{ch['id']}")
            ch["api_key"] = st.text_input("API Key", value=ch["api_key"], key=f"key_{ch['id']}")
            ch["field"] = st.selectbox("Field", ["field1", "field2", "field3", "field4"],
                                       index=int(ch["field"][-1]) - 1, key=f"field_{ch['id']}")

# --- Show/Hide Sensor Lines ---
st.sidebar.markdown("### 👁️ Show/Hide Lines")
sensor_display = {}
for ch in channels:
    with st.sidebar.expander(ch["name"]):
        show_raw = st.checkbox("Show Raw", value=True, key=f"raw_{ch['id']}")
        show_roll = ch["apply_rolling_mean"] and st.checkbox("Show Rolling Mean", value=True, key=f"roll_{ch['id']}")
        sensor_display[ch["id"]] = {"raw": show_raw, "roll": show_roll}

# --- Time Range ---
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Main Title ---
st.title("🌧️ Urban Drainage Insight Dashboard")
st.write(f"Showing data from **{start_date}** to **{end_date}**")

# --- Plot Init ---
fig = go.Figure()
combined_df = pd.DataFrame()

# --- Load and Plot Data ---
for ch in channels:
    try:
        url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
        res = requests.get(url, params={"api_key": ch["api_key"], "start": start_str, "end": end_str})
        feeds = res.json().get("feeds", [])

        original_len = len(feeds)
        current_reading = original_len

        if ch["id"] == "water":
            if original_len >= 223 and start_date == end_date:
                feeds = feeds[222:]

        ist = pytz.timezone('Asia/Kolkata')
        times = []
        values = []
        prev_val = None

        for entry in feeds:
            raw_val = entry.get(ch["field"])
            try:
                raw_float = float(raw_val)
                val = 222 - raw_float if ch["id"] == "water" else raw_float
                timestamp = datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(ist)

                if prev_val is None or abs(val - prev_val) <= 20:
                    times.append(timestamp)
                    values.append(val)
                    prev_val = val
            except (TypeError, ValueError):
                continue

        if not times or not values:
            st.warning(f"No valid data for {ch['name']}")
            continue

        df = pd.DataFrame({"Time (IST)": times, ch["name"]: values})
        if ch["apply_rolling_mean"]:
            df[f"{ch['name']} - Rolling Mean"] = df[ch["name"]].rolling(window=rolling_window, min_periods=1).mean()

        if combined_df.empty:
            combined_df = df
        else:
            combined_df = pd.merge(combined_df, df, on="Time (IST)", how="outer")

        if sensor_display[ch["id"]]["raw"]:
            fig.add_trace(go.Scatter(
                x=df["Time (IST)"],
                y=df[ch["name"]],
                mode="lines+markers",
                name=ch["name"],
                line=dict(color=ch["color"])
            ))

        if ch["apply_rolling_mean"] and sensor_display[ch["id"]]["roll"]:
            fig.add_trace(go.Scatter(
                x=df["Time (IST)"],
                y=df[f"{ch['name']} - Rolling Mean"],
                mode="lines+markers",
                name=f"{ch['name']} (Rolling Avg)",
                line=dict(color="orange", dash="dot")
            ))

        if ch["is_water_level"]:
            alerts = df[df[ch["name"]] >= threshold]
            if not alerts.empty:
                last = alerts.iloc[-1]
                st.error(f"🚨 ALERT: **{ch['name']}** = **{last[ch['name']]:.2f} cm** at {last['Time (IST)']}")
            fig.add_hline(y=threshold, line=dict(color="red", dash="dash"),
                          annotation_text=f"Threshold: {threshold} cm",
                          annotation_position="top left")

    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

# --- Final Plot ---
fig.update_layout(
    title="📈 Sensor Readings Over Time",
    xaxis_title="Time (IST)",
    yaxis_title="Sensor Value (cm / mm / °C)",
    hovermode="x unified"
)
st.plotly_chart(fig, use_container_width=True)

# --- Download CSV ---
if authenticated and not combined_df.empty:
    st.subheader("📅 Download Combined Sensor Data")
    csv = combined_df.sort_values("Time (IST)").to_csv(index=False)
    st.download_button("Download CSV", data=csv, file_name="combined_data.csv", mime="text/csv")
