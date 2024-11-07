import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

import streamlit as st

# Configure page settings
st.set_page_config(page_title="S3 Bucket Manager", page_icon="🪣", layout="wide")

# Constants
API_BASE_URL = "http://127.0.0.1:8000"  # Update with your actual API base URL

# Initialize session state
if "token" not in st.session_state:
    st.session_state.token = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def login_user(username: str, password: str) -> bool:
    """Handle user login and token generation."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/token", data={"username": username, "password": password}
        )
        if response.status_code == 200:
            token_data = response.json()
            st.session_state.token = token_data["access_token"]
            st.session_state.authenticated = True
            return True
        return False
    except requests.RequestException as e:
        st.error(f"Login failed: {str(e)}")
        return False


def get_auth_headers() -> Dict[str, str]:
    """Get headers with authentication token."""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def make_api_request(
    endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Makes authenticated API requests and handles responses."""
    if not st.session_state.authenticated:
        st.error("Please log in first")
        return {}

    url = f"{API_BASE_URL}{endpoint}"
    headers = get_auth_headers()

    try:
        with st.spinner("Processing request..."):
            if method == "GET":
                response = requests.get(url, params=params, headers=headers)
            elif method == "POST":
                response = requests.post(url, params=params, headers=headers)

            if response.status_code == 401:
                st.session_state.authenticated = False
                st.session_state.token = None
                st.error("Session expired. Please log in again.")
                return {}

            response.raise_for_status()
            return response.json()
    except requests.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


def login_form():
    """Render login form."""
    st.header("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if login_user(username, password):
                st.success("Successfully logged in!")
                st.rerun()
            else:
                st.error("Invalid credentials")


def render_sidebar():
    st.sidebar.title("S3 Bucket Manager")
    st.sidebar.markdown("---")

    # Authentication status
    if st.session_state.authenticated:
        st.sidebar.success("🟢 Authenticated")
        if st.sidebar.button("Logout"):
            st.session_state.token = None
            st.session_state.authenticated = False
            st.rerun()
    else:
        st.sidebar.error("🔴 Not authenticated")

    # API Status
    try:
        requests.get(API_BASE_URL + "/buckets/")
        st.sidebar.success("🟢 API Connected")
    except requests.RequestException:
        st.sidebar.error("🔴 API Unavailable")

    st.sidebar.markdown("---")
    st.sidebar.info(
        """
    This application allows you to:
    - List all S3 buckets
    - Create new buckets
    - View bucket details
    - Create buckets with folders
    """
    )


def list_buckets_tab():
    st.header("List Buckets")

    if st.button("Refresh Bucket List"):
        response = make_api_request("/buckets/")
        if response:
            st.success("Successfully retrieved buckets!")
            st.json(response)


def create_bucket_tab():
    st.header("Create Bucket")

    with st.form("create_bucket_form"):
        bucket_name = st.text_input("Bucket Name (optional)")
        region = st.selectbox(
            "Region",
            ["us-east-1", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1"],
            index=0,
        )

        submit_button = st.form_submit_button("Create Bucket")

        if submit_button:
            params = {"region": region}
            if bucket_name:
                params["bucket_name"] = bucket_name

            response = make_api_request("/buckets/create", method="POST", params=params)
            if response:
                st.success("Bucket created successfully!")
                st.json(response)


def bucket_details_tab():
    st.header("Bucket Details")

    bucket_name = st.text_input("Enter Bucket Name")
    if bucket_name and st.button("Get Details"):
        response = make_api_request(f"/buckets/{bucket_name}")
        if response:
            st.success(f"Retrieved details for bucket: {bucket_name}")
            st.json(response)


def create_bucket_with_folder_tab():
    st.header("Create Bucket with Folder")

    with st.form("create_bucket_with_folder_form"):
        bucket_name = st.text_input("Bucket Name (optional)")
        region = st.selectbox(
            "Region",
            ["us-east-1", "us-west-1", "us-west-2", "eu-west-1", "eu-central-1"],
            index=0,
        )
        folder_name = st.text_input("Folder Name", value="new-folder/")

        submit_button = st.form_submit_button("Create Bucket with Folder")

        if submit_button:
            params = {"region": region, "folder_name": folder_name}
            if bucket_name:
                params["bucket_name"] = bucket_name

            response = make_api_request(
                "/buckets/create-with-folder", method="POST", params=params
            )
            if response:
                st.success("Bucket and folder created successfully!")
                st.json(response)


def main():
    st.title("S3 Bucket Management")

    # Render sidebar
    render_sidebar()

    # Show login form if not authenticated
    if not st.session_state.authenticated:
        login_form()
        return

    # Main content tabs (only shown when authenticated)
    tabs = st.tabs(
        ["List Buckets", "Create Bucket", "Bucket Details", "Create with Folder"]
    )

    with tabs[0]:
        list_buckets_tab()

    with tabs[1]:
        create_bucket_tab()

    with tabs[2]:
        bucket_details_tab()

    with tabs[3]:
        create_bucket_with_folder_tab()


if __name__ == "__main__":
    main()
