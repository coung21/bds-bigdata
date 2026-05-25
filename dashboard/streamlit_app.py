import os

import pandas as pd
from sqlalchemy import create_engine
import streamlit as st

DEFAULT_DB_HOST = os.getenv("DB_HOST", "localhost")
DEFAULT_DB_PORT = int(os.getenv("DB_PORT", "5432"))
DEFAULT_DB_NAME = os.getenv("DB_NAME", "bds")
DEFAULT_DB_USER = os.getenv("DB_USER", "user")
DEFAULT_DB_PASSWORD = os.getenv("DB_PASSWORD", "password")


def fetch_rows(limit: int):
    engine = create_engine(
        "postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}".format(
            user=DEFAULT_DB_USER,
            password=DEFAULT_DB_PASSWORD,
            host=DEFAULT_DB_HOST,
            port=DEFAULT_DB_PORT,
            db=DEFAULT_DB_NAME,
        )
    )
    query = """
        SELECT id, title, total_price_vnd, area_m2, unit_price_m2,
               location, published_date, url
        FROM price_logs
        ORDER BY published_date DESC NULLS LAST
        LIMIT %(limit)s
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"limit": limit})
    return df


def main():
    st.set_page_config(page_title="BDS Stream Dashboard", layout="wide")
    st.title("BDS Stream Dashboard")

    tab_overview, tab_data, tab_charts = st.tabs(["Overview", "Data", "Charts"])

    with tab_overview:
        st.write("Basic dashboard for streaming data stored in Postgres.")
        st.write(
            "Update connection settings via env vars: DB_HOST, DB_PORT, DB_NAME, "
            "DB_USER, DB_PASSWORD."
        )

    with tab_data:
        st.subheader("Latest records")
        limit = st.number_input("Number of rows", min_value=1, max_value=500, value=50)
        reload_clicked = st.button("Reload")
        should_load = reload_clicked or "loaded_once" not in st.session_state

        if should_load:
            st.session_state.loaded_once = True
            try:
                df = fetch_rows(int(limit))
            except Exception as exc:
                st.session_state.query_error = str(exc)
                st.session_state.last_df = None
            else:
                st.session_state.query_error = None
                st.session_state.last_df = df

        if st.session_state.get("query_error"):
            st.error(f"Failed to query database: {st.session_state.query_error}")
        else:
            df = st.session_state.get("last_df")
            if df is not None and not df.empty:
                st.dataframe(df, width="stretch")
            elif df is not None and df.empty:
                st.info("No rows found in price_logs.")

    with tab_charts:
        st.subheader("Basic charts")
        df = st.session_state.get("last_df")
        if df is None:
            st.info("Load data to see charts.")
            return
        if df.empty:
            st.info("No rows found in price_logs.")
            return

        df_chart = df.copy()
        df_chart["published_date"] = pd.to_datetime(
            df_chart.get("published_date"), errors="coerce"
        )

        st.markdown("**Price distribution (total_price_vnd)**")
        price_series = df_chart["total_price_vnd"].dropna()
        if not price_series.empty:
            price_bins = pd.cut(price_series, bins=20)
            price_counts = price_bins.value_counts().sort_index()
            price_df = price_counts.rename_axis("bucket").reset_index(name="count")
            price_df["bucket"] = price_df["bucket"].astype(str)
            st.bar_chart(price_df.set_index("bucket"))
        else:
            st.info("No price data available for chart.")

        st.markdown("**Area distribution (area_m2)**")
        area_series = df_chart["area_m2"].dropna()
        if not area_series.empty:
            area_bins = pd.cut(area_series, bins=20)
            area_counts = area_bins.value_counts().sort_index()
            area_df = area_counts.rename_axis("bucket").reset_index(name="count")
            area_df["bucket"] = area_df["bucket"].astype(str)
            st.bar_chart(area_df.set_index("bucket"))
        else:
            st.info("No area data available for chart.")

        st.markdown("**Top locations by listings**")
        if "location" in df_chart.columns:
            location_counts = (
                df_chart["location"].fillna("Unknown").value_counts().head(10)
            )
            st.bar_chart(location_counts)
        else:
            st.info("Location column not available for chart.")

        st.markdown("**Average unit price by day**")
        price_by_day = (
            df_chart.dropna(subset=["published_date", "unit_price_m2"])
            .groupby(df_chart["published_date"].dt.date)["unit_price_m2"]
            .mean()
        )
        if not price_by_day.empty:
            st.line_chart(price_by_day)
        else:
            st.info("Not enough data to compute unit price by day.")


if __name__ == "__main__":
    main()
