# -*- coding: utf-8 -*-

import json
import re
import urllib.parse
import bcrypt
from datetime import date, datetime, timedelta
from pathlib import Path

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

BASE_DIR = Path(__file__).resolve().parent
FILE_MODELLI = BASE_DIR / "modelli_messaggi.json"

SHEET_ID = st.secrets.get("google_sheet", {}).get(
    "spreadsheet_id",
    "16RUw8kcZRurs_LYP9WCGbbLiXZnHEhw_lLEsdlS5Zuc",
)

FOGLIO_LAVAGGI = st.secrets.get("google_sheet", {}).get("worksheet_name", "Lavaggi")
FOGLIO_UTENTI = st.secrets.get("google_sheet", {}).get("users_worksheet_name", "Utenti")

SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# ==========================================================
# 2. STILE
# ==========================================================
st.markdown(
    """
<style>
    .stApp { background: #f8fafc; }
    .hero {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: white; padding: 30px; border-radius: 20px; margin-bottom: 25px;
    }
    .kpi-box {
        background: #ffffff; padding: 20px; border-radius: 15px;
        border: 1px solid #e2e8f0; text-align: center;
    }
    .kpi-active { border: 2px solid #2563eb; background: #eff6ff; }
    .kpi-val { font-size: 28px; font-weight: 800; color: #1e293b; margin: 0; }
    .kpi-lab { font-size: 14px; color: #64748b; font-weight: 600; margin: 0; }
    .card {
        background: white; padding: 25px; border-radius: 20px;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 700 !important; width: 100%; }
</style>
""",
    unsafe_allow_html=True,
)


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


def normalizza_colonne(df):
    df.columns = [re.sub(r"\s+", "", str(c)).strip() for c in df.columns]
    return df


def assicurati_colonne(df, colonne):
    for col in colonne:
        if col not in df.columns:
            df[col] = ""
    return df


def carica_dati():
    try:
        ws = get_ws_by_name(FOGLIO_LAVAGGI)
        df = pd.DataFrame(ws.get_all_records())
        df = normalizza_colonne(df)

        colonne = [
            "Cliente", "Impianto", "DataLavaggio", "Orario", "Telefono",
            "EmailCliente", "Stato", "Fornitore", "Promemoria30gg",
            "DataPromemoria", "Promemoria3gg", "DataPromemoria3gg",
            "DataWA30gg", "DataWA3gg", "Note", "EventoCalendarioCreato",
            "DataEventoCreato", "Task_Rem", "Task_Due",
        ]
        df = assicurati_colonne(df, colonne)

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
            re.sub(r"\s+", "", h).strip().lower(): i + 1
            for i, h in enumerate(headers)
        }

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

    except Exception as e:
        st.error(f"Errore salvataggio: {e}")
        return False


# ==========================================================
# 4. AUTENTICAZIONE DA FOGLIO UTENTI
# ==========================================================
@st.cache_data(ttl=300, show_spinner=False)
def carica_utenti():
    try:
        ws = get_ws_by_name(FOGLIO_UTENTI)
        utenti = pd.DataFrame(ws.get_all_records())
        utenti.columns = [str(c).strip().lower() for c in utenti.columns]

        required = {"username", "password_hash", "ruolo"}
        if not required.issubset(set(utenti.columns)):
            st.error("Il foglio utenti deve avere le colonne: username, password_hash, ruolo")
            return pd.DataFrame()

        utenti["username"] = utenti["username"].astype(str).str.strip()
        utenti["password_hash"] = utenti["password_hash"].astype(str).str.strip()
        utenti["ruolo"] = utenti["ruolo"].astype(str).str.strip().str.lower()

        return utenti

    except Exception as e:
        st.error(f"Errore caricamento utenti: {e}")
        return pd.DataFrame()


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
    password_hash = record["password_hash"]

    if verifica_bcrypt(password, password_hash):
        st.session_state.loggato = True
        st.session_state.utente = record["username"]
        st.session_state.ruolo = record["ruolo"]
        st.success("Accesso effettuato")
        st.rerun()
    else:
        st.error("Credenziali errate")


def logout():
    st.session_state.loggato = False
    st.session_state.utente = None
    st.session_state.ruolo = "ospite"
    st.rerun()


# ==========================================================
# 5. SESSIONE E MODELLI
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

is_admin = st.session_state.ruolo == "admin"
can_edit_client = st.session_state.ruolo in ["admin", "supervisor"]
can_send_comms = st.session_state.ruolo in ["admin", "supervisor"]

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

if FILE_MODELLI.exists():
    with open(FILE_MODELLI, "r", encoding="utf-8") as f:
        modelli = MODELLI_DEFAULT | json.load(f)
else:
    modelli = MODELLI_DEFAULT

st.session_state.modelli = modelli


def compila_testo(testo, row, data, orario):
    return (
        str(testo)
        .replace("[CLIENTE]", str(row.get("Cliente", "")))
        .replace("[DATA]", data)
        .replace("[ORARIO]", str(orario))
        .replace("[IMPIANTO]", str(row.get("Impianto", "")))
    )


