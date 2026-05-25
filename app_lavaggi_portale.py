# -*- coding: utf-8 -*-

import re
import urllib.parse
import bcrypt
from datetime import date, datetime, timedelta

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


# ==========================================================
# 1. CONFIGURAZIONE BASE
# ==========================================================
st.set_page_config(
    page_title="FV Wash Manager",
    layout="wide",
    page_icon="🧼",
    initial_sidebar_state="expanded",
)

SHEET_ID = st.secrets.get("google_sheet", {}).get(
    "spreadsheet_id",
    "16RUw8kcZRurs_LYP9WCGbbLiXZnHEhw_lLEsdlS5Zuc",
)

FOGLIO_LAVAGGI = st.secrets.get("google_sheet", {}).get("worksheet_name", "Lavaggi")
FOGLIO_UTENTI = st.secrets.get("google_sheet", {}).get("users_worksheet_name", "Utenti")
FOGLIO_MODELLI = st.secrets.get("google_sheet", {}).get("models_worksheet_name", "Modelli")
FOGLIO_LOG = st.secrets.get("google_sheet", {}).get("log_worksheet_name", "Log")

SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ==========================================================
# 2. CSS
# ==========================================================
st.markdown("""
<style>
    .stApp {
        background: #f8fafc;
    }

    .hero {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white;
        padding: 26px 30px;
        border-radius: 18px;
        margin-bottom: 22px;
    }

    .hero h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 800;
    }

    .hero p {
        margin: 8px 0 0 0;
        color: #e2e8f0;
        font-size: 15px;
    }

    [data-testid="stSidebar"] {
        background: #0f172a;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown {
        color: #f8fafc !important;
    }

    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] .stTextInput input {
        color: #0f172a !important;
        background: #ffffff !important;
    }

    [data-testid="stSidebar"] .stButton button,
    [data-testid="stSidebar"] .stDownloadButton button,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        font-weight: 800 !important;
        border-radius: 10px !important;
    }
