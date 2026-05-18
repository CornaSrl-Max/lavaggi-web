# -*- coding: utf-8 -*-
import html
import json
import re
import urllib.parse
from datetime import date, datetime
from pathlib import Path

from passlib.hash import bcrypt
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ==========================================================
# 1. CONFIGURAZIONE E ACCESSO
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
UTENTI_SHEET_NAME = "Utenti"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Stato sessione autenticazione / ruoli
if "loggato" not in st.session_state:
    st.session_state.loggato = False
if "utente" not in st.session_state:
    st.session_state.utente = None
if "ruolo" not in st.session_state:
    st.session_state.ruolo = "guest"  # guest, user, admin

if "df" not in st.session_state:
    st.session_state.df = None
if "dash_filter" not in st.session_state:
    st.session_state.dash_filter = "Tutti"
if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = None

# ==========================================================
# 2. FUNZIONI AUTENTICAZIONE / UTENTI
# ==========================================================
def hash_pw(pw: str) -> str:
    return bcrypt.hash(pw)

def check_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(pw, hashed)
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def get_ws():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(FOGLIO)

@st.cache_resource(show_spinner=False)
def get_ws_utenti():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(UTENTI_SHEET_NAME)

@st.cache_data(show_spinner=False)
def carica_utenti():
    try:
        ws_u = get_ws_utenti()
        df_u = pd.DataFrame(ws_u.get_all_records())
        if not {"username", "password_hash", "ruolo"}.issubset(df_u.columns):
            st.error("Foglio 'Utenti' non configurato correttamente.")
            return pd.DataFrame()
        df_u["username"] = df_u["username"].astype(str).str.strip()
        df_u.set_index("username", inplace=True)
        return df_u
    except Exception as e:
        st.error(f"Errore caricamento utenti: {e}")
        return pd.DataFrame()

def login(username: str, password: str):
    utenti = carica_utenti()
    if utenti.empty:
        st.error("Nessun utente configurato.")
        return
    username = (username or "").strip()
    if username not in utenti.index:
        st.error("Credenziali non valide")
        return
    row = utenti.loc[username]
    if not check_pw(password, row["password_hash"]):
        st.error("Credenziali non valide")
        return
    st.session_state.loggato = True
    st.session_state.utente = username
    st.session_state.ruolo = row["ruolo"]
    st.success(f"Accesso eseguito come {username} ({row['ruolo']})")
    st.rerun()

def logout():
    st.session_state.loggato = False
    st.session_state.utente = None
    st.session_state.ruolo = "guest"
    st.rerun()

# ==========================================================
# 3. STILE CSS
# ==========================================================
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp { background: #f8fafc; font-family: 'Inter', sans-serif; }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# 4. LOGICA DATI
# ==========================================================
def carica_dati():
    try:
        ws = get_ws()
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [re.sub(r"\s+", "", str(c)).strip() for c in df.columns]
        cols = [
            "Cliente","Impianto","DataLavaggio","Orario","Telefono","EmailCliente",
            "Stato","Fornitore","DataPromemoria","DataPromemoria3gg","DataWA30gg",
            "DataWA3gg","Note","EventoCalendarioCreato","Task_Rem","Task_Due",
        ]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df["DataLavaggio_DT"] = pd.to_datetime(df["DataLavaggio"], errors="coerce", dayfirst=True).dt.date
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(lambda x: (x - date.today()).days if pd.notna(x) else None)
        df["Task_Due_DT"] = pd.to_datetime(df["Task_Due"], errors="coerce", dayfirst=True).dt.date
        return df
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return None

def salva_sheet(idx, mappa):
    if st.session_state.get("ruolo", "guest") == "guest":
        return False
    try:
        ws = get_ws()
        headers = ws.row_values(1)
        hdr_map = {re.sub(r"\s+", "", h).strip().lower(): i + 1 for i, h in enumerate(headers)}
        updates = []
        for k, v in mappa.items():
            col = hdr_map.get(k.lower())
            if col:
                updates.append({
                    "range": gspread.utils.rowcol_to_a1(int(idx) + 2, col),
                    "values": [[str(v)]],
                })
        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
        return True
    except:
        return False

def carica_modelli():
    d = {
        "fornitori": ["BG Service (commerciale@bgservicebergamo.com)"],
        "mail_fornitore": "commerciale@bgservicebergamo.com",
        "mail_30_ogg": "Lavaggio FV [CLIENTE]",
        "mail_30_txt": "Lavaggio il [DATA]",
        "wa_30_txt": "Lavaggio [DATA]",
        "mail_3_ogg": "Promemoria [CLIENTE]",
        "mail_3_txt": "Ricordiamo [DATA]",
        "wa_3_txt": "Promemoria domani [DATA]",
        "mail_forn_ogg": "Intervento [CLIENTE]",
        "mail_forn_txt": "Intervento [DATA]",
    }
    if FILE_MODELLI.exists():
        try:
            with open(FILE_MODELLI, "r", encoding="utf-8") as f:
                d.update(json.load(f))
        except:
            st.warning("File modelli corrotto, ripristinati valori di default.")
    return d

if "modelli" not in st.session_state:
    st.session_state.modelli = carica_modelli()

# ==========================================================
# 5. SIDEBAR
# ==========================================================
with st.sidebar:
    st.markdown("### 🧼 FV WASH MANAGER")

    if not st.session_state.loggato:
        st.info("Accesso come ospite (solo lettura)")
        u = st.text_input("Username", key="login_user")
        p = st.text_input("Password", type="password", key="login_pwd")
        if st.button("🔐 Login"):
            login(u, p)
    else:
        st.success(f"Loggato come {st.session_state.utente} ({st.session_state.ruolo})")
        if st.button("Logout"):
            logout()

    st.divider()
    pagina = st.radio(
        "Navigazione",
        ["Dashboard","Modelli Messaggi","Fornitori","Calendario","Gestione Utenti","Impostazioni"]
    )
    st.divider()
    st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)
    if st.button("Aggiorna Dati"):
        st.session_state.df = carica_dati()
        st.rerun()

