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
# 1. CONFIGURAZIONE E ACCESSO
# ==========================================================
st.set_page_config(
    page_title="FV WASH MANAGER",
    layout="wide",
    page_icon="🧼",
    initial_sidebar_state="expanded",
)

# Password di accesso
PASSWORD_CORRETTA = st.secrets.get("password_portale", "admin123")

if "autenticato" not in st.session_state:
    st.session_state.autenticato = False

def login():
    if st.session_state.pwd_input == PASSWORD_CORRETTA:
        st.session_state.autenticato = True
    else:
        st.error("Password errata")

def logout():
    st.session_state.autenticato = False
    st.rerun()

# ==========================================================
# 2. COSTANTI E DATI
# ==========================================================
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
# 3. STILE CSS (FIX PULSANTI E VISIBILITÀ)
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
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }
    
    /* KPI Dashboard */
    .kpi-box {
        background: white; padding: 15px; border-radius: 18px; text-align: center;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.3s; margin-bottom: 10px;
    }
    .kpi-active { border: 2px solid #2563eb; background: #f0f7ff; transform: translateY(-5px); }
    .kpi-icon { font-size: 30px; margin-bottom: 5px; display: block; }
    .kpi-val { font-size: 24px; font-weight: 800; color: #1e293b; margin: 0; }
    .kpi-lab { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; }

    /* Fix Pulsanti Sidebar */
    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #f8fafc !important; }
    
    /* Pulsanti nella Sidebar: Sfondo scuro, testo bianco per visibilità */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #1e293b !important;
        color: white !important;
        border: 1px solid #334155 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #334155 !important;
        border-color: #2563eb !important;
    }

    /* Stato Colorato */
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
""", unsafe_allow_html=True)

# ==========================================================
# 4. LOGICA DATI
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
    if not st.session_state.autenticato: return False
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

def carica_modelli():
    d = {
        "fornitori": ["BG Service (commerciale@bgservicebergamo.com)"],
        "mail_fornitore": "commerciale@bgservicebergamo.com",
        "mail_30_ogg": "Lavaggio FV [CLIENTE]", 
        "mail_30_txt": "Lavaggio programmato il [DATA] ore [ORARIO]", 
        "wa_30_txt": "Buongiorno, lavaggio FV programmato il [DATA] ore [ORARIO]", 
        "mail_3_ogg": "Promemoria Lavaggio FV [CLIENTE]", 
        "mail_3_txt": "Le ricordiamo l'appuntamento del [DATA] ore [ORARIO]", 
        "wa_3_txt": "Promemoria: lavaggio FV domani [DATA] ore [ORARIO]", 
        "mail_forn_ogg": "Conferma intervento lavaggio - [CLIENTE]", 
        "mail_forn_txt": "Buongiorno, confermiamo intervento per il cliente [CLIENTE] il giorno [DATA] ore [ORARIO]."
    }
    if FILE_MODELLI.exists():
        with open(FILE_MODELLI, "r", encoding="utf-8") as f: d.update(json.load(f))
    return d

if "modelli" not in st.session_state: st.session_state.modelli = carica_modelli()

# ==========================================================
# 5. SIDEBAR
# ==========================================================
with st.sidebar:
    st.markdown("### 🧼 FV WASH MANAGER")
    
    if not st.session_state.autenticato:
        st.text_input("Password Amministratore", type="password", key="pwd_input", on_change=login)
    else:
        st.success("✅ Modalità Modifica")
        if st.button("🔓 Logout"): logout()

    st.divider()
    pagina = st.radio("Navigazione", ["Dashboard", "Modelli Messaggi", "Calendario", "Impostazioni"])
    
    st.divider()
    st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)
    
    if st.button("🔄 Aggiorna Dati"): 
        st.session_state.df = carica_dati(); st.rerun()

# ==========================================================
# 6. DASHBOARD
# ==========================================================
if st.session_state.df is None: st.session_state.df = carica_dati()
df = st.session_state.df
is_read_only = not st.session_state.autenticato

if pagina == "Dashboard":
    st.markdown('<div class="hero"><h1>FV WASH MANAGER</h1><p>Controllo Operativo Interventi</p></div>', unsafe_allow_html=True)
    
# --- LOGICA FILTRI KPI ---
    # 1. Tutti: Ordine alfabetico per Cliente
    df_tutti = df.sort_values(by="Cliente")
    
    # 2. Confermati: Ordine cronologico per data
    df_conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"].sort_values(by="DataLavaggio_DT", na_position="last")
    
    # 3. Urgenze: Prossimi 15gg (non confermati/fatti), ordine cronologico
    df_urg = df[
        (df["GiorniMancanti"].between(0, 15)) & 
        (df["Stato"].str.upper() != "CONFERMATO DA CLIENTE") & 
        (df["Stato"].str.upper() != "FATTO")
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    
    # 4. Completati (Stato: FATTO): Ordine cronologico
    df_comp = df[df["Stato"].str.upper() == "FATTO"].sort_values(by="DataLavaggio_DT", na_position="last")
    
    # 5. Da Fare: Non Fatti e Non Annullati, ORDINE CRONOLOGICO
    df_da_fare = df[
        (df["Stato"].str.upper() != "FATTO") & 
        (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    
    # 6. Annullati: Ordine cronologico
    df_annullati = df[df["Stato"].str.upper() == "ANNULLATO DA CLIENTE"].sort_values(by="DataLavaggio_DT", na_position="last")

    k_cols = st.columns(6)
    kpis = [("Tutti", "📋", len(df_tutti)), ("Confermati", "👍", len(df_conf)), ("Urgenze", "🔥", len(df_urg)), 
            ("Completati", "✅", len(df_comp)), ("Da Fare", "🛠️", len(df_da_fare)), ("Annullati", "❌", len(df_annullati))]
    
    for i, (name, icon, count) in enumerate(kpis):
        with k_cols[i]:
            active = "kpi-active" if st.session_state.dash_filter == name else ""
            st.markdown(f'<div class="kpi-box {active}"><span class="kpi-icon">{icon}</span><p class="kpi-val">{count}</p><p class="kpi-lab">{name}</p></div>', unsafe_allow_html=True)
            if st.button(name, key=f"f_{name}", use_container_width=True):
                st.session_state.dash_filter = name; st.rerun()

    st.divider()

    # Selezione DataFrame vista
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
        
        for idx, r in df_attivi.head(40).iterrows():
            lbl = f"{r['DataLavaggio']}      {str(r['Cliente']).upper()}"
            st.button(lbl, key=f"sel_{idx}", use_container_width=True, on_click=lambda i=idx: st.session_state.update({"selected_idx": i}))
        
        if not df_sospesi.empty and st.session_state.dash_filter in ["Tutti", "Da Fare", "Annullati"]:
            with st.expander("📁 AREA SOSPESI / ANNULLATI", expanded=False):
                for idx, r in df_sospesi.iterrows():
                    lbl = f"[{r['Stato'] or 'Senza Data'}]      {str(r['Cliente']).upper()}"
                    st.button(lbl, key=f"sel_{idx}", use_container_width=True, on_click=lambda i=idx: st.session_state.update({"selected_idx": i}))

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(f'<div class="card"><h2>{row["Cliente"]}</h2>', unsafe_allow_html=True)
            
            c_1, c_2 = st.columns(2)
            n_cliente = c_1.text_input("Nome Cliente", row["Cliente"], disabled=is_read_only)
            n_impianto = c_2.text_input("Impianto", row["Impianto"], disabled=is_read_only)
            
            c_3, c_4, c_5 = st.columns(3)
            default_date = row["DataLavaggio_DT"] if pd.notna(row["DataLavaggio_DT"]) else date.today()
            n_date = c_3.date_input("Data Lavaggio", default_date, format="DD/MM/YYYY", disabled=is_read_only)
            n_ora = c_4.text_input("Orario", row["Orario"], disabled=is_read_only)
            
            stati_list = ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO DA CLIENTE"]
            current_st = row["Stato"] if row["Stato"] in stati_list else "DA PROGRAMMARE"
            st_class = "st-da-programmare"
            if "AVVISATO" in current_st: st_class = "st-avvisato"
            elif "CONFERMATO" in current_st: st_class = "st-confermato"
            elif "FATTO" in current_st: st_class = "st-fatto"
            elif "ANNULLATO" in current_st: st_class = "st-annullato"
            
            with c_5:
                st.markdown(f'<div class="status-container {st_class}">{current_st}</div>', unsafe_allow_html=True)
                n_st = st.selectbox("Cambia Stato", stati_list, index=stati_list.index(current_st), label_visibility="collapsed", disabled=is_read_only)
            
            c_6, c_7 = st.columns(2)
            n_tel = c_6.text_input("Telefono", row["Telefono"], disabled=is_read_only)
            n_mail = c_7.text_input("Email", row["EmailCliente"], disabled=is_read_only)
            n_note = st.text_area("Note", row["Note"], height=70, disabled=is_read_only)
            
            if st.button("💾 AGGIORNA DATI CLIENTE", use_container_width=True, type="primary", disabled=is_read_only):
                mappa = {"Cliente": n_cliente, "Impianto": n_impianto, "DataLavaggio": n_date.strftime("%d/%m/%Y"), "Orario": n_ora, "Stato": n_st, "Telefono": n_tel, "EmailCliente": n_mail, "Note": n_note}
                if salva_sheet(st.session_state.selected_idx, mappa):
                    st.success("Dati aggiornati!"); st.session_state.df = carica_dati(); st.rerun()
            
            st.divider()
            st.markdown("#### 🚀 Invio Comunicazioni")
            tipo = "3" if (pd.notna(row['GiorniMancanti']) and row['GiorniMancanti'] <= 5) else "30"
            mod = st.session_state.modelli
            data_s = n_date.strftime("%d/%m/%Y")
            
            def comp(t, r, d, o): return t.replace("[CLIENTE]", r['Cliente']).replace("[DATA]", d).replace("[ORARIO]", o).replace("[IMPIANTO]", r['Impianto'])

            ca, cb = st.columns(2)
            if ca.button(f"✉️ Email {tipo}gg", use_container_width=True, disabled=is_read_only):
                ogg = comp(mod[f"mail_{tipo}_ogg"], row, data_s, n_ora); txt = comp(mod[f"mail_{tipo}_txt"], row, data_s, n_ora)
                col_s = "DataPromemoria3gg" if tipo == "3" else "DataPromemoria"
                if salva_sheet(st.session_state.selected_idx, {col_s: date.today().strftime("%d/%m/%Y"), "Stato": "AVVISATO CLIENTE"}):
                    url = f"mailto:{n_mail}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank" style="text-decoration:none;"><div style="background:#2563eb;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">APRI EMAIL</div></a>', unsafe_allow_html=True)

            if cb.button(f"💬 WhatsApp {tipo}gg", use_container_width=True, disabled=is_read_only):
                txt = comp(mod[f"wa_{tipo}_txt"], row, data_s, n_ora); num = "".join(filter(str.isdigit, n_tel))
                if num.startswith("3") and len(num) == 10: num = "39" + num
                col_s = "DataWA3gg" if tipo == "3" else "DataWA30gg"
                if salva_sheet(st.session_state.selected_idx, {col_s: date.today().strftime("%d/%m/%Y"), "Stato": "AVVISATO CLIENTE"}):
                    url = f"https://wa.me/{num}?text={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank" style="text-decoration:none;"><div style="background:#16a34a;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">APRI WHATSAPP</div></a>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================================
# 7. MODELLI MESSAGGI
# ==========================================================
elif pagina == "Modelli Messaggi":
    st.markdown("## 📝 Personalizzazione Messaggi")
    
    st.markdown("""
        <div class="placeholder-box">
            <b>🛠️ Campi Utilizzabili:</b> [CLIENTE], [DATA], [ORARIO], [IMPIANTO]
        </div>
    """, unsafe_allow_html=True)
    
    mod = st.session_state.modelli
    
    st.markdown("#### 🏢 Email Fornitore")
    mod["mail_fornitore"] = st.text_input("Email predefinita Fornitore", mod.get("mail_fornitore", ""))
    
    st.divider()

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.subheader("✉️ Email 30gg")
        mod["mail_30_ogg"] = st.text_input("Oggetto (30gg)", mod["mail_30_ogg"], disabled=is_read_only)
        mod["mail_30_txt"] = st.text_area("Testo (30gg)", mod["mail_30_txt"], height=150, disabled=is_read_only)
    with col_e2:
        st.subheader("✉️ Email 3gg")
        mod["mail_3_ogg"] = st.text_input("Oggetto (3gg)", mod["mail_3_ogg"], disabled=is_read_only)
        mod["mail_3_txt"] = st.text_area("Testo (3gg)", mod["mail_3_txt"], height=150, disabled=is_read_only)

    st.divider()

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        st.subheader("💬 WhatsApp 30gg")
        mod["wa_30_txt"] = st.text_area("Testo WA (30gg)", mod["wa_30_txt"], height=150, disabled=is_read_only)
    with col_w2:
        st.subheader("💬 WhatsApp 3gg")
        mod["wa_3_txt"] = st.text_area("Testo WA (3gg)", mod["wa_3_txt"], height=150, disabled=is_read_only)

    st.divider()

    st.subheader("👷 Email al Fornitore")
    mod["mail_forn_ogg"] = st.text_input("Oggetto Email Fornitore", mod["mail_forn_ogg"], disabled=is_read_only)
    mod["mail_forn_txt"] = st.text_area("Testo Email Fornitore", mod["mail_forn_txt"], height=150, disabled=is_read_only)

    if st.button("💾 SALVA CONFIGURAZIONE MODELLI", use_container_width=True, type="primary", disabled=is_read_only):
        with open(FILE_MODELLI, "w", encoding="utf-8") as f: json.dump(mod, f, indent=4, ensure_ascii=False)
        st.success("Modelli salvati correttamente!")

elif pagina == "Calendario":
    st.markdown("## 📅 Esporta")
    # Logica Calendario ICS invariata...

elif pagina == "Impostazioni":
    st.markdown("## ⚙️ Diagnostica")
    st.dataframe(df)