# ==========================================================
# 6. SIDEBAR
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
        st.session_state.df = carica_dati()
        st.rerun()


# ==========================================================
# 7. DASHBOARD
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

    df_tutti = df.sort_values(by="Cliente")
    df_conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
    df_urg = df[
        (df["GiorniMancanti"].between(0, 15))
        & (df["Stato"].str.upper() != "FATTO")
    ]
    df_comp = df[df["Stato"].str.upper() == "FATTO"]
    df_da_fare = df[
        (df["Stato"].str.upper() != "FATTO")
        & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ]

    k_cols = st.columns(5)
    kpis = [
        ("Tutti", len(df_tutti)),
        ("Confermati", len(df_conf)),
        ("Urgenze", len(df_urg)),
        ("Completati", len(df_comp)),
        ("Da Fare", len(df_da_fare)),
    ]

    for i, (name, count) in enumerate(kpis):
        with k_cols[i]:
            active = "kpi-active" if st.session_state.dash_filter == name else ""
            st.markdown(
                f'<div class="kpi-box {active}"><p class="kpi-val">{count}</p><p class="kpi-lab">{name}</p></div>',
                unsafe_allow_html=True,
            )
            if st.button(name, key=f"f_{name}"):
                st.session_state.dash_filter = name
                st.rerun()

    st.divider()

    if st.session_state.dash_filter == "Tutti":
        df_view = df_tutti
    elif st.session_state.dash_filter == "Confermati":
        df_view = df_conf
    elif st.session_state.dash_filter == "Urgenze":
        df_view = df_urg
    elif st.session_state.dash_filter == "Completati":
        df_view = df_comp
    else:
        df_view = df_da_fare

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
                dot = "🟢"
            elif stato == "ANNULLATO DA CLIENTE":
                dot = "⚪"
            elif gm <= 3:
                dot = "🔴"
            elif gm <= 15:
                dot = "🟡"
            else:
                dot = "⚪"

            label = f"{dot} {r['DataLavaggio']} - {str(r['Cliente']).upper()}"
            if st.button(label, key=f"sel_{idx}"):
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

            def val_invio(v):
                return str(v).strip() if pd.notna(v) and str(v).strip() else "—"

            box_style = "background:#f8fafc; padding:12px 8px; border-radius:12px; border:1px solid #e2e8f0; text-align:center;"
            i1.markdown(f"<div style='{box_style}'><b>Mail 30gg</b><br>{val_invio(row.get('DataPromemoria',''))}</div>", unsafe_allow_html=True)
            i2.markdown(f"<div style='{box_style}'><b>WA 30gg</b><br>{val_invio(row.get('DataWA30gg',''))}</div>", unsafe_allow_html=True)
            i3.markdown(f"<div style='{box_style}'><b>Mail 3gg</b><br>{val_invio(row.get('DataPromemoria3gg',''))}</div>", unsafe_allow_html=True)
            i4.markdown(f"<div style='{box_style}'><b>WA 3gg</b><br>{val_invio(row.get('DataWA3gg',''))}</div>", unsafe_allow_html=True)

            st.write("")

            c1, c2 = st.columns(2)
            n_cl = c1.text_input("Nome Cliente", row["Cliente"], disabled=not can_edit_client)
            n_im = c2.text_input("Impianto", row["Impianto"], disabled=not can_edit_client)

            c3, c4, c5 = st.columns(3)
            d_dt = row["DataLavaggio_DT"] if pd.notna(row["DataLavaggio_DT"]) else date.today()
            n_dt = c3.date_input("Data Lavaggio", d_dt, format="DD/MM/YYYY", disabled=not can_edit_client)
            n_or = c4.text_input("Orario", row["Orario"], disabled=not can_edit_client)

            stati = [
                "DA PROGRAMMARE",
                "AVVISATO CLIENTE",
                "CONFERMATO DA CLIENTE",
                "FATTO",
                "ANNULLATO DA CLIENTE",
            ]
            curr_st = row["Stato"] if row["Stato"] in stati else "DA PROGRAMMARE"
            n_st = c5.selectbox("Stato", stati, index=stati.index(curr_st), disabled=not can_edit_client)

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
                        "DataLavaggio": n_dt.strftime("%d/%m/%Y"),
                        "Orario": n_or,
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
                col_data = "DataPromemoria3gg" if tipo == "3" else "DataPromemoria"
                col_flag = "Promemoria3gg" if tipo == "3" else "Promemoria30gg"

                if salva_sheet(st.session_state.selected_idx, {
                    col_data: date.today().strftime("%d/%m/%Y"),
                    col_flag: "SI",
                    "Stato": "AVVISATO CLIENTE",
                }):
                    url = f"mailto:{n_ml}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank">APRI EMAIL</a>', unsafe_allow_html=True)

            if cb.button(f"💬 WhatsApp {tipo}gg", disabled=not can_send_comms):
                txt = compila_testo(mod[f"wa_{tipo}_txt"], row, data_txt, n_or)
                num = "".join(filter(str.isdigit, str(n_tel)))
                if num.startswith("3") and len(num) == 10:
                    num = "39" + num

                col_data = f"DataWA{tipo}gg"
                col_flag = "Promemoria3gg" if tipo == "3" else "Promemoria30gg"

                if salva_sheet(st.session_state.selected_idx, {
                    col_data: date.today().strftime("%d/%m/%Y"),
                    col_flag: "SI",
                    "Stato": "AVVISATO CLIENTE",
                }):
                    url = f"https://wa.me/{num}?text={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank">APRI WHATSAPP</a>', unsafe_allow_html=True)

            if cc.button("👷 Email Fornitore", disabled=not can_send_comms or n_st != "CONFERMATO DA CLIENTE"):
                ogg = compila_testo(mod["mail_forn_ogg"], row, data_txt, n_or)
                txt = compila_testo(mod["mail_forn_txt"], row, data_txt, n_or)
                url = f"mailto:{mod['mail_fornitore']}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}"
                st.markdown(f'<a href="{url}" target="_blank">AVVISA FORNITORE</a>', unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)


