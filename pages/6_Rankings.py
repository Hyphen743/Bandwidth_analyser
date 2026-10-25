"""Application/device leaderboards and directional account friend rankings."""

from __future__ import annotations

import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from accounts import (
    AccountError, add_friend, create_collector_token, get_friend_code,
    get_rankings, list_friends, remove_friend,
)
from analytics.ranking import RankingAnalytics
from db.repository import DatabaseRepository
from shared_rankings import SharedRankingError, SharedRankingStore
from ui.common import download_csv_button, setup_page

st.set_page_config(page_title="Rankings & Shifts", page_icon="🏆", layout="wide")


def _deployment_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def _render_account_friend_controls(repo: DatabaseRepository, account_id: int) -> None:
    friend_code = get_friend_code(account_id, repo)
    st.markdown("**Your friend code**")
    st.caption("Share this code so someone can add you. They will not see your usage unless you add their code too.")
    st.code(friend_code, language=None)  # Streamlit's code block includes a copy button.

    with st.form("add_account_friend", clear_on_submit=True):
        code = st.text_input("Enter friend's code", max_chars=64)
        submitted = st.form_submit_button("Add Friend", type="primary")
    if submitted:
        try:
            username = add_friend(account_id, code, repo)
            st.success(f"Added {username}. They can see your metrics only if they add your friend code too.")
            st.rerun()
        except AccountError as exc:
            st.error(str(exc))

    friends = list_friends(account_id, repo)
    if friends:
        with st.expander("Friends you follow", expanded=False):
            for friend in friends:
                left, right = st.columns([4, 1])
                left.write(friend["username"])
                if right.button("Remove", key=f"remove_friend_{friend['account_id']}"):
                    remove_friend(account_id, friend["account_id"], repo)
                    st.rerun()

    st.markdown("**Connect this computer's local collector**")
    st.caption("The web page cannot read laptop traffic by itself. Run the local agent on each computer whose real usage should be shared.")
    if st.button("Create / rotate collector token", key="make_collector_token"):
        st.session_state["collector_token"] = create_collector_token(account_id, repo)
    token = st.session_state.get("collector_token")
    if token:
        st.code(token, language=None)
        st.caption("Copy and store this secret securely. It is shown only in this signed-in session; rotating it disables the previous token.")
        backend_url = st.text_input(
            "Collector ingestion URL",
            value=_deployment_setting("BANDWIDTH_API_URL"),
            placeholder="https://your-api-host/api/v1/usage",
            key="collector_backend_url",
        )
        st.code(f'python collector/friend_agent.py --backend-url "{backend_url}" --token "{token}"', language="powershell")
        st.caption("Collector uploads require HTTPS outside localhost. This app does not expose a local data API.")


