
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
