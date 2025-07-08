import streamlit as st
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from functools import reduce

# --- Password Setup ---
PASSWORD = "Sahil@9573"
authenticated = st.session_state.get("authenticated", False)

st.set_page_config(page_title="Urban Drainage Dashboard", layout="wide")

# --- Sidebar ---
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

# --- Threshold & Rolling Mean ---
if authenticated:
    threshold = st.sidebar.number_input("🚨 Water Level Threshold (cm)", min_value=0.0, value=100.0)
    rolling_window = st.sidebar.number_input("📊 Rolling Mean Window", min_value=1, max_value=100, value=5)
else:
    threshold = 100.0
    rolling_window = 3
    st.sidebar.info("🔐 Threshold & Rolling Mean are locked (enter password to edit)")

# --- Channel Configs ---
channels = [
    {
        "name": "Drain Water Fill Level (cm)",
        "channel_id": "2386484",
        "api_key": "97JX1RZK6KTXO14K",
        "field": "field1",
        "color": "red",
        "apply_rolling_mean": authenticated,
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
        "channel_id": "2386484",
        "api_key": "97JX1RZK6KTXO14K",
        "field": "field2",
        "color": "green",
        "apply_rolling_mean": authenticated,
        "is_water_level": False,
        "id": "temp"
    }
]

# Editable if authenticated
if authenticated:
    for ch in channels:
        with st.sidebar.expander(f"🔌 Edit {ch['name']}"):
            ch["channel_id"] = st.text_input("Channel ID", value=ch["channel_id"], key=f"id_{ch['id']}")
            ch["api_key"] = st.text_input("API Key", value=ch["api_key"], key=f"key_{ch['id']}")
            ch["field"] = st.selectbox("Field", ["field1", "field2", "field3", "field4"],
                                       index=int(ch["field"][-1]) - 1, key=f"field_{ch['id']}")

# --- Show/Hide Controls ---
st.sidebar.markdown("### 👁️ Show/Hide Lines")
sensor_display = {}
for ch in channels:
    with st.sidebar.expander(ch["name"]):
        show_raw = st.checkbox("Show Raw", value=True, key=f"raw_{ch['id']}")
        show_roll = ch["apply_rolling_mean"] and st.checkbox("Show Rolling Mean", value=True, key=f"roll_{ch['id']}")
        sensor_display[ch["id"]] = {"raw": show_raw, "roll": show_roll}

# --- Time Range Formatting ---
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Main Title ---
st.title("🌧️ Urban Drainage Insight Dashboard")
st.write(f"Showing data from **{start_date}** to **{end_date}**")

# --- First Graph ---
fig = go.Figure()
combined_df = pd.DataFrame()

for ch in channels:
    try:
        url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
        res = requests.get(url, params={"api_key": ch["api_key"], "start": start_str, "end": end_str})
        feeds = res.json().get("feeds", [])
        ist = pytz.timezone('Asia/Kolkata')
        times, values = [], []
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
            except:
                continue

        df = pd.DataFrame({"Time (IST)": times, ch["name"]: values})
        if ch["apply_rolling_mean"]:
            df[f"{ch['name']} - Rolling Mean"] = df[ch["name"]].rolling(window=rolling_window, min_periods=1).mean()

        if combined_df.empty:
            combined_df = df
        else:
            combined_df = pd.merge(combined_df, df, on="Time (IST)", how="outer")

        if sensor_display[ch["id"]]["raw"]:
            fig.add_trace(go.Scatter(x=df["Time (IST)"], y=df[ch["name"]], mode="lines+markers", name=ch["name"], line=dict(color=ch["color"])))

        if ch["apply_rolling_mean"] and sensor_display[ch["id"]]["roll"]:
            fig.add_trace(go.Scatter(x=df["Time (IST)"], y=df[f"{ch['name']} - Rolling Mean"],
                                     mode="lines+markers", name=f"{ch['name']} (Rolling Avg)",
                                     line=dict(color="orange", dash="dot")))

        if ch["is_water_level"]:
            alerts = df[df[ch["name"]] >= threshold]
            if not alerts.empty:
                last = alerts.iloc[-1]
                st.error(f"🚨 ALERT: **{ch['name']}** = **{last[ch['name']]:.2f} cm** at {last['Time (IST)']}")
            fig.add_hline(y=threshold, line=dict(color="red", dash="dash"),
                          annotation_text=f"Threshold: {threshold} cm", annotation_position="top left")

    except Exception as e:
        st.error(f"Error loading {ch['name']}: {e}")

