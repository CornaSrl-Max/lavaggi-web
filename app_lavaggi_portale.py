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
