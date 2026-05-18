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
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(
        UTENTI_SHEET_NAME
    )


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
    
    .hero {
        background: linear-gradient(rgba(15,23,42,0.8), rgba(15,23,42,0.8)), 
                    url('https://images.unsplash.com/photo-1509391366360-2e959784a276?q=80&w=1600&auto=format&fit=crop');
        background-size: cover; background-position: center;
        padding: 50px 40px; border-radius: 24px; color: white; text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); margin-bottom: 2rem;
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

    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #f8fafc !important; }
    [data-testid="stSidebar"] .stButton > button { background-color: #1e293b !important; color: white !important; border: 1px solid #334155 !important; }

    .status-container { padding: 10px; border-radius: 12px; font-weight: 800; text-align: center; margin-bottom: 5px; color: white; }
    .st-da-programmare { background-color: #94a3b8; }
    .st-avvisato { background-color: #3b82f6; }
    .st-confermato { background-color: #22c55e; }
    .st-fatto { background-color: #475569; }
    .st-annullato { background-color: #ef4444; }

    .card { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 25px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    .stButton>button { border-radius: 12px !important; font-weight: 700 !important; width: 100%; }
    .placeholder-box { background: #eff6ff; border: 1px solid #bfdbfe; padding: 15px; border-radius: 12px; margin-bottom: 20px; color: #1e40af; }
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
            "Cliente",
            "Impianto",
            "DataLavaggio",
            "Orario",
            "Telefono",
            "EmailCliente",
            "Stato",
            "Fornitore",
            "DataPromemoria",
            "DataPromemoria3gg",
            "DataWA30gg",
            "DataWA3gg",
            "Note",
            "EventoCalendarioCreato",
            "Task_Rem",
            "Task_Due",
        ]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df["DataLavaggio_DT"] = pd.to_datetime(
            df["DataLavaggio"], errors="coerce", dayfirst=True
        ).dt.date
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(
            lambda x: (x - date.today()).days if pd.notna(x) else None
        )
        df["Task_Due_DT"] = pd.to_datetime(
            df["Task_Due"], errors="coerce", dayfirst=True
        ).dt.date
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
        hdr_map = {
            re.sub(r"\s+", "", h).strip().lower(): i + 1
            for i, h in enumerate(headers)
        }
        updates = []
        for k, v in mappa.items():
            col = hdr_map.get(k.lower())
            if col:
                updates.append(
                    {
                        "range": gspread.utils.rowcol_to_a1(int(idx) + 2, col),
                        "values": [[str(v)]],
                    }
                )
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
        except Exception:
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
        st.success(
            f"✅ Loggato come {st.session_state.utente} ({st.session_state.ruolo})"
        )
        if st.button("🔓 Logout"):
            logout()

    st.divider()
    pagina = st.radio(
        "Navigazione",
        [
            "Dashboard",
            "Modelli Messaggi",
            "Fornitori",
            "Calendario",
            "Gestione Utenti",
            "Impostazioni",
        ],
    )
    st.divider()
    st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)
    if st.button("🔄 Aggiorna Dati"):
        st.session_state.df = carica_dati()
        st.rerun()

# ==========================================================
# 6. PERMESSI
# ==========================================================
ruolo = st.session_state.ruolo
is_guest = ruolo == "guest"
is_user = ruolo == "user"
is_manager = ruolo == "supervisor"  
is_admin = ruolo == "admin"

# Chi può fare cosa:
can_edit_client = is_user or is_supervisor or is_admin
can_send_comms = is_user or is_supervisor or is_admin
can_edit_settings = is_manager or is_admin  # Il supervisor può modificare i modelli email/WA
can_manage_users = is_admin                 # SOLO l'admin può gestire le password

# ==========================================================
# 7. CARICAMENTO DATI
# ==========================================================
if st.session_state.df is None:
    st.session_state.df = carica_dati()
df = st.session_state.df

# ==========================================================
# 8. DASHBOARD
# ==========================================================
if pagina == "Dashboard":
    st.markdown(
        '<div class="hero"><h1>FV WASH MANAGER</h1><p>Controllo Operativo Interventi</p></div>',
        unsafe_allow_html=True,
    )

    oggi = date.today()
    urg_no_mail = df[
        (df["GiorniMancanti"].between(0, 5))
        & (df["DataPromemoria3gg"] == "")
        & (df["Stato"].str.upper() != "FATTO")
    ]
    manca_30gg = df[
        (df["GiorniMancanti"] > 15)
        & (df["DataPromemoria"] == "")
        & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ]
    task_scadenza = pd.DataFrame()
    if "Task_Due_DT" in df.columns:
        task_scadenza = df[
            df["Task_Due_DT"].apply(
                lambda x: pd.notna(x)
                and (x - oggi).days <= 3
                and (x - oggi).days >= -1
            )
        ]

    if (
        not urg_no_mail.empty
        or not manca_30gg.empty
        or not task_scadenza.empty
    ):
        st.markdown("### ⚠️ Centro Avvisi (Clicca per gestire)")
        c_al1, c_al2, c_al3 = st.columns(3)
        with c_al1:
            if not urg_no_mail.empty:
                if st.button(
                    f"🚨 Reminder 3gg mancanti: {len(urg_no_mail)}",
                    type="primary",
                ):
                    st.session_state.dash_filter = "Alert: Reminder 3gg"
                    st.rerun()
        with c_al2:
            if not manca_30gg.empty:
                if st.button(
                    f"📧 Avvisi 30gg mancanti: {len(manca_30gg)}"
                ):
                    st.session_state.dash_filter = "Alert: Avvisi 30gg"
                    st.rerun()
        with c_al3:
            if not task_scadenza.empty:
                if st.button(
                    f"🔔 Reminder Task scadenza: {len(task_scadenza)}"
                ):
                    st.session_state.dash_filter = "Alert: Task Reminder"
                    st.rerun()
        st.divider()

    df_tutti = df.sort_values(by="Cliente")
    df_conf = df[
        df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_urg = df[
        (df["GiorniMancanti"].between(0, 15))
        & (df["Stato"].str.upper() != "CONFERMATO DA CLIENTE")
        & (df["Stato"].str.upper() != "FATTO")
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_comp = df[
        df["Stato"].str.upper() == "FATTO"
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_da_fare = df[
        (df["Stato"].str.upper() != "FATTO")
        & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_annullati = df[
        df["Stato"].str.upper() == "ANNULLATO DA CLIENTE"
    ].sort_values(by="DataLavaggio_DT", na_position="last")

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
            act = "kpi-active" if st.session_state.dash_filter == name else ""
            st.markdown(
                f'<div class="kpi-box {act}"><span class="kpi-icon">{icon}</span><p class="kpi-val">{count}</p><p class="kpi-lab">{name}</p></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                name, key=f"f_{name}", use_container_width=True
            ):
                st.session_state.dash_filter = name
                st.rerun()

    st.divider()

    if st.session_state.dash_filter == "Alert: Reminder 3gg":
        df_view = urg_no_mail.sort_values(by="DataLavaggio_DT")
    elif st.session_state.dash_filter == "Alert: Avvisi 30gg":
        df_view = manca_30gg.sort_values(by="DataLavaggio_DT")
    elif st.session_state.dash_filter == "Alert: Task Reminder":
        df_view = task_scadenza.sort_values(by="Task_Due_DT")
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

    mask_sospesi = (df_view["DataLavaggio"] == "") | (
        df_view["Stato"].str.upper().isin(
            ["DA PROGRAMMARE", "ANNULLATO DA CLIENTE"]
        )
    )
    df_attivi = df_view[~mask_sospesi]
    df_sospesi = df_view[mask_sospesi]

    col_l, col_r = st.columns([1, 1.8], gap="large")
    with col_l:
        st.markdown(f"### 📅 {st.session_state.dash_filter}")
        search = st.text_input("🔍 Cerca...", placeholder="Filtra Cliente...")
        if search:
            df_attivi = df_attivi[
                df_attivi["Cliente"].str.contains(search, case=False)
            ]
            df_sospesi = df_sospesi[
                df_sospesi["Cliente"].str.contains(search, case=False)
            ]

        for idx, r in df_attivi.head(45).iterrows():
            st_u = str(r["Stato"]).upper()
            gm = r["GiorniMancanti"]
            if st_u == "FATTO":
                dot = "🟢"
            elif st_u == "ANNULLATO DA CLIENTE":
                dot = "⚪"
            elif gm is not None and (
                gm < 0 or (gm <= 3 and st_u != "CONFERMATO DA CLIENTE")
            ):
                dot = "🔴"
            elif r["DataPromemoria"] == "" and r["DataWA30gg"] == "":
                dot = "🟡"
            else:
                dot = "🟢"

            lbl = f"{dot}   {r['DataLavaggio']}      {str(r['Cliente']).upper()}"
            st.button(
                lbl,
                key=f"sel_{idx}",
                use_container_width=True,
                on_click=lambda i=idx: st.session_state.update(
                    {"selected_idx": i}
                ),
            )

        if (
            not df_sospesi.empty
            and st.session_state.dash_filter
            in ["Tutti", "Da Fare", "Annullati"]
        ):
            with st.expander("📁 SOSPESI / ANNULLATI"):
                for idx, r in df_sospesi.iterrows():
                    lbl = f"⚪   [{r['Stato'] or '??'}]      {str(r['Cliente']).upper()}"
                    st.button(
                        lbl,
                        key=f"sel_{idx}",
                        use_container_width=True,
                        on_click=lambda i=idx: st.session_state.update(
                            {"selected_idx": i}
                        ),
                    )

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(
                f'<div class="card"><h2>{row["Cliente"]}</h2>',
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            n_cl = c1.text_input(
                "Nome Cliente",
                row["Cliente"],
                disabled=not can_edit_client,
            )
            n_im = c2.text_input(
                "Impianto", row["Impianto"], disabled=not can_edit_client
            )
            c3, c4, c5 = st.columns(3)
            d_dt = (
                row["DataLavaggio_DT"]
                if pd.notna(row["DataLavaggio_DT"])
                else date.today()
            )
            n_dt = c3.date_input(
                "Data Lavaggio",
                d_dt,
                format="DD/MM/YYYY",
                disabled=not can_edit_client,
            )
            n_or = c4.text_input(
                "Orario", row["Orario"], disabled=not can_edit_client
            )
            st_list = [
                "DA PROGRAMMARE",
                "AVVISATO CLIENTE",
                "CONFERMATO DA CLIENTE",
                "FATTO",
                "ANNULLATO DA CLIENTE",
            ]
            curr_st = (
                row["Stato"]
                if row["Stato"] in st_list
                else "DA PROGRAMMARE"
            )
            st_cls = "st-da-programmare"
            if "AVVISATO" in curr_st:
                st_cls = "st-avvisato"
            elif "CONFERMATO" in curr_st:
                st_cls = "st-confermato"
            elif "FATTO" in curr_st:
                st_cls = "st-fatto"
            elif "ANNULLATO" in curr_st:
                st_cls = "st-annullato"
            with c5:
                st.markdown(
                    f'<div class="status-container {st_cls}">{curr_st}</div>',
                    unsafe_allow_html=True,
                )
                n_st = st.selectbox(
                    "Cambia Stato",
                    st_list,
                    index=st_list.index(curr_st),
                    label_visibility="collapsed",
                    disabled=not can_edit_client,
                )
            c6, c7 = st.columns(2)
            n_tel = c6.text_input(
                "Telefono", row["Telefono"], disabled=not can_edit_client
            )
            n_ml = c7.text_input(
                "Email", row["EmailCliente"], disabled=not can_edit_client
            )
            n_note = st.text_area(
                "Note",
                row["Note"],
                height=70,
                disabled=not can_edit_client,
            )

            st.markdown("#### 🔔 Reminder Custom")
            c_tr, c_td = st.columns([2, 1])
            n_tr = c_tr.text_input(
                "Azione", row["Task_Rem"], disabled=not can_send_comms
            )
            n_td = c_td.date_input(
                "Scadenza",
                row["Task_Due_DT"] if pd.notna(row["Task_Due_DT"]) else None,
                format="DD/MM/YYYY",
                disabled=not can_send_comms,
            )

            if st.button(
                "💾 AGGIORNA DATI CLIENTE",
                type="primary",
                disabled=not can_edit_client,
            ):
                if salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "Cliente": n_cl,
                        "Impianto": n_im,
                        "DataLavaggio": n_dt.strftime("%d/%m/%Y"),
                        "Orario": n_or,
                        "Stato": n_st,
                        "Telefono": n_tel,
                        "EmailCliente": n_ml,
                        "Note": n_note,
                        "Task_Rem": n_tr,
                        "Task_Due": n_td.strftime("%d/%m/%Y")
                        if n_td
                        else "",
                    },
                ):
                    st.session_state.df = carica_dati()
                    st.rerun()

            st.divider()
            st.markdown("#### 🚀 Invio Comunicazioni")
            tipo = (
                "3"
                if (
                    pd.notna(row["GiorniMancanti"])
                    and row["GiorniMancanti"] <= 5
                )
                else "30"
            )
            mod = st.session_state.modelli

            def comp(t, r, d, o):
                return (
                    t.replace("[CLIENTE]", r["Cliente"])
                    .replace("[DATA]", d)
                    .replace("[ORARIO]", o)
                    .replace("[IMPIANTO]", r["Impianto"])
                )

            ca, cb, cc = st.columns(3)
            if ca.button(
                f"✉️ Email {tipo}gg", disabled=not can_send_comms
            ):
                ogg = comp(
                    mod[f"mail_{tipo}_ogg"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                txt = comp(
                    mod[f"mail_{tipo}_txt"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                if salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "DataPromemoria"
                        + ("3gg" if tipo == "3" else ""): date.today().strftime(
                            "%d/%m/%Y"
                        ),
                        "Stato": "AVVISATO CLIENTE",
                    },
                ):
                    st.markdown(
                        f'<a href="mailto:{n_ml}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}" target="_blank" style="text-decoration:none;"><div style="background:#2563eb;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">APRI EMAIL</div></a>',
                        unsafe_allow_html=True,
                    )
            if cb.button(
                f"💬 WhatsApp {tipo}gg", disabled=not can_send_comms
            ):
                txt = comp(
                    mod[f"wa_{tipo}_txt"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                num = "".join(filter(str.isdigit, n_tel))
                if num.startswith("3") and len(num) == 10:
                    num = "39" + num
                if salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "DataWA"
                        + tipo
                        + "gg": date.today().strftime("%d/%m/%Y"),
                        "Stato": "AVVISATO CLIENTE",
                    },
                ):
                    url = f"https://wa.me/{num}?text={urllib.parse.quote(txt)}"
                    st.markdown(
                        f'<a href="{url}" target="_blank" style="text-decoration:none;"><div style="background:#16a34a;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">APRI WHATSAPP</div></a>',
                        unsafe_allow_html=True,
                    )
            if cc.button(
                "👷 Email Fornitore",
                disabled=not can_send_comms
                or n_st != "CONFERMATO DA CLIENTE",
            ):
                ogg = comp(
                    mod["mail_forn_ogg"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                txt = comp(
                    mod["mail_forn_txt"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                st.markdown(
                    f'<a href="mailto:{mod["mail_fornitore"]}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}" target="_blank" style="text-decoration:none;"><div style="background:#475569;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">AVVISA FORNITORE</div></a>',
                    unsafe_allow_html=True,
                )

# ==========================================================
# 9. FORNITORI
# ==========================================================
elif pagina == "Fornitori":
    st.markdown("## 👷 Resoconto Lavaggi per Fornitore")
    conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
    if st.button("Genera Riepilogo per BG Service"):
        txt = "Buongiorno,\ndi seguito i lavaggi confermati:\n\n"
        for _, r in conf.iterrows():
            txt += (
                f"- {r['DataLavaggio']} | {r['Cliente']} | {r['Impianto']}\n"
            )
        st.code(txt)
        st.markdown(
            f'<a href="mailto:{st.session_state.modelli["mail_fornitore"]}?subject=Riepilogo Lavaggi&body={urllib.parse.quote(txt)}" target="_blank" style="background:#1e293b;color:white;padding:10px;border-radius:10px;text-decoration:none;">Invia per Email</a>',
            unsafe_allow_html=True,
        )

# ==========================================================
# 10. MODELLI MESSAGGI
# ==========================================================
elif pagina == "Modelli Messaggi":
    if not can_edit_settings:
        st.warning(
            "Accesso in sola lettura. Solo l'amministratore può modificare i modelli."
        )
        is_read_only = True
    else:
        is_read_only = False

    st.markdown("## 📝 Personalizzazione Messaggi")
    st.markdown(
        '<div class="placeholder-box"><b>Campi:</b> [CLIENTE], [DATA], [ORARIO], [IMPIANTO]</div>',
        unsafe_allow_html=True,
    )
    mod = st.session_state.modelli
    mod["mail_fornitore"] = st.text_input(
        "Email Predefinita Fornitore",
        mod.get("mail_fornitore", ""),
        disabled=is_read_only,
    )
    with st.expander("📧 EMAIL"):
        c1, c2 = st.columns(2)
        mod["mail_30_ogg"] = c1.text_input(
            "Ogg 30gg", mod["mail_30_ogg"], disabled=is_read_only
        )
        mod["mail_30_txt"] = c1.text_area(
            "Testo 30gg", mod["mail_30_txt"], disabled=is_read_only
        )
        mod["mail_3_ogg"] = c2.text_input(
            "Ogg 3gg", mod["mail_3_ogg"], disabled=is_read_only
        )
        mod["mail_3_txt"] = c2.text_area(
            "Testo 3gg", mod["mail_3_txt"], disabled=is_read_only
        )
    with st.expander("💬 WHATSAPP"):
        mod["wa_30_txt"] = st.text_area(
            "WA 30gg", mod["wa_30_txt"], disabled=is_read_only
        )
        mod["wa_3_txt"] = st.text_area(
            "WA 3gg", mod["wa_3_txt"], disabled=is_read_only
        )
    with st.expander("👷 FORNITORE"):
        mod["mail_forn_ogg"] = st.text_input(
            "Ogg Fornitore",
            mod["mail_forn_ogg"],
            disabled=is_read_only,
        )
        mod["mail_forn_txt"] = st.text_area(
            "Testo Fornitore",
            mod["mail_forn_txt"],
            disabled=is_read_only,
        )
    if st.button(
        "💾 SALVA MODELLI", type="primary", disabled=is_read_only
    ):
        with open(FILE_MODELLI, "w", encoding="utf-8") as f:
            json.dump(mod, f, indent=4)
        st.success("Modelli salvati!")

# ==========================================================
# 11. CALENDARIO
# ==========================================================
elif pagina == "Calendario":
    st.markdown("## 📅 Esporta Calendario")
    conf = df[
        (df["Stato"].str.upper() == "CONFERMATO DA CLIENTE")
        & (df["EventoCalendarioCreato"] != "SI")
    ]
    if not conf.empty:
        ics = "BEGIN:VCALENDAR\n"
        for i, r in conf.iterrows():
            ics += (
                "BEGIN:VEVENT\n"
                f"SUMMARY:Lavaggio {r['Cliente']}\n"
                f"DTSTART:{str(r['DataLavaggio_DT']).replace('-','')}T080000\n"
                "END:VEVENT\n"
            )
        ics += "END:VCALENDAR"
        st.download_button(
            "Scarica .ics",
            ics,
            "nuovi.ics",
            disabled=is_guest,
            on_click=lambda: [
                salva_sheet(i, {"EventoCalendarioCreato": "SI"})
                for i in conf.index
            ],
        )

# ==========================================================
# 12. GESTIONE UTENTI
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
    # Aggiunto "supervisor" al menu a tendina
    new_role = st.selectbox("Ruolo", ["user", "supervisor", "admin"])

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
        # Aggiunto "supervisor" al menu a tendina
        new_role2 = st.selectbox("Nuovo ruolo", ["user", "supervisor", "admin"], key="role_edit")

        if st.button("Aggiorna ruolo"):
            row_idx = utenti.index.get_loc(sel_user) + 2
            ws_u.update_cell(row_idx, 3, new_role2)
            st.success("Ruolo aggiornato.")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("### 🔑 Reset password")

    if not utenti.empty:
        reset_user = st.selectbox(
            "Utente da resettare", utenti.index, key="reset_user"
        )
        new_pw_reset = st.text_input(
            "Nuova password", type="password", key="reset_pw"
        )

        if st.button("Reset password"):
            hashed = hash_pw(new_pw_reset)
            row_idx = utenti.index.get_loc(reset_user) + 2
            ws_u.update_cell(row_idx, 2, hashed)
            st.success("Password aggiornata.")
            st.cache_data.clear()
            st.rerun()

    st.divider()
    st.markdown("### 🧪 Generatore Hash Password (solo admin)")

    pw_gen = st.text_input(
        "Password da convertire in hash", type="password", key="pw_gen"
    )
    if st.button("Genera Hash"):
        if not pw_gen:
            st.error("Inserisci una password.")
        else:
            st.code(hash_pw(pw_gen))

# ==========================================================
# 13. IMPOSTAZIONI
# ==========================================================
elif pagina == "Impostazioni":
    if not can_edit_settings:
        st.warning("Accesso riservato all'amministratore.")
        st.stop()
    st.markdown("## ⚙️ Diagnostica Sistema")
    st.write(f"Google Sheet: {FOGLIO}")
    st.dataframe(df)
