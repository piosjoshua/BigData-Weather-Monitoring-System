
import os
from io import BytesIO
from pathlib import Path
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from dotenv import load_dotenv
from pymongo import MongoClient
from streamlit_autorefresh import st_autorefresh
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


st.set_page_config(
    page_title="QuakeScope | Earthquake Intelligence",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DATABASE", "earthquake_db")
COLLECTION_NAME = os.getenv(
    "MONGODB_COLLECTION", "earthquake_events"
)

BG = "#080F1E"
PANEL = "#111C30"
ACCENT = "#FF7849"
MUTED = "#93A4BA"


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: #080F1E;
    color: #F1F5F9;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1450px;
}

header[data-testid="stHeader"] {
    background: #080F1E !important;
    border-bottom: 1px solid #1F3048;
}

header[data-testid="stHeader"] button,
header[data-testid="stHeader"] svg {
    color: #F1F5F9 !important;
}

header[data-testid="stHeader"] svg {
    fill: none;
}

section[data-testid="stSidebar"] {
    background: #0D1729 !important;
    border-right: 1px solid #233047;
}

section[data-testid="stSidebar"] [data-testid="stRadio"] label,
section[data-testid="stSidebar"] [data-testid="stRadio"] p,
section[data-testid="stSidebar"] [data-testid="stRadio"] span {
    color: #D7E1ED !important;
    opacity: 1 !important;
}

section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover p {
    color: #FF7849 !important;
}

section[data-testid="stSidebar"] [data-testid="stRadio"] input {
    accent-color: #FF7849;
}

section[data-testid="stSidebar"] button {
    color: #F1F5F9 !important;
}

h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: -0.6px;
    color: #F8FAFC;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg, #142238, #101B2D);
    padding: 22px;
    border: 1px solid #263750;
    border-radius: 16px;
    min-height: 115px;
}

[data-testid="stMetricLabel"] {
    color: #A6B6C9 !important;
}

[data-testid="stMetricLabel"] p {
    color: #A6B6C9 !important;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.75rem;
}

