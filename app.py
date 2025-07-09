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

# --- Threshold Settings (one per device) ---
st.sidebar.markdown("### 🚨 Threshold Settings")
threshold_device1 = st.sidebar.number_input("Device 1 Water Level Threshold (cm)", min_value=0.0, value=100.0, key="thresh_water_device1")
threshold_device2 = st.sidebar.number_input("Device 2 Water Level Threshold (cm)", min_value=0.0, value=100.0, key="thresh_water_device2")

# --- Password Section ---
st.sidebar.markdown("### 🔐 Advanced Settings")
pw_attempt = st.sidebar.text_input("Enter Password", type="password")
if pw_attempt == PASSWORD:
    st.sidebar.success("Unlocked ✅")
    authenticated = True
    st.session_state.authenticated = True

# --- Rolling Mean (only editable if authenticated) ---
if authenticated:
    rolling_window = st.sidebar.number_input("📊 Rolling Mean Window", min_value=1, max_value=100, value=5)
else:
    rolling_window = 3
    st.sidebar.info("🔒 Rolling Mean is locked (default: 3)")

# --- Channels Configuration ---
devices = [
    {
        "name": "Device 1",
        "channels": [
            {
                "name": "Water Fill Level (cm)",
                "channel_id": "2997622",
                "api_key": "P8X877UO7IHF2HI4",
                "field": "field1",
                "color": "red",
                "apply_rolling_mean": authenticated,
                "id": "water",
                "water_level_calc": lambda x: 222 - x
            },
            {
                "name": "Rainfall (mm)",
                "channel_id": "2991850",
                "api_key": "UK4DMEZEVVJB711E",
                "field": "field2",
                "color": "blue",
                "apply_rolling_mean": False,
                "id": "rain"
            },
            {
                "name": "Temperature (°C)",
                "channel_id": "2997622",
                "api_key": "P8X877UO7IHF2HI4",
                "field": "field2",
                "color": "green",
                "apply_rolling_mean": authenticated,
                "id": "temp"
            }
        ],
        "threshold": threshold_device1
    },
    {
        "name": "Device 2",
        "channels": [
            {
                "name": "Water Fill Level (cm)",
                "channel_id": "2613741",
                "api_key": "RQKUIUL7DWB7JV8H",
                "field": "field2",
                "color": "red",
                "apply_rolling_mean": authenticated,
                "id": "water",
                "water_level_calc": lambda x: 269 - x
            },
            {
                "name": "Rainfall (mm)",
                "channel_id": "2991850",
                "api_key": "UK4DMEZEVVJB711E",
                "field": "field2",
                "color": "blue",
                "apply_rolling_mean": False,
                "id": "rain"
            },
            {
                "name": "Temperature (°C)",
                "channel_id": "2613741",
                "api_key": "RQKUIUL7DWB7JV8H",
                "field": "field1",
                "color": "green",
                "apply_rolling_mean": authenticated,
                "id": "temp"
            }
        ],
        "threshold": threshold_device2
    }
]

# --- Channel API Config (if authenticated) ---
if authenticated:
    for device in devices:
        with st.sidebar.expander(f"🔌 {device['name']} Settings"):
            for ch in device["channels"]:
                with st.expander(f"Edit {ch['name']}"):
                    ch["channel_id"] = st.text_input("Channel ID", value=ch["channel_id"], key=f"id_{device['name']}_{ch['id']}")
                    ch["api_key"] = st.text_input("API Key", value=ch["api_key"], key=f"key_{device['name']}_{ch['id']}")
                    ch["field"] = st.selectbox("Field", ["field1", "field2", "field3", "field4"],
                                               index=int(ch["field"][-1]) - 1, key=f"field_{device['name']}_{ch['id']}")

# --- Show/Hide Sensor Lines ---
st.sidebar.markdown("### 👁️ Show/Hide Lines")
sensor_display = {}
for device in devices:
    sensor_display[device["name"]] = {}
    with st.sidebar.expander(device["name"]):
        for ch in device["channels"]:
            with st.expander(ch["name"]):
                show_raw = st.checkbox("Show Raw", value=True, key=f"raw_{device['name']}_{ch['id']}")
                show_roll = ch["apply_rolling_mean"] and st.checkbox("Show Rolling Mean", value=True, key=f"roll_{device['name']}_{ch['id']}")
                sensor_display[device["name"]][ch["id"]] = {"raw": show_raw, "roll": show_roll}

# --- Time Range ---
start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date, datetime.max.time())
start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Main Title ---
st.title("🌧️ Urban Drainage Insight Dashboard")
st.write(f"Showing data from **{start_date}** to **{end_date}**")

