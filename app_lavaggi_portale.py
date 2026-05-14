# -*- coding: utf-8 -*-
import html
import json
import re
import urllib.parse
from datetime import date, datetime
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ==========================================================
# 1. CONFIGURAZIONE E COSTANTI
# ==========================================================
st.set_page_config(
    page_title="FV WASH MANAGER",
    layout="wide",
    page_icon="🧼",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
FILE_MODELLI = BASE_DIR / "modelli_messaggi.json"
SHEET_ID = "16RUw8kcZRurs_LYP9WCGbbLiXZnHEhw_lLEsdlS5Zuc"
FOGLIO = st.secrets.get("google_sheet", {}).get("worksheet_name", "Lavaggi")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

if "df" not in st.session_state: st.session_state.df = None
if "dash_filter" not in st.session_state: st.session_state.dash_filter = "Tutti"
if "selected_idx" not in st.session_state: st.session_state.selected_idx = None

# ==========================================================
# 2. STILE CSS
# ==========================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp { background: #f8fafc; font-family: 'Inter', sans-serif; }
    
    .hero {
        background: linear-gradient(rgba(15,23,42,0.8), rgba(15,23,42,0.8)), 
                    url('https://images.unsplash.com/photo-1509391366360-2e959784a276?q=80&w=1600&auto=format&fit=crop');
        background-size: cover; background-position: center;
        padding: 50px 40px; border-radius: 24px; color: white; text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1); margin-bottom: 2rem;
    }
    
    .kpi-box {
        background: white; padding: 15px; border-radius: 18px; text-align: center;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.3s; margin-bottom: 10px;
    }
    .kpi-active { border: 2px solid #2563eb; background: #f0f7ff; transform: translateY(-5px); }
    .kpi-icon { font-size: 30px; margin-bottom: 5px; display: block; }
    .kpi-val { font-size: 24px; font-weight: 800; color: #1e293b; margin: 0; }
    .kpi-lab { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; }

    .status-container { padding: 10px; border-radius: 12px; font-weight: 800; text-align: center; margin-bottom: 5px; color: white; }
    .st-da-programmare { background-color: #94a3b8; }
    .st-avvisato { background-color: #3b82f6; }
    .st-confermato { background-color: #22c55e; }
    .st-fatto { background-color: #475569; }
    .st-annullato { background-color: #ef4444; }

    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }

    .card { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 25px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    
    /* Uniformità pulsanti filtri */
    .stButton>button { border-radius: 12px !important; font-weight: 700 !important; width: 100%; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 3. LOGICA DATI
# ==========================================================
@st.cache_resource(show_spinner=False)
def get_ws():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(FOGLIO)

def carica_dati():
    try:
        ws = get_ws()
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [re.sub(r"\s+", "", str(c)).strip() for c in df.columns]
        cols = ["Cliente", "Impianto", "DataLavaggio", "Orario", "Telefono", "EmailCliente", "Stato", 
                "Fornitore", "DataPromemoria", "DataPromemoria3gg", "DataWA30gg", "DataWA3gg", "Note", "EventoCalendarioCreato"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
        df["DataLavaggio_DT"] = pd.to_datetime(df["DataLavaggio"], errors="coerce", dayfirst=True).dt.date
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(lambda x: (x - date.today()).days if pd.notna(x) else None)
        return df
    except Exception as e:
        st.error(f"Errore: {e}"); return None

def salva_sheet(idx, mappa):
    try:
        ws = get_ws(); headers = ws.row_values(1)
        hdr_map = {re.sub(r"\s+", "", h).strip().lower(): i + 1 for i, h in enumerate(headers)}
        updates = []
        for k, v in mappa.items():
            col = hdr_map.get(k.lower())
            if col: updates.append({"range": gspread.utils.rowcol_to_a1(int(idx) + 2, col), "values": [[str(v)]]})
        if updates: ws.batch_update(updates, value_input_option="USER_ENTERED")
        return True
    except: return False

# ==========================================================
# 4. DASHBOARD E FILTRI
# ==========================================================
if st.session_state.df is None: st.session_state.df = carica_dati()
df = st.session_state.df

with st.sidebar:
    st.markdown("### 🧼 FV WASH MANAGER")
    pagina = st.radio("Navigazione", ["Dashboard", "Modelli Messaggi", "Calendario", "Impostazioni"])
    
    st.divider()
    st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)
    
    if st.button("🔄 Aggiorna Dati"): 
        st.session_state.df = carica_dati(); st.rerun()

if pagina == "Dashboard":
    st.markdown('<div class="hero"><h1>FV WASH MANAGER</h1><p>Controllo Operativo Interventi</p></div>', unsafe_allow_html=True)
    
    # --- LOGICA FILTRI ---
    df_tutti = df.sort_values(by="Cliente")
    df_conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
    df_urg = df[(df["GiorniMancanti"].between(0, 15)) & (df["Stato"].str.upper() != "CONFERMATO DA CLIENTE") & (df["Stato"].str.upper() != "FATTO")]
    df_comp = df[df["Stato"].str.upper() == "FATTO"]
    df_da_fare = df[(df["Stato"].str.upper() != "FATTO") & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")]
    df_annullati = df[df["Stato"].str.upper() == "ANNULLATO DA CLIENTE"]

    # --- KPI DASHBOARD ---
    cols_kpi = st.columns(6)
    filters = [("Tutti", "📋", len(df_tutti)), ("Confermati", "👍", len(df_conf)), ("Urgenze", "🔥", len(df_urg)), 
               ("Completati", "✅", len(df_comp)), ("Da Fare", "🛠️", len(df_da_fare)), ("Annullati", "❌", len(df_annullati))]

    for i, (name, icon, count) in enumerate(filters):
        with cols_kpi[i]:
            active = "kpi-active" if st.session_state.dash_filter == name else ""
            st.markdown(f'<div class="kpi-box {active}"><span class="kpi-icon">{icon}</span><p class="kpi-val">{count}</p><p class="kpi-lab">{name}</p></div>', unsafe_allow_html=True)
            if st.button(name, key=f"f_{name}", use_container_width=True):
                st.session_state.dash_filter = name; st.rerun()

    st.divider()

    # Selezione DataFrame
    if st.session_state.dash_filter == "Tutti": df_view = df_tutti
    elif st.session_state.dash_filter == "Confermati": df_view = df_conf
    elif st.session_state.dash_filter == "Urgenze": df_view = df_urg
    elif st.session_state.dash_filter == "Completati": df_view = df_comp
    elif st.session_state.dash_filter == "Da Fare": df_view = df_da_fare
    else: df_view = df_annullati

    mask_sospesi = (df_view["DataLavaggio"] == "") | (df_view["Stato"].str.upper().isin(["DA PROGRAMMARE", "ANNULLATO DA CLIENTE"]))
    df_attivi = df_view[~mask_sospesi]
    df_sospesi = df_view[mask_sospesi]

    col_l, col_r = st.columns([1, 1.8], gap="large")
    
    with col_l:
        st.markdown(f"### 📅 {st.session_state.dash_filter}")
        search = st.text_input("🔍 Cerca...", placeholder="Filtra Cliente...")
        if search:
            df_attivi = df_attivi[df_attivi["Cliente"].str.contains(search, case=False)]
            df_sospesi = df_sospesi[df_sospesi["Cliente"].str.contains(search, case=False)]
        
        # --- LISTA ATTIVI AGGIORNATA (MAIUSCOLO E SPAZIATURA) ---
        for idx, r in df_attivi.head(40).iterrows():
            data_str = str(r['DataLavaggio'])
            cliente_str = str(r['Cliente']).upper() # Tutto maiuscolo
            # Spaziatura ampia: 6 spazi tra data e cliente
            lbl = f"{data_str}      {cliente_str}" 
            st.button(lbl, key=f"sel_{idx}", use_container_width=True, on_click=lambda i=idx: st.session_state.update({"selected_idx": i}))
        
        if not df_sospesi.empty:
            with st.expander("📁 AREA SOSPESI / ANNULLATI", expanded=False):
                for idx, r in df_sospesi.iterrows():
                    cliente_sosp = str(r['Cliente']).upper()
                    lbl = f"[{r['Stato'] or '??'}]      {cliente_sosp}"
                    st.button(lbl, key=f"sel_{idx}", use_container_width=True, on_click=lambda i=idx: st.session_state.update({"selected_idx": i}))

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(f'<div class="card"><h2>{row["Cliente"]}</h2>', unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            new_cliente = c1.text_input("Nome Cliente", row["Cliente"])
            new_impianto = c2.text_input("Impianto", row["Impianto"])
            
            c3, c4, c5 = st.columns(3)
            default_date = row["DataLavaggio_DT"] if pd.notna(row["DataLavaggio_DT"]) else date.today()
            new_date = c3.date_input("Data Lavaggio", default_date, format="DD/MM/YYYY")
            new_ora = c4.text_input("Orario", row["Orario"])
            
            stati = ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO DA CLIENTE"]
            current_st = row["Stato"] if row["Stato"] in stati else "DA PROGRAMMARE"
            st_class = "st-da-programmare"
            if "AVVISATO" in current_st: st_class = "st-avvisato"
            elif "CONFERMATO" in current_st: st_class = "st-confermato"
            elif "FATTO" in current_st: st_class = "st-fatto"
            elif "ANNULLATO" in current_st: st_class = "st-annullato"
            
            with c5:
                st.markdown(f'<div class="status-container {st_class}">{current_st}</div>', unsafe_allow_html=True)
                new_st = st.selectbox("Stato", stati, index=stati.index(current_st), label_visibility="collapsed")
            
            if st.button("💾 AGGIORNA DATI CLIENTE", type="primary"):
                if salva_sheet(st.session_state.selected_idx, {"Cliente": new_cliente, "Impianto": new_impianto, "DataLavaggio": new_date.strftime("%d/%m/%Y"), "Stato": new_st}):
                    st.session_state.df = carica_dati(); st.rerun()

# (Resto del codice per Messaggi, Calendario, ecc. rimane invariato)
