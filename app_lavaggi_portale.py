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
        padding: 30px;
        border-radius: 20px;
        margin-bottom: 25px;
    }

    .hero h1 {
        margin: 0;
        font-size: 34px;
        font-weight: 800;
    }

    .hero p {
        margin: 8px 0 0 0;
        color: #e2e8f0;
        font-size: 16px;
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

    [data-testid="stSidebar"] .stButton button *,
    [data-testid="stSidebar"] .stDownloadButton button *,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] *,
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] * {
        color: #0f172a !important;
    }

    [data-testid="stSidebar"] a,
    [data-testid="stSidebar"] a * {
        color: #0f172a !important;
        font-weight: 800 !important;
    }

    .kpi-btn button {
        min-height: 98px;
        border-radius: 16px !important;
        border: 1px solid #dbe3ef !important;
        background: #ffffff !important;
        font-weight: 800 !important;
        white-space: pre-line;
        color: #0f172a !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    .kpi-btn button * {
        color: #0f172a !important;
    }

    .kpi-btn button:hover {
        border-color: #2563eb !important;
        background: #f8fbff !important;
    }

    .kpi-btn-active button {
        border: 2px solid #2563eb !important;
        background: #eff6ff !important;
    }

    .card {
        background: white;
        padding: 25px;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }

    .status-badge {
        padding: 11px 12px;
        border-radius: 12px;
        font-weight: 900;
        text-align: center;
        font-size: 13px;
        border: 1px solid transparent;
        margin-bottom: 8px;
        min-height: 42px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .status-da-programmare {
        background: #f1f5f9;
        color: #475569;
        border-color: #cbd5e1;
    }

    .status-avvisato {
        background: #fef3c7;
        color: #92400e;
        border-color: #f59e0b;
    }

    .status-confermato {
        background: #dcfce7;
        color: #166534;
        border-color: #22c55e;
    }

    .status-fatto {
        background: #dbeafe;
        color: #1e40af;
        border-color: #60a5fa;
    }

    .status-annullato {
        background: #e5e7eb;
        color: #374151;
        border-color: #9ca3af;
    }

    .action-link {
        display: block;
        text-align: center;
        text-decoration: none;
        color: white !important;
        padding: 12px;
        border-radius: 12px;
        font-weight: 800;
        margin-top: 8px;
    }

    .action-mail { background: #2563eb; }
    .action-wa { background: #16a34a; }
    .action-supplier { background: #475569; }
</style>
""", unsafe_allow_html=True)


# ==========================================================
# 3. GOOGLE SHEETS
# ==========================================================
@st.cache_resource(show_spinner=False)
def get_client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    return get_client().open_by_key(SHEET_ID)


def get_ws_by_name(name):
    return get_spreadsheet().worksheet(name)


def normalizza_nome_colonna(nome):
    return re.sub(r"\s+", "", str(nome)).strip()


def carica_dati():
    try:
        ws = get_ws_by_name(FOGLIO_LAVAGGI)
        df = pd.DataFrame(ws.get_all_records())

        if df.empty:
            return pd.DataFrame()

        df.columns = [normalizza_nome_colonna(c) for c in df.columns]

        colonne = [
            "Cliente", "Impianto", "DataLavaggio", "Orario", "Telefono",
            "EmailCliente", "Stato", "Fornitore", "Promemoria30gg",
            "DataPromemoria", "Promemoria3gg", "DataPromemoria3gg",
            "DataWA30gg", "DataWA3gg", "Note", "EventoCalendarioCreato",
            "DataEventoCreato", "Task_Rem", "Task_Due",
        ]

        for col in colonne:
            if col not in df.columns:
                df[col] = ""

        df["DataLavaggio_DT"] = pd.to_datetime(
            df["DataLavaggio"], errors="coerce", dayfirst=True
        ).dt.date

        df["Task_Due_DT"] = pd.to_datetime(
            df["Task_Due"], errors="coerce", dayfirst=True
        ).dt.date

        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(
            lambda x: (x - date.today()).days if pd.notna(x) else 999
        )

        return df

    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()


def salva_sheet(idx, mappa):
    if not st.session_state.loggato:
        return False

    try:
        ws = get_ws_by_name(FOGLIO_LAVAGGI)
        headers = ws.row_values(1)

        hdr_map = {
            normalizza_nome_colonna(h).lower(): i + 1
            for i, h in enumerate(headers)
        }

        updates = []

        for k, v in mappa.items():
            col = hdr_map.get(normalizza_nome_colonna(k).lower())
            if col:
                cella = gspread.utils.rowcol_to_a1(int(idx) + 2, col)
                updates.append({"range": cella, "values": [[str(v)]]})

        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")

        return True

    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False


# ==========================================================
# 4. AUTENTICAZIONE E UTENTI
# ==========================================================
@st.cache_data(ttl=300, show_spinner=False)
def carica_utenti():
    try:
        ws = get_ws_by_name(FOGLIO_UTENTI)
        utenti = pd.DataFrame(ws.get_all_records())

        if utenti.empty:
            return pd.DataFrame()

        utenti.columns = [str(c).strip().lower() for c in utenti.columns]

        required = {"username", "password_hash", "ruolo"}
        if not required.issubset(set(utenti.columns)):
            st.error("Il foglio Utenti deve avere le colonne: username, password_hash, ruolo")
            return pd.DataFrame()

        utenti["username"] = utenti["username"].astype(str).str.strip()
        utenti["password_hash"] = utenti["password_hash"].astype(str).str.strip()
        utenti["ruolo"] = utenti["ruolo"].astype(str).str.strip().str.lower()

        return utenti

    except Exception as e:
        st.error(f"Errore caricamento utenti: {e}")
        return pd.DataFrame()


def genera_hash_password(password):
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verifica_bcrypt(password, password_hash):
    try:
        if not password_hash.startswith("$2"):
            return False

        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    except Exception:
        return False


def login(username, password):
    username = str(username).strip()
    utenti = carica_utenti()

    if utenti.empty:
        st.error("Nessun utente disponibile.")
        return

    match = utenti[utenti["username"] == username]

    if match.empty:
        st.error("Credenziali errate")
        return

    record = match.iloc[0]

    if verifica_bcrypt(password, record["password_hash"]):
        st.session_state.loggato = True
        st.session_state.utente = record["username"]
        st.session_state.ruolo = record["ruolo"]
        st.rerun()
    else:
        st.error("Credenziali errate")


def logout():
    st.session_state.loggato = False
    st.session_state.utente = None
    st.session_state.ruolo = "ospite"
    st.rerun()


def salva_utente(username, password, ruolo):
    if not is_admin:
        return False

    username = str(username).strip()
    ruolo = str(ruolo).strip().lower()

    if not username:
        st.error("Username obbligatorio.")
        return False

    if ruolo not in ["admin", "supervisor", "user"]:
        st.error("Ruolo non valido.")
        return False

    try:
        ws = get_ws_by_name(FOGLIO_UTENTI)
        utenti = carica_utenti()

        match = utenti[utenti["username"] == username]

        if match.empty:
            if not password:
                st.error("Password obbligatoria per nuovo utente.")
                return False

            ws.append_row(
                [username, genera_hash_password(password), ruolo],
                value_input_option="USER_ENTERED",
            )

        else:
            cell = ws.find(username, in_column=1)
            row_num = cell.row

            ws.update_cell(row_num, 3, ruolo)

            if password:
                ws.update_cell(row_num, 2, genera_hash_password(password))

        carica_utenti.clear()
        return True

    except Exception as e:
        st.error(f"Errore salvataggio utente: {e}")
        return False


def elimina_utente(username):
    if not is_admin:
        return False

    if username == st.session_state.utente:
        st.error("Non puoi eliminare l'utente con cui sei collegato.")
        return False

    try:
        ws = get_ws_by_name(FOGLIO_UTENTI)
        cell = ws.find(username, in_column=1)

        if cell:
            ws.delete_rows(cell.row)
            carica_utenti.clear()
            return True

        st.error("Utente non trovato.")
        return False

    except Exception as e:
        st.error(f"Errore eliminazione utente: {e}")
        return False


# ==========================================================
# 5. MODELLI MESSAGGI SU GOOGLE SHEET
# ==========================================================
MODELLI_DEFAULT = {
    "mail_fornitore": "commerciale@bgservicebergamo.com",
    "mail_30_ogg": "Lavaggio FV [CLIENTE]",
    "mail_30_txt": "Buongiorno, ricordiamo il lavaggio previsto il [DATA] alle [ORARIO].",
    "wa_30_txt": "Buongiorno, ricordiamo il lavaggio previsto il [DATA] alle [ORARIO].",
    "mail_3_ogg": "Promemoria lavaggio FV [CLIENTE]",
    "mail_3_txt": "Buongiorno, confermiamo il lavaggio previsto il [DATA] alle [ORARIO].",
    "wa_3_txt": "Buongiorno, confermiamo il lavaggio previsto il [DATA] alle [ORARIO].",
    "mail_forn_ogg": "Intervento lavaggio FV [CLIENTE]",
    "mail_forn_txt": "Buongiorno, intervento previsto il [DATA] alle [ORARIO] presso [CLIENTE] - [IMPIANTO].",
}


@st.cache_data(ttl=300, show_spinner=False)
def carica_modelli_sheet():
    try:
        ws = get_ws_by_name(FOGLIO_MODELLI)
        rows = ws.get_all_records()

        modelli = MODELLI_DEFAULT.copy()

        for row in rows:
            chiave = str(row.get("chiave", "")).strip()
            valore = str(row.get("valore", ""))

            if chiave:
                modelli[chiave] = valore

        return modelli

    except Exception as e:
        st.warning(f"Foglio Modelli non disponibile, uso valori predefiniti: {e}")
        return MODELLI_DEFAULT.copy()


def salva_modelli_sheet(modelli):
    if not is_admin:
        st.error("Solo admin può salvare i modelli.")
        return False

    try:
        ws = get_ws_by_name(FOGLIO_MODELLI)

        values = [["chiave", "valore"]]

        for chiave, valore in modelli.items():
            values.append([chiave, valore])

        ws.clear()
        ws.update(values, value_input_option="USER_ENTERED")

        carica_modelli_sheet.clear()
        return True

    except Exception as e:
        st.error(f"Errore salvataggio modelli: {e}")
        return False


def compila_testo(testo, row, data, orario):
    return (
        str(testo)
        .replace("[CLIENTE]", str(row.get("Cliente", "")))
        .replace("[DATA]", data)
        .replace("[ORARIO]", str(orario))
        .replace("[IMPIANTO]", str(row.get("Impianto", "")))
    )


def valore_invio(v):
    return str(v).strip() if pd.notna(v) and str(v).strip() else "—"


def classe_stato(stato):
    stato = str(stato).upper().strip()
    if "AVVISATO" in stato:
        return "status-avvisato"
    if "CONFERMATO" in stato:
        return "status-confermato"
    if "FATTO" in stato:
        return "status-fatto"
    if "ANNULLATO" in stato:
        return "status-annullato"
    return "status-da-programmare"


def badge_stato(stato):
    return (
        f'<div class="status-badge {classe_stato(stato)}">'
        f'{str(stato).upper()}'
        "</div>"
    )


def ordina_per_cliente(df_in):
    return df_in.sort_values(
        by="Cliente",
        key=lambda s: s.astype(str).str.upper(),
    )


def ordina_per_data_lavaggio(df_in):
    return df_in.sort_values(
        by=["DataLavaggio_DT", "Cliente"],
        ascending=[True, True],
        na_position="first",
        key=lambda s: s.astype(str).str.upper() if s.name == "Cliente" else s,
    )


def ordina_per_data_task(df_in):
    return df_in.sort_values(
        by=["Task_Due_DT", "Cliente"],
        ascending=[True, True],
        na_position="first",
        key=lambda s: s.astype(str).str.upper() if s.name == "Cliente" else s,
    )


# ==========================================================
# 6. SESSIONE
# ==========================================================
if "loggato" not in st.session_state:
    st.session_state.loggato = False

if "utente" not in st.session_state:
    st.session_state.utente = None

if "ruolo" not in st.session_state:
    st.session_state.ruolo = "ospite"

if "df" not in st.session_state:
    st.session_state.df = carica_dati()

if "selected_idx" not in st.session_state:
    st.session_state.selected_idx = None

if "dash_filter" not in st.session_state:
    st.session_state.dash_filter = "Tutti"

if "modelli" not in st.session_state:
    st.session_state.modelli = carica_modelli_sheet()


is_admin = st.session_state.ruolo == "admin"
can_edit_client = st.session_state.ruolo in ["admin", "supervisor"]
can_send_comms = st.session_state.ruolo in ["admin", "supervisor"]


# ==========================================================
# 7. SIDEBAR
# ==========================================================
with st.sidebar:
    st.markdown("### 🧼 FV WASH MANAGER")

    if not st.session_state.loggato:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("🔐 Login"):
            login(username, password)

    else:
        st.success(f"{st.session_state.utente} · {st.session_state.ruolo}")

        if st.button("🔓 Logout"):
            logout()

    st.divider()

    pagine = ["Dashboard", "Modelli Messaggi", "Fornitori", "Calendario"]

    if is_admin:
        pagine += ["Gestione Utenti"]

    pagine += ["Impostazioni"]

    pagina = st.radio("Navigazione", pagine)

    st.divider()

    if is_admin:
        st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)

    if st.button("🔄 Aggiorna Dati"):
        carica_utenti.clear()
        carica_modelli_sheet.clear()
        st.session_state.modelli = carica_modelli_sheet()
        st.session_state.df = carica_dati()
        st.rerun()


# ==========================================================
# 8. DASHBOARD
# ==========================================================
df = st.session_state.df

if pagina == "Dashboard":
    st.markdown(
        '<div class="hero"><h1>FV WASH MANAGER</h1><p>Controllo Operativo Interventi</p></div>',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.warning("Nessun dato disponibile.")
        st.stop()

    oggi = date.today()

    urg_no_mail = df[
        (df["GiorniMancanti"].between(0, 5))
        & (df["DataPromemoria3gg"].astype(str).str.strip() == "")
        & (df["Stato"].astype(str).str.upper() != "FATTO")
    ]

    manca_30gg = df[
        (df["GiorniMancanti"] > 15)
        & (df["DataPromemoria"].astype(str).str.strip() == "")
        & (df["Stato"].astype(str).str.upper() != "ANNULLATO DA CLIENTE")
    ]

    task_scadenza = df[
        df["Task_Due_DT"].apply(
            lambda x: pd.notna(x) and -1 <= (x - oggi).days <= 3
        )
    ]

    if not urg_no_mail.empty or not manca_30gg.empty or not task_scadenza.empty:
        st.markdown("### ⚠️ Centro Avvisi")
        a1, a2, a3 = st.columns(3)

        with a1:
            if not urg_no_mail.empty:
                if st.button(f"🚨 Reminder 3gg mancanti: {len(urg_no_mail)}"):
                    st.session_state.dash_filter = "Alert: Reminder 3gg"
                    st.rerun()

        with a2:
            if not manca_30gg.empty:
                if st.button(f"📧 Avvisi 30gg mancanti: {len(manca_30gg)}"):
                    st.session_state.dash_filter = "Alert: Avvisi 30gg"
                    st.rerun()

        with a3:
            if not task_scadenza.empty:
                if st.button(f"🔔 Task Reminder: {len(task_scadenza)}"):
                    st.session_state.dash_filter = "Alert: Task Reminder"
                    st.rerun()

        st.divider()

    df_tutti = ordina_per_cliente(df)

    df_conf = ordina_per_data_lavaggio(
        df[df["Stato"].astype(str).str.upper() == "CONFERMATO DA CLIENTE"]
    )

    df_urg = ordina_per_data_lavaggio(df[
        (df["GiorniMancanti"].between(0, 15))
        & (df["Stato"].astype(str).str.upper() != "FATTO")
        & (df["Stato"].astype(str).str.upper() != "CONFERMATO DA CLIENTE")
    ])

    df_comp = ordina_per_data_lavaggio(
        df[df["Stato"].astype(str).str.upper() == "FATTO"]
    )

    df_da_fare = ordina_per_data_lavaggio(df[
        (df["Stato"].astype(str).str.upper() != "FATTO")
        & (df["Stato"].astype(str).str.upper() != "ANNULLATO DA CLIENTE")
    ])

    df_annullati = ordina_per_data_lavaggio(
        df[df["Stato"].astype(str).str.upper() == "ANNULLATO DA CLIENTE"]
    )

    k_cols = st.columns(6)
    kpis = [
        ("Tutti", "📋", len(df_tutti)),
        ("Confermati", "👍", len(df_conf)),
        ("Urgenze", "🔥", len(df_urg)),
        ("Completati", "✅", len(df_comp)),
        ("Da Fare", "🛠️", len(df_da_fare)),
        ("Annullati", "❌", len(df_annullati)),
    ]

    for i, (name, icon, count) in enumerate(kpis):
        with k_cols[i]:
            active_class = "kpi-btn-active" if st.session_state.dash_filter == name else ""
            st.markdown(f'<div class="kpi-btn {active_class}">', unsafe_allow_html=True)

            if st.button(f"{icon}\n{count}\n{name}", key=f"f_{name}", use_container_width=True):
                st.session_state.dash_filter = name
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    if st.session_state.dash_filter == "Alert: Reminder 3gg":
        df_view = ordina_per_data_lavaggio(urg_no_mail)
    elif st.session_state.dash_filter == "Alert: Avvisi 30gg":
        df_view = ordina_per_data_lavaggio(manca_30gg)
    elif st.session_state.dash_filter == "Alert: Task Reminder":
        df_view = ordina_per_data_task(task_scadenza)
    elif st.session_state.dash_filter == "Tutti":
        df_view = df_tutti
    elif st.session_state.dash_filter == "Confermati":
        df_view = df_conf
    elif st.session_state.dash_filter == "Urgenze":
        df_view = df_urg
    elif st.session_state.dash_filter == "Completati":
        df_view = df_comp
    elif st.session_state.dash_filter == "Da Fare":
        df_view = df_da_fare
    else:
        df_view = df_annullati

    col_l, col_r = st.columns([1, 1.8], gap="large")

    with col_l:
        st.markdown(f"### 📅 {st.session_state.dash_filter}")

        search = st.text_input("🔍 Cerca cliente...")

        if search:
            df_view = df_view[
                df_view["Cliente"].astype(str).str.contains(search, case=False, na=False)
            ]

        for idx, r in df_view.head(50).iterrows():
            stato = str(r["Stato"]).upper()
            gm = r["GiorniMancanti"]

            if stato == "FATTO":
                dot = "🟦"
            elif "ANNULLATO" in stato:
                dot = "⚪"
            elif "CONFERMATO" in stato:
                dot = "🟩"
            elif "AVVISATO" in stato:
                dot = "🟨"
            elif gm < 0:
                dot = "🔴"
            elif gm <= 3:
                dot = "🔴"
            elif str(r.get("DataPromemoria", "")).strip() == "" and str(r.get("DataWA30gg", "")).strip() == "":
                dot = "🟡"
            else:
                dot = "⚪"

            label = f"{dot} {r['DataLavaggio']} - {str(r['Cliente']).upper()}"

            if st.button(label, key=f"sel_{idx}", use_container_width=True):
                st.session_state.selected_idx = idx
                st.rerun()

    with col_r:
        if st.session_state.selected_idx is None:
            st.info("Seleziona un cliente dalla lista.")
        else:
            row = df.loc[st.session_state.selected_idx]

            st.markdown(
                f'<div class="card"><h2 style="margin-top:0;">{row["Cliente"]}</h2>',
                unsafe_allow_html=True,
            )

            if not can_edit_client:
                st.warning("🔒 Sola lettura. Accedi con ruolo admin o supervisor per modificare.")

            st.markdown("#### 📡 Storico Invii Promemoria")
            i1, i2, i3, i4 = st.columns(4)

            box_style = (
                "background:#f8fafc; padding:12px 8px; border-radius:12px; "
                "border:1px solid #e2e8f0; text-align:center; line-height:1.4;"
            )

            i1.markdown(f"<div style='{box_style}'><b>Mail 30gg</b><br>{valore_invio(row.get('DataPromemoria',''))}</div>", unsafe_allow_html=True)
            i2.markdown(f"<div style='{box_style}'><b>WA 30gg</b><br>{valore_invio(row.get('DataWA30gg',''))}</div>", unsafe_allow_html=True)
            i3.markdown(f"<div style='{box_style}'><b>Mail 3gg</b><br>{valore_invio(row.get('DataPromemoria3gg',''))}</div>", unsafe_allow_html=True)
            i4.markdown(f"<div style='{box_style}'><b>WA 3gg</b><br>{valore_invio(row.get('DataWA3gg',''))}</div>", unsafe_allow_html=True)

            st.write("")

            c1, c2 = st.columns(2)
            n_cl = c1.text_input("Nome Cliente", row["Cliente"], disabled=not can_edit_client)
            n_im = c2.text_input("Impianto", row["Impianto"], disabled=not can_edit_client)

            c3, c4, c5 = st.columns(3)

            d_dt = row["DataLavaggio_DT"] if pd.notna(row["DataLavaggio_DT"]) else date.today()

            cancella_data_lavaggio = c3.checkbox(
                "Cancella data",
                value=False,
                disabled=not can_edit_client,
                key=f"clear_data_lavaggio_{st.session_state.selected_idx}",
            )

            n_dt = c3.date_input(
                "Data Lavaggio",
                d_dt,
                format="DD/MM/YYYY",
                disabled=not can_edit_client or cancella_data_lavaggio,
            )

            n_or = c4.text_input(
                "Orario",
                row["Orario"],
                disabled=not can_edit_client,
            )

            stati = [
                "DA PROGRAMMARE",
                "AVVISATO CLIENTE",
                "CONFERMATO DA CLIENTE",
                "FATTO",
                "ANNULLATO DA CLIENTE",
            ]

            curr_st = row["Stato"] if row["Stato"] in stati else "DA PROGRAMMARE"

            with c5:
                n_st = st.selectbox(
                    "Stato",
                    stati,
                    index=stati.index(curr_st),
                    disabled=not can_edit_client,
                )

                st.markdown(badge_stato(n_st), unsafe_allow_html=True)

                if st.button(
                    "💾 REGISTRA STATO",
                    key=f"save_stato_{st.session_state.selected_idx}",
                    disabled=not can_edit_client,
                    use_container_width=True,
                ):
                    if salva_sheet(
                        st.session_state.selected_idx,
                        {"Stato": n_st},
                    ):
                        st.success("Stato aggiornato.")
                        st.session_state.df = carica_dati()
                        st.rerun()

            c6, c7 = st.columns(2)
            n_tel = c6.text_input("Telefono", row["Telefono"], disabled=not can_edit_client)
            n_ml = c7.text_input("Email Cliente", row["EmailCliente"], disabled=not can_edit_client)

            n_note = st.text_area("Note", row["Note"], height=70, disabled=not can_edit_client)

            st.markdown("#### 🔔 Reminder Custom")
            c8, c9 = st.columns([2, 1])
            n_task = c8.text_input("Azione", row["Task_Rem"], disabled=not can_edit_client)
            task_date = row["Task_Due_DT"] if pd.notna(row["Task_Due_DT"]) else None
            n_task_due = c9.date_input("Scadenza", task_date, format="DD/MM/YYYY", disabled=not can_edit_client)

            if st.button("💾 AGGIORNA DATI CLIENTE", type="primary", disabled=not can_edit_client):
                ok = salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "Cliente": n_cl,
                        "Impianto": n_im,
                        "DataLavaggio": "" if cancella_data_lavaggio else n_dt.strftime("%d/%m/%Y"),
                        "Orario": "" if cancella_data_lavaggio else n_or,
                        "Stato": n_st,
                        "Telefono": n_tel,
                        "EmailCliente": n_ml,
                        "Note": n_note,
                        "Task_Rem": n_task,
                        "Task_Due": n_task_due.strftime("%d/%m/%Y") if n_task_due else "",
                    },
                )

                if ok:
                    st.success("Dati aggiornati.")
                    st.session_state.df = carica_dati()
                    st.rerun()

            st.divider()
            st.markdown("#### 🚀 Invio Comunicazioni")

            tipo = "3" if row["GiorniMancanti"] <= 5 else "30"
            data_txt = n_dt.strftime("%d/%m/%Y")
            mod = st.session_state.modelli

            ca, cb, cc = st.columns(3)

            if ca.button(f"✉️ Email {tipo}gg", disabled=not can_send_comms):
                ogg = compila_testo(mod[f"mail_{tipo}_ogg"], row, data_txt, n_or)
                txt = compila_testo(mod[f"mail_{tipo}_txt"], row, data_txt, n_or)

                if tipo == "3":
                    aggiornamenti = {
                        "DataPromemoria3gg": date.today().strftime("%d/%m/%Y"),
                        "Promemoria3gg": "SI",
                        "Stato": "AVVISATO CLIENTE",
                    }
                else:
                    aggiornamenti = {
                        "DataPromemoria": date.today().strftime("%d/%m/%Y"),
                        "Promemoria30gg": "SI",
                        "Stato": "AVVISATO CLIENTE",
                    }

                if salva_sheet(st.session_state.selected_idx, aggiornamenti):
                    st.session_state.df = carica_dati()
                    url = f"mailto:{n_ml}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank" class="action-link action-mail">APRI EMAIL</a>', unsafe_allow_html=True)

            if cb.button(f"💬 WhatsApp {tipo}gg", disabled=not can_send_comms):
                txt = compila_testo(mod[f"wa_{tipo}_txt"], row, data_txt, n_or)
                num = "".join(filter(str.isdigit, str(n_tel)))

                if num.startswith("3") and len(num) == 10:
                    num = "39" + num

                if tipo == "3":
                    aggiornamenti = {
                        "DataWA3gg": date.today().strftime("%d/%m/%Y"),
                        "Promemoria3gg": "SI",
                        "Stato": "AVVISATO CLIENTE",
                    }
                else:
                    aggiornamenti = {
                        "DataWA30gg": date.today().strftime("%d/%m/%Y"),
                        "Promemoria30gg": "SI",
                        "Stato": "AVVISATO CLIENTE",
                    }

                if salva_sheet(st.session_state.selected_idx, aggiornamenti):
                    st.session_state.df = carica_dati()
                    url = f"https://wa.me/{num}?text={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank" class="action-link action-wa">APRI WHATSAPP</a>', unsafe_allow_html=True)

            if cc.button("👷 Email Fornitore", disabled=not can_send_comms or n_st != "CONFERMATO DA CLIENTE"):
                ogg = compila_testo(mod["mail_forn_ogg"], row, data_txt, n_or)
                txt = compila_testo(mod["mail_forn_txt"], row, data_txt, n_or)
                url = f"mailto:{mod['mail_fornitore']}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}"
                st.markdown(f'<a href="{url}" target="_blank" class="action-link action-supplier">AVVISA FORNITORE</a>', unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)


# ==========================================================
# 9. MODELLI MESSAGGI
# ==========================================================
elif pagina == "Modelli Messaggi":
    st.title("📝 Modelli Messaggi")

    mod = st.session_state.modelli.copy()

    if not is_admin:
        st.info("Solo admin può modificare i modelli. Gli altri utenti possono consultarli.")

    mod["mail_fornitore"] = st.text_input(
        "Email Fornitore",
        mod.get("mail_fornitore", ""),
        disabled=not is_admin,
    )

    with st.expander("Email Clienti", expanded=True):
        c1, c2 = st.columns(2)

        mod["mail_30_ogg"] = c1.text_input("Oggetto 30gg", mod.get("mail_30_ogg", ""), disabled=not is_admin)
        mod["mail_30_txt"] = c1.text_area("Testo 30gg", mod.get("mail_30_txt", ""), disabled=not is_admin)

        mod["mail_3_ogg"] = c2.text_input("Oggetto 3gg", mod.get("mail_3_ogg", ""), disabled=not is_admin)
        mod["mail_3_txt"] = c2.text_area("Testo 3gg", mod.get("mail_3_txt", ""), disabled=not is_admin)

    with st.expander("WhatsApp", expanded=True):
        mod["wa_30_txt"] = st.text_area("WhatsApp 30gg", mod.get("wa_30_txt", ""), disabled=not is_admin)
        mod["wa_3_txt"] = st.text_area("WhatsApp 3gg", mod.get("wa_3_txt", ""), disabled=not is_admin)

    with st.expander("Fornitore", expanded=True):
        mod["mail_forn_ogg"] = st.text_input("Oggetto Fornitore", mod.get("mail_forn_ogg", ""), disabled=not is_admin)
        mod["mail_forn_txt"] = st.text_area("Testo Fornitore", mod.get("mail_forn_txt", ""), disabled=not is_admin)

    if st.button("💾 SALVA MODELLI", type="primary", disabled=not is_admin):
        if salva_modelli_sheet(mod):
            st.session_state.modelli = carica_modelli_sheet()
            st.success("Modelli salvati su Google Sheet.")
            st.rerun()


# ==========================================================
# 10. FORNITORI
# ==========================================================
elif pagina == "Fornitori":
    st.title("👷 Resoconto Fornitore")

    limite = date.today() + timedelta(days=30)

    df_f = df[
        (df["DataLavaggio_DT"].between(date.today(), limite))
        & (df["Stato"].astype(str).str.upper() != "ANNULLATO DA CLIENTE")
    ].sort_values(by="DataLavaggio_DT", na_position="first")

    st.write(f"Lavaggi programmati entro il {limite.strftime('%d/%m/%Y')}: **{len(df_f)}**")

    if not df_f.empty:
        st.dataframe(
            df_f[["DataLavaggio", "Orario", "Cliente", "Impianto", "Stato"]],
            use_container_width=True,
        )

        testo = "Buongiorno,\ndi seguito il riepilogo dei lavaggi dei prossimi 30 giorni:\n\n"

        for _, r in df_f.iterrows():
            testo += f"- {r['DataLavaggio']} {r['Orario']}: {r['Cliente']} | {r['Impianto']} | Stato: {r['Stato']}\n"

        if st.button("Genera Email Fornitore", disabled=not can_send_comms):
            st.code(testo)
            url = (
                f"mailto:{st.session_state.modelli['mail_fornitore']}"
                f"?subject=Riepilogo Lavaggi 30gg"
                f"&body={urllib.parse.quote(testo)}"
            )
            st.markdown(f'<a href="{url}" target="_blank" class="action-link action-supplier">INVIA AL FORNITORE</a>', unsafe_allow_html=True)


# ==========================================================
# 11. CALENDARIO
# ==========================================================
elif pagina == "Calendario":
    st.title("📅 Esporta Calendario")

    conf = df[
        (df["Stato"].astype(str).str.upper() == "CONFERMATO DA CLIENTE")
        & (df["EventoCalendarioCreato"].astype(str).str.upper() != "SI")
    ]

    if conf.empty:
        st.info("Nessun nuovo evento confermato da esportare.")
    else:
        ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//FV Wash Manager//IT\n"

        for _, r in conf.iterrows():
            dt = r["DataLavaggio_DT"]

            if pd.notna(dt):
                data_ics = str(dt).replace("-", "")
                ics += (
                    "BEGIN:VEVENT\n"
                    f"SUMMARY:Lavaggio {r['Cliente']}\n"
                    f"DTSTART:{data_ics}T080000\n"
                    f"DTEND:{data_ics}T090000\n"
                    "END:VEVENT\n"
                )

        ics += "END:VCALENDAR"

        if st.download_button("Scarica .ics", ics, "lavaggi.ics", disabled=not can_send_comms):
            for i in conf.index:
                salva_sheet(
                    i,
                    {
                        "EventoCalendarioCreato": "SI",
                        "DataEventoCreato": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    },
                )

            st.success("Eventi segnati come esportati.")


# ==========================================================
# 12. GESTIONE UTENTI
# ==========================================================
elif pagina == "Gestione Utenti":
    st.title("👤 Gestione Utenti")

    if not is_admin:
        st.warning("Accesso riservato agli amministratori.")
        st.stop()

    utenti = carica_utenti()

    if utenti.empty:
        st.warning("Nessun utente trovato.")
    else:
        st.dataframe(
            utenti[["username", "ruolo"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.markdown("### Nuovo utente / modifica utente")

    lista_utenti = ["Nuovo utente"]

    if not utenti.empty:
        lista_utenti += utenti["username"].tolist()

    scelta = st.selectbox("Seleziona utente", lista_utenti)

    if scelta == "Nuovo utente":
        username = st.text_input("Username")
        ruolo = st.selectbox("Ruolo", ["user", "supervisor", "admin"])
        password = st.text_input("Password", type="password")
        conferma = st.text_input("Conferma password", type="password")

        if st.button("➕ CREA UTENTE", type="primary"):
            if password != conferma:
                st.error("Le password non coincidono.")
            elif salva_utente(username, password, ruolo):
                st.success("Utente creato.")
                st.rerun()

    else:
        record = utenti[utenti["username"] == scelta].iloc[0]

        username = st.text_input("Username", record["username"], disabled=True)

        ruolo_corrente = record["ruolo"] if record["ruolo"] in ["user", "supervisor", "admin"] else "user"

        ruolo = st.selectbox(
            "Ruolo",
            ["user", "supervisor", "admin"],
            index=["user", "supervisor", "admin"].index(ruolo_corrente),
        )

        st.info("Lascia vuota la password se vuoi modificare solo il ruolo.")

        nuova_password = st.text_input("Nuova password", type="password")
        conferma_password = st.text_input("Conferma nuova password", type="password")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("💾 SALVA MODIFICHE", type="primary"):
                if nuova_password and nuova_password != conferma_password:
                    st.error("Le password non coincidono.")
                elif salva_utente(username, nuova_password, ruolo):
                    st.success("Utente aggiornato.")
                    st.rerun()

        with c2:
            if st.button("🗑️ ELIMINA UTENTE"):
                if elimina_utente(username):
                    st.success("Utente eliminato.")
                    st.rerun()


# ==========================================================
# 13. IMPOSTAZIONI
# ==========================================================
elif pagina == "Impostazioni":
    st.title("⚙️ Diagnostica")

    st.write(f"Utente: **{st.session_state.utente or 'ospite'}**")
    st.write(f"Ruolo: **{st.session_state.ruolo}**")
    st.write(f"Foglio lavaggi: **{FOGLIO_LAVAGGI}**")
    st.write(f"Foglio utenti: **{FOGLIO_UTENTI}**")
    st.write(f"Foglio modelli: **{FOGLIO_MODELLI}**")

    st.dataframe(df, use_container_width=True)