# --- Function to Load and Plot Data ---
def plot_device_data(device, start_str, end_str, rolling_window, sensor_display):
    fig = go.Figure()
    combined_df = pd.DataFrame()

    for ch in device["channels"]:
        try:
            url = f"https://api.thingspeak.com/channels/{ch['channel_id']}/fields/{ch['field'][-1]}.json"
            res = requests.get(url, params={"api_key": ch["api_key"], "start": start_str, "end": end_str})
            feeds = res.json().get("feeds", [])

            original_len = len(feeds)
            if ch["id"] == "water" and original_len >= 223 and start_date == end_date:
                feeds = feeds[222:]

            ist = pytz.timezone('Asia/Kolkata')
            times = []
            values = []
            prev_val = None

            for entry in feeds:
                raw_val = entry.get(ch["field"])
                try:
                    raw_float = float(raw_val)
                    val = ch.get("water_level_calc", lambda x: x)(raw_float) if ch["id"] == "water" else raw_float
                    timestamp = datetime.strptime(entry["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc).astimezone(ist)

                    if prev_val is None or abs(val - prev_val) <= 20:
                        times.append(timestamp)
                        values.append(val)
                        prev_val = val
                except (TypeError, ValueError):
                    continue

            if not times or not values:
                st.warning(f"No valid data for {ch['name']} in {device['name']}")
                continue

            df = pd.DataFrame({"Time (IST)": times, ch["name"]: values})
            if ch["apply_rolling_mean"]:
                df[f"{ch['name']} - Rolling Mean"] = df[ch["name"]].rolling(window=rolling_window, min_periods=1).mean()

            if combined_df.empty:
                combined_df = df
            else:
                combined_df = pd.merge(combined_df, df, on="Time (IST)", how="outer")

            # Plotting
            if sensor_display[device["name"]][ch["id"]]["raw"]:
                yaxis = 'y2' if ch["id"] == "rain" else 'y1'
                if ch["id"] == "rain":
                    fig.add_trace(go.Bar(
                        x=df["Time (IST)"],
                        y=df[ch["name"]],
                        name=ch["name"],
                        marker=dict(color=ch["color"]),
                        yaxis=yaxis
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=df["Time (IST)"],
                        y=df[ch["name"]],
                        mode="lines+markers",
                        name=ch["name"],
                        line=dict(color=ch["color"]),
                        yaxis=yaxis
                    ))

            if ch["apply_rolling_mean"] and sensor_display[device["name"]][ch["id"]]["roll"]:
                yaxis = 'y2' if ch["id"] == "rain" else 'y1'
                fig.add_trace(go.Scatter(
                    x=df["Time (IST)"],
                    y=df[f"{ch['name']} - Rolling Mean"],
                    mode="lines+markers",
                    name=f"{ch['name']} (Rolling Avg)",
                    line=dict(color="#800080", dash="dot"),
                    yaxis=yaxis
                ))

            # Threshold alerts and line for water level
            if ch["id"] == "water":
                alerts = df[df[ch["name"]] >= device["threshold"]]
                if not alerts.empty:
                    last = alerts.iloc[-1]
                    st.error(f"🚨 ALERT: **{ch['name']}** = **{last[ch['name']]:.2f} cm** at {last['Time (IST)']} ({device['name']})")
                fig.add_hline(y=device["threshold"], line=dict(color="red", dash="dash"),
                              annotation_text=f"{ch['name']} Threshold: {device['threshold']} cm",
                              annotation_position="top left", yref="y1")

        except Exception as e:
            st.error(f"Error loading {ch['name']} for {device['name']}: {e}")

    # Final Plot Layout
    fig.update_layout(
        title=f"📈 {device['name']} Sensor Readings",
        xaxis_title="Time (IST)",
        yaxis_title="Water Level (cm) / Temperature (°C)",
        yaxis2=dict(
            title="Rainfall (mm)",
            overlaying="y",
            side="right",
            showgrid=False
        ),
        hovermode="x unified",
        showlegend=True
    )

    return fig, combined_df

# --- Display Graphs Vertically ---
fig1, df1 = plot_device_data(devices[0], start_str, end_str, rolling_window, sensor_display)
st.plotly_chart(fig1, use_container_width=True)

fig2, df2 = plot_device_data(devices[1], start_str, end_str, rolling_window, sensor_display)
st.plotly_chart(fig2, use_container_width=True)

# --- Download CSV ---
if authenticated:
    st.subheader("📅 Download Combined Sensor Data")
    for device in devices:
        df = df1 if device["name"] == "Device 1" else df2
        if not df.empty:
            csv = df.sort_values("Time (IST)").to_csv(index=False)
            st.download_button(f"Download {device['name']} CSV", data=csv, file_name=f"{device['name'].lower().replace(' ', '_')}_data.csv", mime="text/csv")