def _render_shared_account_friend_controls(
    shared: SharedRankingStore,
    repo: DatabaseRepository,
    account_id: int,
    username: str,
) -> None:
    friend_code = get_friend_code(account_id, repo)
    shared.register_account(friend_code, username)
    st.markdown("**Your friend code**")
    st.caption("Share this code so someone can add you. Friendships are one-way; each person must add the other's code to see both rankings.")
    st.code(friend_code, language=None)

    with st.form("shared_add_account_friend", clear_on_submit=True):
        code = st.text_input("Enter friend's code", max_chars=64)
        submitted = st.form_submit_button("Add Friend", type="primary")
    if submitted:
        try:
            friend_name = shared.add_friend(friend_code, code)
            st.success(f"Added {friend_name}. Their usage appears after their collector sends samples.")
            st.rerun()
        except SharedRankingError as exc:
            st.error(str(exc))

    friends = shared.list_friends(friend_code)
    if friends:
        with st.expander("Friends you follow", expanded=False):
            for friend in friends:
                left, right = st.columns([4, 1])
                left.write(friend["username"])
                if right.button("Remove", key=f"shared_remove_friend_{friend['friend_code']}"):
                    shared.remove_friend(friend_code, friend["friend_code"])
                    st.rerun()

    st.markdown("**Connect this computer's local collector**")
    st.caption("The separate collector samples this computer's default-route adapter. It must keep running to send current usage.")
    if st.button("Create / rotate collector token", key="make_shared_collector_token"):
        token = create_collector_token(account_id, repo)
        try:
            shared.register_collector_token(friend_code, token)
        except SharedRankingError as exc:
            st.error(f"Token could not be registered with the shared service: {exc}")
            st.session_state.pop("shared_collector_token", None)
        else:
            st.session_state["shared_collector_token"] = token
    token = st.session_state.get("shared_collector_token")
    if token:
        st.code(token, language=None)
        st.caption("This secret is shown only in this signed-in session. Rotating the token disables the previous token.")
        backend_url = st.text_input(
            "Public HTTPS ingestion URL",
            value=_deployment_setting("BANDWIDTH_API_URL"),
            placeholder="https://your-api-host/api/v1/usage",
            key="shared_collector_backend_url",
        )
        if backend_url:
            st.code(f'python collector/friend_agent.py --backend-url "{backend_url}" --token "{token}"', language="powershell")
            st.caption("Run this command from a downloaded project folder on each computer you want ranked. Stop it with Ctrl+C.")
        else:
            st.info("Set BANDWIDTH_API_URL to your public HTTPS collector service URL before sharing this command.")


@st.fragment(run_every=15)
def _render_shared_friend_ranking(
    shared: SharedRankingStore,
    friend_code: str,
    start_ts: str,
    end_ts: str,
) -> None:
    try:
        rows = shared.rankings(friend_code, start_ts, end_ts)
    except SharedRankingError as exc:
        st.warning(f"Shared ranking refresh failed: {exc}")
        return
    if not rows:
        st.info("No friend accounts have been added yet.")
        return
    display = []
    for rank, item in enumerate(rows, start=1):
        display.append({
            "Rank": rank,
            "Username": item["username"],
            "Device": item.get("hostname", "Unknown device"),
            "Download usage (GB)": round(item["download_bytes"] / (1024 ** 3), 4) if item["download_bytes"] is not None else "—",
            "Upload usage (GB)": round(item["upload_bytes"] / (1024 ** 3), 4) if item["upload_bytes"] is not None else "—",
            "Total usage (GB)": round(item["total_bytes"] / (1024 ** 3), 4) if item["total_bytes"] is not None else "—",
            "Metric status": item["status"],
        })
    frame = pd.DataFrame(display)
    st.dataframe(frame, width="stretch", hide_index=True)
    st.caption("Auto-refreshes every 15 seconds. Each row is one device's actual default-adapter byte deltas. 'Stale' means no upload in 2 minutes; 'Unavailable' means no sample in the selected period.")
    download_csv_button(frame, filename="friend_bandwidth_ranking.csv", label="Export Friend Ranking")


@st.fragment(run_every=15)
def _render_friend_ranking(account_id: int, start_ts: str, end_ts: str, repo: DatabaseRepository) -> None:
    rows = get_rankings(account_id, start_ts, end_ts, repo)
    if not rows:
        st.info("No ranking data is available.")
        return
    display = []
    for rank, item in enumerate(rows, start=1):
        display.append({
            "Rank": rank,
            "Username": item["username"],
            "Download usage (GB)": round(item["download_bytes"] / (1024 ** 3), 4) if item["download_bytes"] is not None else "—",
            "Upload usage (GB)": round(item["upload_bytes"] / (1024 ** 3), 4) if item["upload_bytes"] is not None else "—",
            "Total usage (GB)": round(item["total_bytes"] / (1024 ** 3), 4) if item["total_bytes"] is not None else "—",
            "Metric status": item["status"],
        })
    frame = pd.DataFrame(display)
    st.dataframe(frame, width="stretch", hide_index=True)
    st.caption("Auto-refreshes every 15 seconds. Values are actual samples from each user's local collector. ‘Stale’ means no sample in the last 2 minutes; ‘Unavailable’ means no samples in the selected period.")
    download_csv_button(frame, filename="friend_bandwidth_ranking.csv", label="Export Friend Ranking")