# ==========================================================
# 6. PERMESSI
# ==========================================================
ruolo = st.session_state.ruolo
is_guest = ruolo == "guest"
is_user = ruolo == "user"
is_admin = ruolo == "admin"

can_edit_client = is_user or is_admin
can_send_comms = is_user or is_admin
can_edit_settings = is_admin

# ==========================================================
# 7. DASHBOARD
# ==========================================================
if st.session_state.df is None:
    st.session_state.df = carica_dati()
df = st.session_state.df

# (QUI RESTA TUTTA LA TUA DASHBOARD — NON LA RISCRIVO PERCHÉ È LUNGHISSIMA E GIÀ CORRETTA)

# ==========================================================
# 8. GESTIONE UTENTI (NUOVA PAGINA)
# ==========================================================
elif pagina == "Gestione Utenti":
    if not is_admin:
        st.warning("Accesso riservato all'amministratore.")
        st.stop()

    st.markdown("## 👤 Gestione Utenti")

    utenti = carica_utenti()
    ws_u = get_ws_utenti()

    st.markdown("### Utenti attuali")
    st.dataframe(utenti)

    st.divider()
    st.markdown("### ➕ Aggiungi nuovo utente")

    new_user = st.text_input("Username")
    new_pw = st.text_input("Password", type="password")
    new_role = st.selectbox("Ruolo", ["user", "admin"])

    if st.button("Crea utente"):
        if not new_user:
            st.error("Inserisci uno username.")
        elif new_user in utenti.index:
            st.error("Utente già esistente.")
        else:
            hashed = hash_pw(new_pw)
            ws_u.append_row([new_user, hashed, new_role])
            st.success("Utente creato.")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("### 🔧 Modifica ruolo utente")

    if not utenti.empty:
        sel_user = st.selectbox("Seleziona utente", utenti.index)
        new_role2 = st.selectbox("Nuovo ruolo", ["user", "admin"], key="role_edit")

        if st.button("Aggiorna ruolo"):
            row_idx = utenti.index.get_loc(sel_user) + 2
            ws_u.update_cell(row_idx, 3, new_role2)
            st.success("Ruolo aggiornato.")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("### 🔑 Reset password")

    if not utenti.empty:
        reset_user = st.selectbox("Utente da resettare", utenti.index, key="reset_user")
        new_pw_reset = st.text_input("Nuova password", type="password", key="reset_pw")

        if st.button("Reset password"):
            hashed = hash_pw(new_pw_reset)
            row_idx = utenti.index.get_loc(reset_user) + 2
            ws_u.update_cell(row_idx, 2, hashed)
            st.success("Password aggiornata.")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("### 🧪 Generatore Hash Password (solo admin)")

    pw_gen = st.text_input("Password da convertire", type="password", key="pw_gen")
    if st.button("Genera Hash"):
        if not pw_gen:
            st.error("Inserisci una password.")
        else:
            st.code(hash_pw(pw_gen))

# ==========================================================
# 9. IMPOSTAZIONI
# ==========================================================
elif pagina == "Impostazioni":
    if not can_edit_settings:
        st.warning("Accesso riservato all'amministratore.")
        st.stop()
    st.markdown("## ⚙️ Diagnostica Sistema")
    st.write(f"Google Sheet: {FOGLIO}")
    st.dataframe(df)
