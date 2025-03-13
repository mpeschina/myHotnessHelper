import streamlit as st
import pandas as pd


@st.cache_data
def load_and_prepare_data(csv_file):
    """
    1) Reads the CSV
    2) Sorts by (game_id, date) to correctly compute diffs
    3) Calculates a 'views_diff' column for daily new views
    """
    df = pd.read_csv(csv_file, parse_dates=["date"])
    df["name"] = df["name"].str.replace("'", "", regex=False)
    df.sort_values(by=["game_id", "date"], inplace=True)
    df["views_diff"] = df.groupby("game_id")["views"].diff().fillna(0)

    # Filter out any rows before that cutoff date
    cutoff_date = df["date"].min() + pd.Timedelta(days=1)
    df = df[df["date"] >= cutoff_date]
    return df



def safe_get_user_data(df):
    # Get min and max dates
    min_date = df["date"].min()
    max_date = df["date"].max()

    # Two separate date pickers for start and end date
    start_date = st.sidebar.date_input("Start Date", min_date, min_value=min_date, max_value=max_date)
    end_date = st.sidebar.date_input("End Date", max_date, min_value=min_date, max_value=max_date)

    # Ensure start_date is before or equal to end_date
    if start_date > end_date:
        st.sidebar.error("Start date cannot be after end date. Please adjust your selection.")

    return start_date, end_date