fig.update_layout(title="📊 Sensor Readings Over Time", xaxis_title="Time (IST)", yaxis_title="Sensor Value (cm / mm / °C)", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# --- Second Graph: Rain Water Collection ---
st.markdown("## 🌧️ Rain Water Collection")

fields_info = [
    {"channel_id": "2386484", "api_key": "97JX1RZK6KTXO14K", "field": 7, "label": "ch1_f7"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 2, "label": "ch2_f2"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 4, "label": "ch2_f4"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 6, "label": "ch2_f6"},
    {"channel_id": "2386484", "api_key": "97JX1RZK6KTXO14K", "field": 1, "label": "ch1_f1"},
    {"channel_id": "2386484", "api_key": "97JX1RZK6KTXO14K", "field": 3, "label": "ch1_f3"},
    {"channel_id": "2386484", "api_key": "97JX1RZK6KTXO14K", "field": 5, "label": "ch1_f5"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 1, "label": "ch2_f1"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 3, "label": "ch2_f3"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 5, "label": "ch2_f5"},
    {"channel_id": "2708884", "api_key": "AETOH2AGT7L7O90D", "field": 7, "label": "ch2_f7"},
    {"channel_id": "2991850", "api_key": "UK4DMEZEVVJB711E", "field": 2, "label": "Rainfall (mm)"}
]

def fetch_field(cid, key, field, start, end, label):
    try:
        url = f"https://api.thingspeak.com/channels/{cid}/fields/{field}.json"
        res = requests.get(url, params={"api_key": key, "start": start, "end": end})
        feeds = res.json().get("feeds", [])
        ist = pytz.timezone('Asia/Kolkata')
        data = []
        for entry in feeds:
            val = entry.get(f"field{field}")
            if val:
                try:
                    value = float(val)
                    ts = datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(ist)
                    data.append((ts, value))
                except:
                    continue
        return pd.DataFrame(data, columns=["Time (IST)", label])
    except:
        return pd.DataFrame()

# Combine & plot
all_dataframes = [fetch_field(f["channel_id"], f["api_key"], f["field"], start_str, end_str, f["label"]) for f in fields_info]
if all_dataframes:
    df_combined = reduce(lambda left, right: pd.merge(left, right, on="Time (IST)", how="outer"), all_dataframes)
    df_combined.sort_values("Time (IST)", inplace=True)
    df_combined.fillna(method='ffill', inplace=True)

    df_combined["Total Volume"] = df_combined[["ch1_f7", "ch2_f2", "ch2_f4", "ch2_f6"]].sum(axis=1)
    df_combined["Flowrate"] = df_combined[["ch1_f1", "ch1_f3", "ch1_f5", "ch2_f1", "ch2_f3", "ch2_f5", "ch2_f7"]].sum(axis=1)

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df_combined["Time (IST)"], y=df_combined["Total Volume"], name="Total Volume (litres)", mode="lines+markers", line=dict(color="blue")))
    fig2.add_trace(go.Scatter(x=df_combined["Time (IST)"], y=df_combined["Flowrate"], name="Flowrate (litres/sec)", mode="lines+markers", line=dict(color="green")))
    if "Rainfall (mm)" in df_combined.columns:
        fig2.add_trace(go.Scatter(x=df_combined["Time (IST)"], y=df_combined["Rainfall (mm)"], name="Rainfall (mm)", mode="lines+markers", line=dict(color="purple")))

    fig2.update_layout(title="🌧️ Rain Water Collection: Volume, Flowrate & Rainfall Over Time",
                       xaxis_title="Time (IST)", yaxis_title="Sensor Values", hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

# --- CSV Download for First Graph ---
if authenticated and not combined_df.empty:
    st.subheader("🗓️ Download Combined Sensor Data")
    csv = combined_df.sort_values("Time (IST)").to_csv(index=False)
    st.download_button("Download CSV", data=csv, file_name="combined_data.csv", mime="text/csv")