def main() -> None:
    repo, filters = setup_page(
        title="Leaderboards & Period Rank Shifts",
        subtitle="Compare application and device history, and rank friends by their shared live usage.",
    )
    primary_repo = DatabaseRepository()
    account_value = st.session_state.get("account_id")
    if account_value is None:
        st.error("Your sign-in session is missing. Sign in again to open Rankings.")
        st.stop()
    account_id = int(account_value)
    username = str(st.session_state.get("username", "Account"))
    shared_url = _deployment_setting("BANDWIDTH_SHARED_DATABASE_URL")
    shared_store = SharedRankingStore(shared_url) if shared_url else None
    shared_error = None
    if shared_store is not None:
        try:
            shared_store.ensure_schema()
        except SharedRankingError as exc:
            shared_error = str(exc)
    start_ts, end_ts = filters["start_ts"], filters["end_ts"]
    engine = RankingAnalytics(repo)
    top_n = st.radio("Leaderboard Depth", [5, 10], index=1, horizontal=True)
    app_ranks = engine.get_app_rankings(start_ts, end_ts, limit=top_n)
    dev_ranks = engine.get_device_rankings(start_ts, end_ts, limit=top_n)
    tab_apps, tab_devices = st.tabs(["Applications Leaderboard", "Devices & Friends"])

    with tab_apps:
        st.subheader(f"Top {top_n} Applications")
        if not app_ranks.empty:
            display_apps = app_ranks[["current_rank", "rank_change", "app_name", "category", "total_gb"]].rename(columns={
                "current_rank": "Rank", "rank_change": "Shift", "app_name": "Application", "category": "Category", "total_gb": "Volume (GB)"
            })
            st.dataframe(display_apps, width="stretch", hide_index=True)
            download_csv_button(display_apps, filename="top_apps_rankings.csv", label="Export Apps Leaderboard")
        else:
            st.info("No application rankings available.")

    with tab_devices:
        st.subheader(f"Top {top_n} Endpoints")
        if not dev_ranks.empty:
            display_devs = dev_ranks[["current_rank", "rank_change", "hostname", "device_type", "total_gb"]].rename(columns={
                "current_rank": "Rank", "rank_change": "Shift", "hostname": "Device Hostname", "device_type": "Hardware Type", "total_gb": "Volume (GB)"
            })
            st.dataframe(display_devs, width="stretch", hide_index=True)
            download_csv_button(display_devs, filename="top_devices_rankings.csv", label="Export Devices Leaderboard")
        else:
            st.info("No device rankings available.")

        st.markdown("---")
        st.subheader("Friend Bandwidth Ranking")
        st.caption(f"Selected period: {start_ts} through {end_ts}.")
        if shared_store is None:
            st.warning(
                "Shared ranking is not configured. This local SQLite mode only shares accounts and samples "
                "with this same database; separate deployed services need BANDWIDTH_SHARED_DATABASE_URL."
            )
            _render_account_friend_controls(primary_repo, account_id)
            st.markdown("### Period usage ranking")
            _render_friend_ranking(account_id, start_ts, end_ts, primary_repo)
        elif shared_error:
            st.error(f"Shared ranking is unavailable: {shared_error}")
        else:
            try:
                _render_shared_account_friend_controls(shared_store, primary_repo, account_id, username)
                friend_code = get_friend_code(account_id, primary_repo)
                st.markdown("### Period usage ranking")
                _render_shared_friend_ranking(shared_store, friend_code, start_ts, end_ts)
            except SharedRankingError as exc:
                st.error(f"Shared ranking is unavailable: {exc}")


if __name__ == "__main__":
    main()
