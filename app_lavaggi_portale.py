# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import json
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials

# ==========================================================
# 1. CONFIGURAZIONE BASE
# ==========================================================
st.set_page_config(
    page_title="FV Wash Manager Platinum+",
    layout="wide",
    page_icon="🧼",
    initial_sidebar_state="expanded"
)

# Configurazione percorsi e Google Sheets
BASE_DIR = Path(__file__).resolve().parent
FILE_MODELLI = BASE_DIR / "modelli_messaggi.json"
FOGLIO = "Lavaggi"
SHEET_ID = st.secrets.get("google_sheet", {}).get("spreadsheet_id", "")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit" if SHEET_ID else ""

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# CSS Personalizzato
st.markdown("""
<style>
    .kpi-box { background: #ffffff; padding: 20px; border-radius: 15px; border: 1px solid #e2e8f0; text-align: center; transition: 0.3s; }
    .kpi-active { border: 2px solid #2563eb; background: #eff6ff; }
    .kpi-icon { font-size: 24px; margin-bottom: 10px; }
    .kpi-val { font-size: 28px; font-weight: 800; color: #1e293b; margin: 0; }
    .kpi-lab { font-size: 14px; color: #64748b; font-weight: 600; margin: 0; }
    .card { background: white; padding: 25px; border-radius: 20px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    .status-container { padding: 8px 15px; border-radius: 10px; font-weight: 700; text-align: center; font-size: 13px; }
    .st-da-programmare { background: #f1f5f9; color: #475569; }
    .st-avvisato { background: #fef3c7; color: #92400e; }
    .st-confermato { background: #dcfce7; color: #166534; }
    .st-fatto { background: #dbeafe; color: #1e40af; }
    .st-annullato { background: #fee2e2; color: #991b1b; }
    .hero { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: white; padding: 30px; border-radius: 20px; margin-bottom: 25px; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 2. FUNZIONI CORE (DATI E AUTH)
# ==========================================================

@st.cache_resource
def get_worksheet():
    if not SHEET_ID:
        st.error("Manca spreadsheet_id nei secrets")
        st.stop()
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(FOGLIO)

def carica_dati():
    try:
        ws = get_worksheet()
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # Pulizia e conversioni
        df["DataLavaggio_DT"] = pd.to_datetime(df["DataLavaggio"], format="%d/%m/%Y", errors="coerce").dt.date
        df["Task_Due_DT"] = pd.to_datetime(df["Task_Due"], format="%d/%m/%Y", errors="coerce").dt.date
        
        def calc_giorni(d):
            if pd.isna(d): return 999
            return (d - date.today()).days
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(calc_giorni)
        return df
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return pd.DataFrame()

def salva_sheet(index, updates):
    try:
        ws = get_worksheet()
        # gspread usa base 1 e ha l'intestazione
        row_idx = int(index) + 2 
        headers = ws.row_values(1)
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                ws.update_cell(row_idx, col_idx, str(value))
        return True
    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False

# ==========================================================
# 3. STATO SESSIONE E LOGIN
# ==========================================================
if "loggato" not in st.session_state:
    st.session_state.update({
        "loggato": False, "utente": None, "ruolo": "ospite",
        "df": carica_dati(), "selected_idx": None, "dash_filter": "Tutti"
    })

def login(user, pwd):
    utenti = st.secrets.get("users", {})
    if user in utenti and utenti[user]["password"] == pwd:
        st.session_state.update({"loggato": True, "utente": user, "ruolo": utenti[user]["role"]})
        st.rerun()
    else:
        st.error("Credenziali errate")

def logout():
    st.session_state.update({"loggato": False, "utente": None, "ruolo": "ospite"})
    st.rerun()

# Permessi
is_admin = st.session_state.ruolo == "admin"
can_edit_client = st.session_state.ruolo in ["admin", "supervisor"]
can_send_comms = st.session_state.ruolo in ["admin", "supervisor"]

# Caricamento Modelli
if not FILE_MODELLI.exists():
    with open(FILE_MODELLI, "w") as f:
        json.dump({"mail_30_ogg": "", "mail_30_txt": "", "wa_30_txt": ""}, f)
with open(FILE_MODELLI, "r", encoding="utf-8") as f:
    st.session_state.modelli = json.load(f)

# ==========================================================
# 5. SIDEBAR E NAVIGAZIONE
# ==========================================================
with st.sidebar:
    st.markdown("### 🧼 FV WASH MANAGER")
    if not st.session_state.loggato:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("🔐 Login"): login(u, p)
    else:
        st.success(f"User: {st.session_state.utente}")
        if st.button("🔓 Logout"): logout()

    st.divider()
    lista_pagine = ["Dashboard", "Modelli Messaggi", "Fornitori", "Calendario"]
    if is_admin: lista_pagine += ["Log di Sistema", "Gestione Utenti"]
    lista_pagine.append("Impostazioni")
    pagina = st.radio("Navigazione", lista_pagine)
    
    st.divider()
    # --- VISIBILE SOLO ADMIN ---
    if is_admin:
        st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)
        st.write("")
        
    if st.button("🔄 Aggiorna Dati"):
        st.session_state.df = carica_dati()
        st.rerun()

# ==========================================================
# 8. DASHBOARD
# ==========================================================
df = st.session_state.df

if pagina == "Dashboard":
    st.markdown('<div class="hero"><h1>FV WASH MANAGER</h1><p>Controllo Operativo Interventi</p></div>', unsafe_allow_html=True)

    # KPI e Filtri Rapidi
    df_tutti = df.sort_values(by="Cliente")
    df_conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
    df_urg = df[(df["GiorniMancanti"].between(0, 15)) & (df["Stato"].str.upper() != "FATTO")]
    df_comp = df[df["Stato"].str.upper() == "FATTO"]
    df_da_fare = df[(df["Stato"].str.upper() != "FATTO") & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")]

    k_cols = st.columns(5)
    kpis = [("Tutti", "📋", len(df_tutti)), ("Confermati", "👍", len(df_conf)), ("Urgenze", "🔥", len(df_urg)), ("Completati", "✅", len(df_comp)), ("Da Fare", "🛠️", len(df_da_fare))]
    
    for i, (name, icon, count) in enumerate(kpis):
        with k_cols[i]:
            act = "kpi-active" if st.session_state.dash_filter == name else ""
            st.markdown(f'<div class="kpi-box {act}"><p class="kpi-val">{count}</p><p class="kpi-lab">{name}</p></div>', unsafe_allow_html=True)
            if st.button(name, key=f"f_{name}", use_container_width=True):
                st.session_state.dash_filter = name
                st.rerun()

    st.divider()

    # Logica Filtro
    if st.session_state.dash_filter == "Tutti": df_view = df_tutti
    elif st.session_state.dash_filter == "Confermati": df_view = df_conf
    elif st.session_state.dash_filter == "Urgenze": df_view = df_urg
    elif st.session_state.dash_filter == "Completati": df_view = df_comp
    else: df_view = df_da_fare

    col_l, col_r = st.columns([1, 1.8], gap="large")
    
    with col_l:
        st.markdown(f"### 📅 {st.session_state.dash_filter}")
        search = st.text_input("🔍 Cerca cliente...")
        if search:
            df_view = df_view[df_view["Cliente"].str.contains(search, case=False)]
        
        for idx, r in df_view.head(30).iterrows():
            dot = "🟢" if r["Stato"] == "FATTO" else "🟡" if r["GiorniMancanti"] < 7 else "⚪"
            lbl = f"{dot} {r['DataLavaggio']} - {str(r['Cliente']).upper()}"
            if st.button(lbl, key=f"sel_{idx}", use_container_width=True):
                st.session_state.selected_idx = idx

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(f'<div class="card"><h2 style="margin-top:0;">{row["Cliente"]}</h2>', unsafe_allow_html=True)
            
            # --- STORICO INVII (RIPRISTINATO) ---
            st.markdown("#### 📡 Storico Invii Promemoria")
            i1, i2, i3, i4 = st.columns(4)
            
            def val_invio(v):
                return str(v).strip() if pd.notna(v) and str(v).strip() else "—"
                
            box_style = "background:#f8fafc; padding:12px 8px; border-radius:12px; border:1px solid #e2e8f0; text-align:center; line-height:1.4;"
            lbl_style = "font-size:11px; color:#64748b; font-weight:700; text-transform:uppercase;"
            val_style = "font-size:14px; font-weight:800; color:#0f172a;"
            
            i1.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>Mail 30gg</span><br/><span style='{val_style}'>{val_invio(row.get('DataPromemoria',''))}</span></div>", unsafe_allow_html=True)
            i2.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>WA 30gg</span><br/><span style='{val_style}'>{val_invio(row.get('DataWA30gg',''))}</span></div>", unsafe_allow_html=True)
            i3.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>Mail 3gg</span><br/><span style='{val_style}'>{val_invio(row.get('DataPromemoria3gg',''))}</span></div>", unsafe_allow_html=True)
            i4.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>WA 3gg</span><br/><span style='{val_style}'>{val_invio(row.get('DataWA3gg',''))}</span></div>", unsafe_allow_html=True)
            
            st.write("")
            
            # Campi Editabili
            c1, c2 = st.columns(2)
            n_cl = c1.text_input("Nome Cliente", row["Cliente"], disabled=not can_edit_client)
            n_im = c2.text_input("Impianto", row["Impianto"], disabled=not can_edit_client)
            
            c3, c4, c5 = st.columns(3)
            d_dt = row["DataLavaggio_DT"] if pd.notna(row["DataLavaggio_DT"]) else date.today()
            n_dt = c3.date_input("Data Lavaggio", d_dt, format="DD/MM/YYYY", disabled=not can_edit_client)
            n_or = c4.text_input("Orario", row["Orario"], disabled=not can_edit_client)
            
            st_list = ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO DA CLIENTE"]
            curr_st = row["Stato"] if row["Stato"] in st_list else "DA PROGRAMMARE"
            n_st = c5.selectbox("Stato", st_list, index=st_list.index(curr_st), disabled=not can_edit_client)
            
            n_note = st.text_area("Note", row["Note"], height=70, disabled=not can_edit_client)

            if st.button("💾 AGGIORNA DATI CLIENTE", type="primary", disabled=not can_edit_client):
                if salva_sheet(st.session_state.selected_idx, {
                    "Cliente": n_cl, "Impianto": n_im, "DataLavaggio": n_dt.strftime("%d/%m/%Y"),
                    "Orario": n_or, "Stato": n_st, "Note": n_note
                }):
                    st.success("Dati aggiornati!")
                    st.session_state.df = carica_dati()
                    st.rerun()

            st.divider()
            st.markdown("#### 🚀 Invio Comunicazioni")
            ca, cb = st.columns(2)
            if ca.button("✉️ Invia Email Promemoria", use_container_width=True, disabled=not can_send_comms):
                st.info("Funzione Email in fase di attivazione...")
            if cb.button("💬 Invia WhatsApp Promemoria", use_container_width=True, disabled=not can_send_comms):
                st.info("Funzione WhatsApp in fase di attivazione...")
            
            st.markdown('</div>', unsafe_allow_html=True)

# Altre pagine (placeholder per brevità)
elif pagina == "Modelli Messaggi":
    st.title("Gestione Modelli")
    # ... codice modelli ...
