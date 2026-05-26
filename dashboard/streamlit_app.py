import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine


DEFAULT_DB_HOST = os.getenv("DB_HOST", "localhost")
DEFAULT_DB_PORT = int(os.getenv("DB_PORT", "5432"))
DEFAULT_DB_NAME = os.getenv("DB_NAME", "bds")
DEFAULT_DB_USER = os.getenv("DB_USER", "user")
DEFAULT_DB_PASSWORD = os.getenv("DB_PASSWORD", "password")


st.set_page_config(
    page_title="BDS Market Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_engine():
    return create_engine(
        "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
            user=DEFAULT_DB_USER,
            password=DEFAULT_DB_PASSWORD,
            host=DEFAULT_DB_HOST,
            port=DEFAULT_DB_PORT,
            db=DEFAULT_DB_NAME,
        )
    )


@st.cache_data(ttl=30)
def fetch_rows(limit: int) -> pd.DataFrame:
    query = """
        SELECT id, title, total_price_vnd, area_m2, unit_price_m2,
               location, published_date, url
        FROM price_logs
        ORDER BY published_date DESC NULLS LAST, id DESC
        LIMIT %(limit)s
    """
    with get_engine().connect() as conn:
        return pd.read_sql(query, conn, params={"limit": limit})


def format_vnd(value) -> str:
    if pd.isna(value):
        return "N/A"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f} ty"
    if value >= 1_000_000:
        return f"{value / 1_000_000:,.0f} tr"
    return f"{value:,.0f} VND"


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    data = df.copy()
    data["published_date"] = pd.to_datetime(data["published_date"], errors="coerce")
    data["published_day"] = data["published_date"].dt.date
    data["location"] = data["location"].fillna("Unknown")
    data["district"] = data["location"].apply(extract_district)
    return data


def extract_district(location: str) -> str:
    parts = [part.strip() for part in str(location).split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-2]
    if parts:
        return parts[-1]
    return "Unknown"


def slider_bounds(min_value: float, max_value: float, fallback_step: float) -> tuple[float, float, float]:
    if pd.isna(min_value) or pd.isna(max_value):
        return 0.0, fallback_step, fallback_step
    if min_value == max_value:
        return min_value, max_value + fallback_step, fallback_step
    return min_value, max_value, max((max_value - min_value) / 100, fallback_step)


def apply_filters() -> pd.DataFrame:
    st.sidebar.header("Filters")
    limit = st.sidebar.slider("Rows to load", 50, 1000, 300, step=50)

    if st.sidebar.button("Reload data", use_container_width=True):
        st.cache_data.clear()

    df = prepare_data(fetch_rows(limit))
    if df.empty:
        return df

    districts = sorted(df["district"].dropna().unique().tolist())
    selected_districts = st.sidebar.multiselect(
        "District / area",
        districts,
        default=districts[: min(8, len(districts))],
    )

    price_min, price_max, price_step = slider_bounds(
        float(df["total_price_vnd"].min(skipna=True)),
        float(df["total_price_vnd"].max(skipna=True)),
        1_000_000.0,
    )
    area_min, area_max, area_step = slider_bounds(
        float(df["area_m2"].min(skipna=True)),
        float(df["area_m2"].max(skipna=True)),
        1.0,
    )

    price_range = st.sidebar.slider(
        "Total price (VND)",
        min_value=price_min,
        max_value=price_max,
        value=(price_min, price_max),
        step=price_step,
        format="%.0f",
    )
    area_range = st.sidebar.slider(
        "Area (m2)",
        min_value=area_min,
        max_value=area_max,
        value=(area_min, area_max),
        step=area_step,
        format="%.1f",
    )

    filtered = df[
        df["district"].isin(selected_districts)
        & df["total_price_vnd"].between(price_range[0], price_range[1])
        & df["area_m2"].between(area_range[0], area_range[1])
    ]
    return filtered


