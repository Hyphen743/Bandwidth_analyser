"""Minimal Streamlit account gate used by the existing app pages."""

from __future__ import annotations

import streamlit as st

from accounts import AccountError, authenticate, create_account
from db.repository import DatabaseRepository


def require_account(repo: DatabaseRepository) -> bool:
    if st.session_state.get("account_id"):
        return True
    st.title("Bandwidth Analyzer")
    st.caption("Sign in to continue to your network dashboard.")
    sign_in, sign_up = st.tabs(["Sign In", "Sign Up"])
    with sign_in:
        with st.form("account_signin"):
            username = st.text_input("Username", key="signin_username")
            password = st.text_input("Password", type="password", key="signin_password")
            submit = st.form_submit_button("Sign In", type="primary")
        if submit:
            user = authenticate(username, password, repo)
            if user:
                st.session_state.update(user)
                st.rerun()
            st.error("Username or password is incorrect.")
    with sign_up:
        with st.form("account_signup"):
            username = st.text_input("Username", key="signup_username")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
            submit = st.form_submit_button("Create Account", type="primary")
        if submit:
            if password != confirm:
                st.error("The passwords do not match.")
            else:
                try:
                    st.session_state.update(create_account(username, password, repo))
                    st.rerun()
                except AccountError as exc:
                    st.error(str(exc))
    return False


def render_logout() -> None:
    st.caption(f"Signed in as **{st.session_state.get('username', 'Account')}**")
    if st.button("Sign Out", key="account_signout"):
        for key in ("account_id", "username", "friend_code", "collector_token"):
            st.session_state.pop(key, None)
        st.rerun()