# ==========================================================
# 8. MODELLI
# ==========================================================
elif pagina == "Modelli Messaggi":
    st.title("📝 Modelli Messaggi")

    mod = st.session_state.modelli

    mod["mail_fornitore"] = st.text_input(
        "Email Fornitore",
        mod.get("mail_fornitore", ""),
        disabled=not is_admin,
    )

    with st.expander("Email Clienti", expanded=True):
        c1, c2 = st.columns(2)
        mod["mail_30_ogg"] = c1.text_input("Oggetto 30gg", mod["mail_30_ogg"], disabled=not is_admin)
        mod["mail_30_txt"] = c1.text_area("Testo 30gg", mod["mail_30_txt"], disabled=not is_admin)
        mod["mail_3_ogg"] = c2.text_input("Oggetto 3gg", mod["mail_3_ogg"], disabled=not is_admin)
        mod["mail_3_txt"] = c2.text_area("Testo 3gg", mod["mail_3_txt"], disabled=not is_admin)

    with st.expander("WhatsApp", expanded=True):
        mod["wa_30_txt"] = st.text_area("WhatsApp 30gg", mod["wa_30_txt"], disabled=not is_admin)
        mod["wa_3_txt"] = st.text_area("WhatsApp 3gg", mod["wa_3_txt"], disabled=not is_admin)

    with st.expander("Fornitore", expanded=True):
        mod["mail_forn_ogg"] = st.text_input("Oggetto Fornitore", mod["mail_forn_ogg"], disabled=not is_admin)
        mod["mail_forn_txt"] = st.text_area("Testo Fornitore", mod["mail_forn_txt"], disabled=not is_admin)

    if st.button("💾 SALVA MODELLI", type="primary", disabled=not is_admin):
        with open(FILE_MODELLI, "w", encoding="utf-8") as f:
            json.dump(mod, f, indent=4, ensure_ascii=False)
        st.success("Modelli salvati.")


# ==========================================================
# 9. FORNITORI
# ==========================================================
elif pagina == "Fornitori":
    st.title("👷 Resoconto Fornitore")

    limite = date.today() + timedelta(days=30)
    df_f = df[
        (df["DataLavaggio_DT"].between(date.today(), limite))
        & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ].sort_values(by="DataLavaggio_DT")

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
            url = f"mailto:{st.session_state.modelli['mail_fornitore']}?subject=Riepilogo Lavaggi 30gg&body={urllib.parse.quote(testo)}"
            st.markdown(f'<a href="{url}" target="_blank">INVIA AL FORNITORE</a>', unsafe_allow_html=True)


# ==========================================================
# 10. CALENDARIO
# ==========================================================
elif pagina == "Calendario":
    st.title("📅 Esporta Calendario")

    conf = df[
        (df["Stato"].str.upper() == "CONFERMATO DA CLIENTE")
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
                salva_sheet(i, {
                    "EventoCalendarioCreato": "SI",
                    "DataEventoCreato": datetime.now().strftime("%d/%m/%Y %H:%M"),
                })
            st.success("Eventi segnati come esportati.")


# ==========================================================
# 11. GESTIONE UTENTI
# ==========================================================
elif pagina == "Gestione Utenti":
    st.title("👤 Gestione Utenti")

    if not is_admin:
        st.warning("Accesso riservato agli amministratori.")
        st.stop()

    utenti = carica_utenti()
    st.dataframe(utenti[["username", "ruolo"]], use_container_width=True)

    st.info(
        "Le password sono salvate come hash bcrypt nel foglio utenti. "
        "Per aggiungere o modificare un utente, aggiorna il foglio con colonne username, password_hash, ruolo."
    )


# ==========================================================
# 12. IMPOSTAZIONI
# ==========================================================
elif pagina == "Impostazioni":
    st.title("⚙️ Diagnostica")

    st.write(f"Utente: **{st.session_state.utente or 'ospite'}**")
    st.write(f"Ruolo: **{st.session_state.ruolo}**")
    st.write(f"Foglio lavaggi: **{FOGLIO_LAVAGGI}**")
    st.write(f"Foglio utenti: **{FOGLIO_UTENTI}**")

    st.dataframe(df, use_container_width=True)