def render_kpis(df: pd.DataFrame):
    total_listings = len(df)
    avg_price = df["total_price_vnd"].mean()
    avg_area = df["area_m2"].mean()
    avg_unit_price = df["unit_price_m2"].mean()

    cols = st.columns(4)
    cols[0].metric("Listings", f"{total_listings:,}")
    cols[1].metric("Avg total price", format_vnd(avg_price))
    cols[2].metric("Avg area", "N/A" if pd.isna(avg_area) else f"{avg_area:,.1f} m2")
    cols[3].metric("Avg price / m2", format_vnd(avg_unit_price))


def render_charts(df: pd.DataFrame):
    left, right = st.columns([1.15, 1])

    with left:
        st.subheader("Average unit price by day")
        price_by_day = (
            df.dropna(subset=["published_day", "unit_price_m2"])
            .groupby("published_day")["unit_price_m2"]
            .mean()
            .sort_index()
        )
        if price_by_day.empty:
            st.info("Not enough dated records for this chart.")
        else:
            st.line_chart(price_by_day)

    with right:
        st.subheader("Top areas by listings")
        location_counts = df["district"].value_counts().head(12)
        if location_counts.empty:
            st.info("No location data available.")
        else:
            st.bar_chart(location_counts)

    left, right = st.columns(2)
    with left:
        st.subheader("Total price distribution")
        price_series = df["total_price_vnd"].dropna()
        if price_series.empty:
            st.info("No price data available.")
        else:
            price_bins = pd.cut(price_series, bins=12)
            price_counts = price_bins.value_counts().sort_index()
            price_df = price_counts.rename_axis("bucket").reset_index(name="count")
            price_df["bucket"] = price_df["bucket"].astype(str)
            st.bar_chart(price_df.set_index("bucket"))

    with right:
        st.subheader("Area distribution")
        area_series = df["area_m2"].dropna()
        if area_series.empty:
            st.info("No area data available.")
        else:
            area_bins = pd.cut(area_series, bins=12)
            area_counts = area_bins.value_counts().sort_index()
            area_df = area_counts.rename_axis("bucket").reset_index(name="count")
            area_df["bucket"] = area_df["bucket"].astype(str)
            st.bar_chart(area_df.set_index("bucket"))


def render_table(df: pd.DataFrame):
    st.subheader("Latest listings")
    table_df = df[
        [
            "published_date",
            "title",
            "district",
            "total_price_vnd",
            "area_m2",
            "unit_price_m2",
            "url",
        ]
    ].copy()
    table_df["published_date"] = table_df["published_date"].dt.strftime("%Y-%m-%d %H:%M")
    table_df["total_price"] = table_df["total_price_vnd"].apply(format_vnd)
    table_df["unit_price_m2"] = table_df["unit_price_m2"].apply(format_vnd)
    table_df = table_df.drop(columns=["total_price_vnd"])

    st.dataframe(
        table_df,
        width="stretch",
        hide_index=True,
        column_config={
            "published_date": st.column_config.TextColumn("Published"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "district": st.column_config.TextColumn("Area"),
            "area_m2": st.column_config.NumberColumn("Area m2", format="%.1f"),
            "unit_price_m2": st.column_config.TextColumn("Price / m2"),
            "total_price": st.column_config.TextColumn("Total price"),
            "url": st.column_config.LinkColumn("Listing"),
        },
    )


def main():
    st.title("BDS Market Dashboard")
    st.caption("Real-time view of cleaned listing prices stored in Postgres.")

    try:
        df = apply_filters()
    except Exception as exc:
        st.error(f"Cannot load data from Postgres: {exc}")
        st.stop()

    if df.empty:
        st.info("No records found in price_logs. Start Spark and producer to populate data.")
        return

    render_kpis(df)
    st.divider()
    render_charts(df)
    st.divider()
    render_table(df)


if __name__ == "__main__":
    main()