div.stButton > button {
    background-color: #FF7849 !important;
    color: #FFFFFF !important;
    border: 1px solid #FF7849 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}

div.stButton > button p {
    color: #FFFFFF !important;
}

div.stButton > button:hover {
    background-color: #FF946C !important;
    border-color: #FF946C !important;
    color: #FFFFFF !important;
}

div.stDownloadButton > button {
    background-color: #17263D !important;
    color: #FFFFFF !important;
    border: 1px solid #FF7849 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
}

div.stDownloadButton > button p {
    color: #FFFFFF !important;
}

div.stDownloadButton > button:hover {
    background-color: #263C58 !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #25354D;
    border-radius: 12px;
    overflow: hidden;
}

hr {
    border-color: #233047 !important;
}

.hero {
    background: linear-gradient(
        110deg,
        #172A45 0%,
        #101B2D 60%,
        #281C28 100%
    );
    border: 1px solid #2B3B55;
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
}

.eyebrow {
    color: #FF9269;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}

.hero-title {
    color: #FFFFFF;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -1px;
    margin-top: 8px;
}

.hero-text {
    color: #A9B8CA;
    margin-top: 8px;
    font-size: 0.95rem;
}

.section-heading {
    color: #F1F5F9;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.2rem;
    font-weight: 600;
    margin: 18px 0 12px;
}

.pill {
    display: inline-block;
    background: #173B32;
    color: #5DE3AB;
    border: 1px solid #28614B;
    padding: 6px 12px;
    border-radius: 30px;
    font-size: 0.76rem;
    font-weight: 600;
}

.info-panel {
    background: #121E32;
    border: 1px solid #293A55;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 14px;
}

.info-label {
    color: #94A6BC;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.info-value {
    color: #FFFFFF;
    font-size: 1.12rem;
    font-weight: 600;
    margin-top: 8px;
    overflow-wrap: anywhere;
}

.small-note {
    color: #B1BED0;
    font-size: 0.83rem;
}

[data-testid="stCaptionContainer"] {
    color: #A4B2C5 !important;
}

</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_mongo_client():
    return MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000
    )


@st.cache_data(ttl=10, show_spinner=False)
def load_data():
    client = get_mongo_client()
    client.admin.command("ping")

    records = list(
        client[DB_NAME][COLLECTION_NAME].find(
            {},
            {"_id": 0}
        )
    )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if "timestamp" not in df.columns:
        raise ValueError(
            "MongoDB records have no timestamp field."
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce"
    )

    for field in [
        "magnitude",
        "latitude",
        "longitude",
        "depth_km",
        "tsunami"
    ]:
        if field not in df.columns:
            df[field] = None

        df[field] = pd.to_numeric(
            df[field],
            errors="coerce"
        )

    if "place" not in df.columns:
        df["place"] = "Unknown"

    df["place"] = df["place"].fillna("Unknown")

    return (
        df.dropna(subset=["timestamp"])
        .sort_values("timestamp", ascending=False)
        .reset_index(drop=True)
    )


def magnitude_category(value):
    if pd.isna(value):
        return "Unknown"
    if value < 2:
        return "Micro"
    if value < 4:
        return "Minor"
    if value < 5:
        return "Light"
    if value < 6:
        return "Moderate"
    if value < 7:
        return "Strong"
    return "Major"


def show_hero(title, subtitle, label):
    st.markdown(
        f"""
        <div class="hero">
            <div class="eyebrow">{escape(label)}</div>
            <div class="hero-title">{escape(title)}</div>
            <div class="hero-text">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def section_heading(text):
    st.markdown(
        f'<div class="section-heading">{escape(text)}</div>',
        unsafe_allow_html=True
    )


def show_statistics(df):
    magnitude = df["magnitude"].dropna()
    depth = df["depth_km"].dropna()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Earthquakes",
        f"{len(df):,}"
    )

    c2.metric(
        "Average Magnitude",
        f"{magnitude.mean():.2f}"
        if not magnitude.empty else "N/A"
    )

    c3.metric(
        "Highest Magnitude",
        f"{magnitude.max():.2f}"
        if not magnitude.empty else "N/A"
    )

    c4.metric(
        "Average Depth",
        f"{depth.mean():.1f} km"
        if not depth.empty else "N/A"
    )


def show_map(df):
    data = df.dropna(
        subset=[
            "latitude",
            "longitude",
            "magnitude"
        ]
    ).copy()

    data = data[
        data["latitude"].between(-90, 90)
        & data["longitude"].between(-180, 180)
    ]

    if data.empty:
        st.info("No earthquake coordinates available.")
        return

    data["marker_size"] = (
        data["magnitude"].clip(lower=0) + 1
    )

    fig = px.scatter_geo(
        data,
        lat="latitude",
        lon="longitude",
        size="marker_size",
        color="magnitude",
        hover_name="place",
        hover_data={
            "magnitude": ":.2f",
            "depth_km": ":.1f",
            "marker_size": False
        },
        color_continuous_scale=[
            "#3B82F6",
            "#FBBF24",
            "#F97316",
            "#EF4444"
        ],
        projection="natural earth"
    )

    fig.update_geos(
        showland=True,
        landcolor="#1D2C42",
        showocean=True,
        oceancolor="#0B1526",
        showcoastlines=True,
        coastlinecolor="#53647C",
        showframe=False,
        bgcolor=BG
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        height=480,
        margin=dict(l=0, r=0, t=5, b=0),
        coloraxis_colorbar=dict(
            title="Magnitude",
            thickness=12
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def show_table(df):
    data = df.copy()

    if "timestamp" in data.columns:
        data["timestamp"] = (
            data["timestamp"]
            .dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        )

    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True
    )


def create_excel(df):
    data = df.copy()

    data["timestamp"] = (
        data["timestamp"]
        .dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    data["category"] = (
        data["magnitude"]
        .apply(magnitude_category)
    )

    for column in data.columns:
        if column != "timestamp":
            data[column] = data[column].apply(
                lambda value: str(value)
                if isinstance(value, (dict, list))
                else value
            )

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        data.to_excel(
            writer,
            index=False,
            sheet_name="Earthquake Records"
        )

        sheet = writer.sheets["Earthquake Records"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

        for cell in sheet[1]:
            cell.fill = PatternFill(
                start_color="17365D",
                end_color="17365D",
                fill_type="solid"
            )
            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )
            cell.alignment = Alignment(
                horizontal="center"
            )

        for index, cells in enumerate(
            sheet.columns,
            start=1
        ):
            width = max(
                len(str(cell.value or ""))
                for cell in cells
            ) + 3

            sheet.column_dimensions[
                get_column_letter(index)
            ].width = min(max(width, 14), 48)

    return output.getvalue()


def style_chart(fig, height=380):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG,
        plot_bgcolor=PANEL,
        font=dict(color="#DCE6F2"),
        height=height,
        margin=dict(
            l=20,
            r=20,
            t=50,
            b=20
        )
    )
    return fig


with st.sidebar:
    st.markdown(
        """
        <div style="padding:12px 0 18px;">
            <div style="
                font-family:'Space Grotesk',sans-serif;
                font-size:1.8rem;
                font-weight:800;
                color:#FFFFFF;
                letter-spacing:-1px;
            ">
                🌐 Quake<span style="color:#FF7849;">Scope</span>
            </div>
            <div style="
                color:#A9B8CA;
                font-size:0.72rem;
                letter-spacing:0.7px;
                margin-top:5px;
            ">
                EARTHQUAKE INTELLIGENCE PLATFORM
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    page = st.radio(
        "Workspace",
        [
            "Overview",
            "Earthquake History",
            "Analytics",
            "About"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    st.markdown(
        '<span class="pill">● LIVE DATA CONNECTION</span>',
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div style="padding-top:20px;">
            <div class="small-note">DATA SOURCE</div>
            <div style="color:#FFFFFF;margin-top:6px;">
                USGS Earthquake API
            </div>
            <div class="small-note" style="margin-top:18px;">
                PROCESSING PIPELINE
            </div>
            <div style="color:#FFFFFF;margin-top:6px;">
                Kafka → Spark → MongoDB
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()
    st.caption("QuakeScope v1.1")
    st.caption("Big Data Application Project")


if page == "Overview":
    st_autorefresh(
        interval=15000,
        key="quake_refresh"
    )


if not MONGO_URI:
    st.error(
        "MongoDB connection information is missing from .env."
    )
    st.stop()


try:
    df = load_data()

except Exception as error:
    st.error("Unable to load data from MongoDB Atlas.")
    st.code(
        f"{type(error).__name__}: {error}"
    )
    st.stop()


if page == "Overview":
    show_hero(
        "Global Earthquake Overview",
        "Monitor recorded seismic activity across the world with real earthquake data.",
        "LIVE SEISMIC INTELLIGENCE"
    )

    top_left, top_right = st.columns([4, 1])

    with top_left:
        st.caption(
            "Automatically checks MongoDB for updates every 15 seconds."
        )

    with top_right:
        if st.button(
            "↻ Refresh Now",
            use_container_width=True
        ):
            st.cache_data.clear()
            st.rerun()

    if df.empty:
        st.warning(
            "No earthquake events are currently stored."
        )
        st.stop()

    show_statistics(df)

    st.write("")

    map_column, latest_column = st.columns(
        [1.7, 1],
        gap="large"
    )

    with map_column:
        section_heading("Global Seismic Activity")
        show_map(df.head(500))

    with latest_column:
        section_heading("Latest Earthquake")

        latest = df.iloc[0]

        magnitude = latest["magnitude"]
        depth = latest["depth_km"]

        magnitude_text = (
            f"M {magnitude:.2f}"
            if pd.notna(magnitude)
            else "N/A"
        )

        place = escape(str(latest["place"]))

        st.markdown(
            f"""
            <div class="info-panel">
                <div class="info-label">
                    Latest Recorded Magnitude
                </div>
                <div style="
                    font-family:'Space Grotesk',sans-serif;
                    font-size:3rem;
                    color:#FF7849;
                    font-weight:800;
                    margin:10px 0 18px;
                ">
                    {magnitude_text}
                </div>
                <div class="info-label">
                    Earthquake Location
                </div>
                <div class="info-value">
                    {place}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.metric(
            "Earthquake Depth",
            f"{depth:.1f} km"
            if pd.notna(depth)
            else "N/A"
        )

        st.metric(
            "Tsunami Indicator",
            "Yes"
            if latest.get("tsunami", 0) == 1
            else "No"
        )

        st.caption(
            "Event time: "
            + latest["timestamp"].strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
        )

    section_heading("Recent Earthquake Activity")

    recent_columns = [
        "timestamp",
        "place",
        "magnitude",
        "depth_km",
        "latitude",
        "longitude"
    ]

    show_table(
        df[recent_columns].head(15)
    )


elif page == "Earthquake History":
    show_hero(
        "Earthquake History",
        "Search, filter, and export all earthquake records stored in MongoDB.",
        "HISTORICAL DATABASE"
    )

    if df.empty:
        st.warning("No historical earthquake records found.")
        st.stop()

    show_statistics(df)

    section_heading("Explore Historical Data")

    date_column, search_column = st.columns(2)

    min_date = df["timestamp"].min().date()
    max_date = df["timestamp"].max().date()

    with date_column:
        selected_dates = st.date_input(
            "Date Range (UTC)",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    with search_column:
        location_search = st.text_input(
            "Search Location",
            placeholder="Alaska, Japan, Philippines..."
        )

    filtered = df.copy()

    if len(selected_dates) == 2:
        start_date, end_date = selected_dates

        filtered = filtered[
            filtered["timestamp"].dt.date.between(
                start_date,
                end_date
            )
        ]

    magnitudes = df["magnitude"].dropna()

    if not magnitudes.empty:
        minimum = float(magnitudes.min())
        maximum = float(magnitudes.max())

        if minimum < maximum:
            mag_range = st.slider(
                "Magnitude Range",
                min_value=minimum,
                max_value=maximum,
                value=(minimum, maximum),
                step=0.01
            )

            filtered = filtered[
                filtered["magnitude"].between(
                    mag_range[0],
                    mag_range[1]
                )
            ]

    if location_search:
        filtered = filtered[
            filtered["place"].str.contains(
                location_search,
                case=False,
                regex=False,
                na=False
            )
        ]

    st.divider()

    heading_column, export_column = st.columns(
        [3, 1]
    )

    with heading_column:
        section_heading(
            f"Showing {len(filtered):,} of {len(df):,} Records"
        )

    with export_column:
        if not filtered.empty:
            st.download_button(
                "↓ Export to Excel",
                data=create_excel(filtered),
                file_name="QuakeScope_Earthquake_History.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True
            )

    show_table(filtered)

    if filtered.empty:
        st.info(
            "No earthquake records match the selected filters."
        )


elif page == "Analytics":
    show_hero(
        "Seismic Data Analytics",
        "Explore magnitude distributions, earthquake trends, and event frequency.",
        "DATA INTELLIGENCE"
    )

    if df.empty:
        st.warning("No earthquake data available.")
        st.stop()

    show_statistics(df)

    valid = df.dropna(
        subset=["magnitude"]
    ).copy()

    if valid.empty:
        st.info("No valid magnitude measurements available.")
        st.stop()

    section_heading("Magnitude Analysis")

    left_chart, right_chart = st.columns(2)

    with left_chart:
        distribution = px.histogram(
            valid,
            x="magnitude",
            nbins=25,
            color_discrete_sequence=[ACCENT],
            title="Magnitude Distribution",
            labels={
                "magnitude": "Earthquake Magnitude"
            }
        )

        st.plotly_chart(
            style_chart(distribution),
            use_container_width=True
        )

    with right_chart:
        valid["category"] = (
            valid["magnitude"]
            .apply(magnitude_category)
        )

        categories = (
            valid["category"]
            .value_counts()
            .reset_index()
        )

        categories.columns = [
            "Category",
            "Count"
        ]

        category_chart = px.pie(
            categories,
            names="Category",
            values="Count",
            hole=0.62,
            title="Earthquake Severity Categories",
            color_discrete_sequence=[
                "#FF7849",
                "#FBBF24",
                "#3B82F6",
                "#22C55E",
                "#A78BFA",
                "#EF4444"
            ]
        )

        st.plotly_chart(
            style_chart(category_chart),
            use_container_width=True
        )

    section_heading("Earthquake Frequency")

    daily = df.copy()
    daily["date"] = daily["timestamp"].dt.date

    daily_counts = (
        daily.groupby("date")
        .size()
        .reset_index(name="count")
    )

    daily_chart = px.bar(
        daily_counts,
        x="date",
        y="count",
        title="Earthquakes Recorded Per Day",
        labels={
            "date": "Date (UTC)",
            "count": "Number of Earthquakes"
        },
        color_discrete_sequence=[ACCENT]
    )

    st.plotly_chart(
        style_chart(daily_chart),
        use_container_width=True
    )

    section_heading("Magnitude Timeline")

    timeline = px.scatter(
        valid.sort_values("timestamp"),
        x="timestamp",
        y="magnitude",
        color="magnitude",
        hover_name="place",
        title="Magnitude Over Time",
        color_continuous_scale="YlOrRd"
    )

    st.plotly_chart(
        style_chart(timeline),
        use_container_width=True
    )

    section_heading("Aggregated Statistics")

    summary = pd.DataFrame({
        "Metric": [
            "Total Earthquake Events",
            "Average Magnitude",
            "Highest Magnitude",
            "Lowest Magnitude",
            "Average Depth (km)",
            "Tsunami-Flagged Events"
        ],
        "Value": [
            len(df),
            round(df["magnitude"].mean(), 2),
            round(df["magnitude"].max(), 2),
            round(df["magnitude"].min(), 2),
            round(df["depth_km"].mean(), 2),
            int((df["tsunami"] == 1).sum())
        ]
    })

    st.dataframe(
        summary,
        use_container_width=True,
        hide_index=True
    )


elif page == "About":
    show_hero(
        "About QuakeScope",
        "A modern earthquake intelligence dashboard powered by Big Data technologies.",
        "PROJECT OVERVIEW"
    )

    section_heading("What is QuakeScope?")

    st.write(
        "QuakeScope is a Big Data application designed "
        "to collect, process, store, and visualize "
        "real earthquake records from the United States "
        "Geological Survey (USGS) Earthquake API."
    )

    section_heading("System Architecture")

    st.code(
        "USGS Earthquake API\n"
        "         ↓\n"
        "Python Kafka Producer\n"
        "         ↓\n"
        "Apache Kafka\n"
        "         ↓\n"
        "Apache Spark Structured Streaming\n"
        "         ↓\n"
        "MongoDB Atlas\n"
        "         ↓\n"
        "Streamlit Dashboard"
    )

    section_heading("Technology Stack")

    technologies = {
        "USGS Earthquake API": "Real-world seismic event data",
        "Apache Kafka": "Message streaming",
        "Apache Spark": "Streaming processing and aggregation",
        "MongoDB Atlas": "Persistent historical event storage",
        "Streamlit": "Interactive dashboard interface",
        "Plotly": "Geographic and statistical visualizations",
        "OpenPyXL": "Excel report generation"
    }

    for technology, description in technologies.items():
        st.markdown(
            f"**{technology}** — {description}"
        )

    section_heading("Main Features")

    st.markdown(
        """
        - Automatically refreshed monitoring dashboard
        - Interactive earthquake location map
        - Complete earthquake history from MongoDB
        - Date, magnitude, and location filters
        - Seismic data analytics and aggregation
        - Downloadable Excel reports
        """
    )

    section_heading("Project Purpose")

    st.write(
        "The system demonstrates how streaming "
        "technologies can transform frequently updated "
        "public earthquake data into useful visual insights. "
        "It allows users to explore earthquake frequency, "
        "magnitude, depth, and geographic distribution."
    )

    st.warning(
        "QuakeScope is an educational analytics platform. "
        "It does not predict earthquakes and is not an "
        "official early-warning system."
    )


st.divider()

st.caption(
    "QuakeScope © 2026 | Real-Time Seismic Intelligence "
    "• USGS API • Apache Kafka • Apache Spark • MongoDB Atlas"
)