def graph_section():
    st.title("BGG Hotness Daily Views – By Game or By Rank")

    # --- Load Data ---
    csv_file_path = "bgg_hotness_history.csv"  # Update path as needed
    df = load_and_prepare_data(csv_file_path)

    # --- Sidebar Controls ---
    # 1) Choose a mode: "By Game" or "By Rank"
    mode = st.sidebar.radio(
        "View Mode",
        options=["By Game", "By Rank"],
        help="Choose whether to compare daily new views by game or by rank."
    )

    # Add checkboxes for Nerdlab games
    st.sidebar.subheader("Highlight Your Games")
    highlight_final_titan = st.sidebar.checkbox("Final Titan", value=True)
    highlight_mindbug = st.sidebar.checkbox("Mindbug", value=False)
    highlight_agent_avenue = st.sidebar.checkbox("Agent Avenue", value=False)

    # Collect your highlighted games into a list
    highlighted_games = []
    if highlight_final_titan:
        highlighted_games.append("Final Titan")
    if highlight_mindbug:
        highlighted_games.append("Mindbug")
    if highlight_agent_avenue:
        highlighted_games.append("Agent Avenue")

    start_date, end_date = safe_get_user_data(df)
    
    # Filter by the date range
    mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
    df_filtered = df[mask].copy()

    if mode == "By Game":
        # Multi-select of game names
        #all_games_list = sorted(df["name"].unique().tolist())
        all_games_list = df.drop_duplicates(subset="name").sort_values("rank")["name"].tolist()
        most_recent_games = df[df["date"] == pd.to_datetime(end_date)].drop_duplicates(subset="name").sort_values("rank")["name"].tolist()

        if "selected_games" not in st.session_state:
            st.session_state.selected_games = most_recent_games[:7]

        # Add Select All and Select None buttons
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            if st.button("Select All"):
                st.session_state.selected_games = all_games_list
            if st.button("None"):
                st.session_state.selected_games = []
        if col2.button("TOP 7 (at end date)"):
            st.session_state.selected_games = most_recent_games[:7]
        if col3.button("TOP 15 (at end date)"):
            st.session_state.selected_games = most_recent_games[:15]

        selected_games = st.sidebar.multiselect(
            "Select one or more games",
            options=all_games_list,
            default=st.session_state.selected_games,
            help="Pick multiple games to compare daily new views."
        )

        selected_games.extend(highlighted_games)
        if selected_games:
            df_selected = df_filtered[df_filtered["name"].isin(selected_games)].copy()

            # Pivot so each selected game is its own column
            pivoted = df_selected.pivot_table(
                index="date",
                columns="name",
                values="views_diff",
                aggfunc="sum"
            ).fillna(0)

            st.subheader("Number of Page Views per Game")

            if (highlighted_games):
                colors = []
                for col in pivoted.columns:
                    if col in highlighted_games:
                        colors.append("#FF0000")  # Highlighted games in red
                    else:
                        colors.append("#AAAAAA")  # Normal games in gray
                st.line_chart(data=pivoted, height=450, use_container_width=True, color=colors)
            else:
                st.line_chart(data=pivoted, height=450, use_container_width=True)

            # Optional bar chart
            #st.subheader("Number of Page Views per game")
            #st.bar_chart(pivoted, height=350)

        else:
            st.warning("No games selected. Please pick at least one game from the sidebar.")

    else:
        import altair as alt

        # Multi-select of rank values
        all_ranks = sorted(df["rank"].unique().tolist())
        if "selected_ranks" not in st.session_state:
            st.session_state.selected_ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Add Select All and Select None buttons
        col1, col2, col3 = st.sidebar.columns(3)
        if col1.button("Select All"):
            st.session_state.selected_ranks = all_ranks
        if col2.button("Select None"):
            st.session_state.selected_ranks = []
        if col3.button("Select Default"):
            st.session_state.selected_ranks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        selected_ranks = st.sidebar.multiselect(
            "Select one or more ranks",
            options=all_ranks,
            default=st.session_state.selected_ranks,
            help="Pick multiple ranks to compare daily new views.",
        )

        if selected_ranks:
            # Filter data by selected ranks
            df_selected = df_filtered[df_filtered["rank"].isin(selected_ranks)].copy()

            # Ensure all highlighted games are included in the data
            highlighted_data = df_filtered[df_filtered["name"].isin(highlighted_games)]
            df_selected = pd.concat([df_selected, highlighted_data]).drop_duplicates()

            if highlighted_games:
                df_selected["highlight"] = df_selected["name"].apply(
                    lambda x: "Highlighted" if x in highlighted_games else "Normal"
                )
            else:
                df_selected["highlight"] = df_selected["rank"].astype(str)  # Default color for each rank


            # Prepare Altair chart
            st.subheader("Number of Page Views per Rank")

            # Define color encoding based on highlighted or default state
            if highlighted_games:
                color_encoding = alt.Color(
                    "highlight:N",
                    scale=alt.Scale(
                        domain=["Highlighted", "Normal"],
                        range=["red", "gray"],
                    ),
                    legend=alt.Legend(title="Highlight Status"),
                )
            else:
                color_encoding = alt.Color(
                    "rank:N",  # Use rank as the default color
                    legend=alt.Legend(title="Rank"),
                )

            chart = (
                alt.Chart(df_selected[df_selected["rank"].isin(selected_ranks)])
                .mark_line()
                .encode(
                    x="date:T",
                    y="views_diff:Q",
                    color=color_encoding,
                    detail="rank:N",  # Ensure separate lines for each rank
                    tooltip=["date:T", "rank:N", "views_diff:Q"],
                )
                .properties(width=700, height=450)
            )

            # Overlay: Plot highlighted games separately
            highlight_chart = (
                alt.Chart(df_selected[df_selected["name"].isin(highlighted_games)])
                .mark_line(strokeWidth=3, color="red")  # Thicker red line for visibility
                .encode(
                    x="date:T",
                    y="views_diff:Q",
                    detail="name:N",  # Each game gets its own line
                    tooltip=["date:T", "rank:N", "views_diff:Q", "name:N"],
                )
            )
            final_chart = chart + highlight_chart


            st.altair_chart(final_chart, use_container_width=True)
        else:
            st.warning("No ranks selected. Please pick at least one rank from the sidebar.")




def hotness_table_section():
    # --- NEW SECTION: Detailed Table for a Single Day ---
    st.header("View of old Hotness List")

    # --- Load Data ---
    csv_file_path = "bgg_hotness_history.csv"  # Update path as needed
    df = load_and_prepare_data(csv_file_path)

    # Let user pick a SINGLE day for a table of the hotness list
    # Default to the earliest day in the dataset
    single_day = st.date_input(
        "Pick a single day",
        value=df["date"].max(),
        min_value=df["date"].min(),
        max_value=df["date"].max(),
        key="single_day_detail"
    )

    # Filter to that one date
    day_mask = df["date"] == pd.to_datetime(single_day)
    df_single_day = df[day_mask].copy()

    # Sort by rank
    df_single_day.sort_values(by="rank", inplace=True)

    if df_single_day.empty:
        st.warning(f"No data found for {single_day}.")
    else:
        st.write(f"Hotness for {single_day}:")
        # Show whatever columns you want. Here we show rank, name, total views, daily views
        st.dataframe(
            df_single_day[
                ["rank", "game_id", "name", "year", "views", "views_diff"]
            ]
        )

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    graph_section()
    hotness_table_section()
