import io
from pypdf import PdfReader
from docx import Document

import streamlit as st

import google.generativeai as genai

import json

import os

import glob
import uuid

from PIL import Image

import streamlit.components.v1 as components



# ==============================================================================

# 1. CONFIGURAZIONE FILE SYSTEM E COSTANTI

# ==============================================================================

CARTELLA_CHAT = "chat_saved"

EXT = ".json"

STATS_FILE = "lifetime_stats.json"



if not os.path.exists(CARTELLA_CHAT):
    os.makedirs(CARTELLA_CHAT)
if not os.path.exists(os.path.join(CARTELLA_CHAT, "generated_videos")):
    os.makedirs(os.path.join(CARTELLA_CHAT, "generated_videos"))



# ==============================================================================

# 2. DEFINIZIONE MODELLI E LIMITI

# ==============================================================================

CONFIG_MODELLI = {

    "preview 3 Pro": {"id": "gemini-3-pro-preview", "limit": 5_000_000, "tier": "pro"},

    "preview 3 Flash": {"id": "gemini-3-flash-preview", "limit": 3_000_000, "tier": "flash"},

    "Gemini 2.5 Pro": {"id": "gemini-2.5-pro", "limit": 5_000_000, "tier": "pro"},

    "Gemini 2.5 Flash": {"id": "gemini-2.5-flash", "limit": 3_000_000, "tier": "flash"},

    "Gemini 2.5 Flash-Lite": {"id": "gemini-2.5-flash-lite", "limit": 10_000_000, "tier": "lite"},

    "Gemini 2.0 Flash": {"id": "gemini-2.0-flash", "limit": 10_000_000, "tier": "flash"},

    "Gemini 2.0 Flash Image": {"id": "gemini-2.0-flash-image", "limit": 3_000_000, "tier": "flash"},

    "Gemini 2.0 Flash-Lite": {"id": "gemini-2.0-flash-lite", "limit": 10_000_000, "tier": "lite"},
    
}


IDS_PESANTI = [ "gemini-2.5-flash-image",
                "gemini-2.0-flash-image",
                "gemini-2.0-flash",
                "gemini-3-flash-preview",
               "gemini-2.5-flash-tts",
               "gemini-2.5-pro-tts",
               "gemini-2.5-pro", 
               "gemini-3-pro-preview", 
               "gemini-3-pro-image-preview",
               "gemini-2.5-flash",
               "veo-2.0-generate-001"]

ID_MODELLO_LITE = "gemini-2.5-flash-lite"

# ==============================================================================
# CONFIGURAZIONE PREZZI (Aggiornata al Listino Google Feb 2026)
# ==============================================================================
# NOTE: 
# - I prezzi sono in USD ($).
# - "tier_limit": soglia di token (es. 200.000) oltre la quale il prezzo aumenta (solo per Pro).
# - "input_1": Prezzo Input sotto soglia / "input_2": Prezzo Input sopra soglia.
# - "output_1": Prezzo Output sotto soglia / "output_2": Prezzo Output sopra soglia.

PRICING_TABLE = {
    # --- GEMINI 3 SERIES ---
    "gemini-3-pro-preview": {
        "type": "text_tier",
        "tier_limit": 200_000,
        "input_1": 2.00,   "input_2": 4.00,
        "output_1": 12.00, "output_2": 18.00
    },
    "gemini-3-flash-preview": {
        "type": "text_flat",
        "input": 0.50,
        "output": 3.00
    },
    # Modello Immagine: Input come testo Pro, Output per immagine generata
    "gemini-3-pro-image-preview": {
        "type": "image_gen",
        "input_price_per_1m": 2.00,  # Prezzo input testo
        "price_per_img": 0.134       # $0.134 per immagine standard (<2K)
    },

    # --- GEMINI 2.5 SERIES ---
    "gemini-2.5-pro": {
        "type": "text_tier",
        "tier_limit": 200_000,
        "input_1": 1.25,   "input_2": 2.50,
        "output_1": 10.00, "output_2": 15.00
    },
    "gemini-2.5-flash": {
        "type": "text_flat",
        "input": 0.30, 
        "output": 2.50
    },
    "gemini-2.5-flash-lite": {
        "type": "text_flat",
        "input": 0.10, 
        "output": 0.40
    },
    "gemini-2.5-flash-image": {
        "type": "image_gen",
        "input_price_per_1m": 0.30,
        "price_per_img": 0.039       # $0.039 per immagine standard
    },

    # --- GEMINI 2.0 SERIES ---
    "gemini-2.0-flash": {
        "type": "text_flat",
        "input": 0.10, 
        "output": 0.40
    },
    "gemini-2.0-flash-lite": {
        "type": "text_flat",
        "input": 0.075, 
        "output": 0.30
    },

    # --- VIDEO & ALTRI ---
    "veo-2.0-generate-001": {
        "type": "video",
        "price_per_sec": 0.35 
    },
    # Fallback Generico
    "default": {
        "type": "text_flat",
        "input": 0.30, "output": 1.00
    }
}




# ==============================================================================

# 3. INTERFACCIA UTENTE: SETUP E CUSTOM CSS (CYBERPUNK DARK)

# ==============================================================================

st.set_page_config(page_title="My Gemini", page_icon="🌑", layout="wide")



st.markdown("""
<style>
/* 1. VARIABILI GLOBALI */
:root {
    --bg-color: #0b141a;
    --sidebar-bg: #111b21;
    --user-msg-bg: #005c4b;
    --bot-msg-bg: #202c33;
    --text-color: #e9edef;
    --input-bg: #2a3942;
    --accent-color: #00a884;
    --cyber-gray: #262730;
    --neon-purple: #7e22ce;
    --neon-red: #ff0055;
    --text-gray: #a0a0a0;
}

/* 2. BACKGROUND E TESTO BASE */
.stApp { background-color: var(--bg-color); color: var(--text-color); }
section[data-testid="stSidebar"] { background-color: var(--sidebar-bg); border-right: 1px solid #333; }
h1, h2, h3, p, label, li, span, div { color: var(--text-color) !important; }

/* FIX HEADER & FOOTER */
header[data-testid="stHeader"] { background-color: var(--bg-color) !important; }
div[data-testid="stDecoration"] { display: none; }
footer, .stDeployButton { display: none !important; visibility: hidden !important; }

/* FIX CONTENITORE INPUT */
div[data-testid="stBottomBlockContainer"] {
    background-color: var(--bg-color) !important;
    border-top: 1px solid #333;
    padding-bottom: 20px; 
}
div[data-testid="stBottomBlockContainer"] > div { background-color: var(--bg-color) !important; }

/* SCROLLBAR */
::-webkit-scrollbar { width: 16px; height: 16px; }
::-webkit-scrollbar-track { background: #1a1a1a; }
::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #ff0055, #7e22ce) !important;
    border-radius: 8px;
    border: 2px solid var(--bg-color);
}
::-webkit-scrollbar-thumb:hover, ::-webkit-scrollbar-thumb:active {
    background: linear-gradient(180deg, #ff0055, #7e22ce) !important;
}

/* STILE INPUT BARRA LATERALE */
section[data-testid="stSidebar"] .stTextInput input {
    background-color: var(--cyber-gray) !important;
    color: var(--text-gray) !important;
    border: 2px solid var(--neon-purple) !important;
    border-radius: 8px;
}
section[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: var(--neon-red) !important;
    color: white !important;
    box-shadow: 0 0 8px rgba(255, 0, 85, 0.4);
}

/* --- STILE BOTTONI ICONA (MATITA & CESTINO) --- */
section[data-testid="stSidebar"] .stButton button {
    background-color: var(--cyber-gray) !important; 
    border: 1px solid var(--neon-purple) !important;
    border-radius: 8px !important;
    color: white !important; 
    box-shadow: 0 0 5px rgba(126, 34, 206, 0.2) !important;
    transition: all 0.3s ease !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background-color: var(--cyber-gray) !important; 
    border-color: var(--neon-red) !important;
    color: var(--neon-red) !important; 
    box-shadow: 0 0 15px rgba(255, 0, 85, 0.6) !important;
    transform: translateY(-1px);
}
section[data-testid="stSidebar"] .stButton button:active,
section[data-testid="stSidebar"] .stButton button:focus:not(:active) {
    background-color: #1a1a20 !important; 
    border-color: var(--neon-red) !important;
    color: white !important;
    box-shadow: inset 0 0 5px rgba(0,0,0,0.8) !important;
    outline: none !important;
}

/* FIX TOOLTIP */
div[role="tooltip"] {
    background-color: var(--sidebar-bg) !important;
    color: white !important;
    border: 1px solid var(--neon-purple) !important;
    border-radius: 6px !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
}
div[role="tooltip"] > div {
    color: #e9edef !important; 
    font-size: 14px !important;
}

/* HACK: FLOATING PAPERCLIP */
div[data-testid="stPopover"] {
    position: fixed !important;
    bottom: 80px !important;
    left: 20px !important;
    z-index: 999999 !important;
    width: auto !important;
}
div[data-testid="stPopover"] button {
    border-radius: 50% !important;
    width: 50px !important;
    height: 50px !important;
    background-color: var(--cyber-gray) !important;
    border: 2px solid var(--neon-purple) !important;
    color: var(--text-gray) !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    padding: 0 !important;
    transition: all 0.3s ease !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
div[data-testid="stPopover"] button:hover {
    background-color: var(--cyber-gray) !important; 
    border-color: var(--neon-red) !important;
    color: var(--neon-red) !important;
    box-shadow: 0 0 15px var(--neon-red) !important;
    transform: scale(1.1) !important;
}
div[data-testid="stPopoverBody"] {
    background-color: var(--sidebar-bg) !important;
    border: 1px solid var(--neon-purple) !important;
    color: white !important;
}
div[data-testid="stPopoverBody"] p, 
div[data-testid="stPopoverBody"] span, 
div[data-testid="stPopoverBody"] div,
div[data-testid="stPopoverBody"] h1, div[data-testid="stPopoverBody"] h2, div[data-testid="stPopoverBody"] h3,
div[data-testid="stPopoverBody"] small, 
div[data-testid="stPopoverBody"] label {
    color: white !important;
}

section[data-testid="stFileUploaderDropzone"] {
    background-color: var(--cyber-gray) !important;
    border: 1px dashed var(--neon-purple) !important;
}
div[data-testid="stFileUploader"] button {
    background-color: var(--input-bg) !important;
    color: white !important; 
    border: 1px solid #555 !important;
}

/* --- FIX VERO: NOME FILE E DIMENSIONE --- */
div[data-testid="stFileUploaderFile"] {
    background-color: #e0e0e0 !important;
    border: 1px solid #00a884 !important;
}
div[data-testid="stFileUploaderFile"] p,
div[data-testid="stFileUploaderFile"] div,
div[data-testid="stFileUploaderFile"] span,
div[data-testid="stFileUploaderFile"] small {
    color: #000000 !important;
    text-shadow: none !important;
}
div[data-testid="stFileUploaderFile"] svg {
    fill: #000000 !important;
    color: #000000 !important;
}
div[data-testid="stFileUploaderFile"] button {
    color: #333333 !important;
}

/* --- FIX VERO: BLOCCO COPIA (BIANCO SU NERO) --- */
/* Forza lo sfondo chiaro per il blocco codice (stessa logica dell'uploader) */
div[data-testid="stCode"] {
    background-color: #e0e0e0 !important;
    border: 1px solid #00a884 !important;
    border-radius: 8px !important;
}
/* Forza il testo NERO assoluto */
div[data-testid="stCode"] code,
div[data-testid="stCode"] span,
div[data-testid="stCode"] pre {
    color: #000000 !important;
    text-shadow: none !important;
    background-color: transparent !important; /* Via sfondi strani */
    font-family: 'Consolas', 'Courier New', monospace !important;
}
/* Forza l'icona copia NERA */
div[data-testid="stCode"] button {
    color: #000000 !important;
}
div[data-testid="stCode"] svg {
    fill: #000000 !important;
    color: #000000 !important;
}

/* INPUT BAR CHAT */
.stChatInput textarea {
    background-color: var(--input-bg) !important;
    color: white !important;
    border: 1px solid #444 !important;
}
input::placeholder, textarea::placeholder { color: #cccccc !important; opacity: 1; }

/* LISTA CHAT */
div[role="radiogroup"] > label > div:first-of-type { display: none; }
div[role="radiogroup"] label {
    background-color: #1e2126;
    padding: 6px 12px;
    margin-bottom: 5px;
    border-radius: 6px;
    border: 1px solid #2d3035;
    color: #ccc !important;
}
div[role="radiogroup"] label:hover {
    border-color: var(--accent-color);
    background-color: #262930;
    color: white !important;
}
div[role="radiogroup"] label[data-checked="true"] {
    background: linear-gradient(90deg, #005c4b 0%, #00a884 100%);
    border: none;
    color: white !important;
    font-weight: bold;
}

/* --- LAYOUT BOLLE (LARGHEZZA FISSA 89%) --- */
div[data-testid="stChatMessageAvatar"] { display: none !important; }

/* 1. MESSAGGIO UTENTE (User) -> DESTRA & VERDE */
div[data-testid="stChatMessage"]:has(div[data-role="user"]) {
    background-color: rgba(255, 255, 255, 0.07)  !important;
    border: 0px solid ss
    color: #e9edef !important;
    border-radius: 15px 0px 15px 15px !important;
    
    /* Forza larghezza all'89% e spinge a destra */
    margin-left: auto !important;
    margin-right: 0 !important;
    width: 80% !important;
    max-width: 80% !important;
    
    flex-direction: row !important;
    text-align: left;
}

/* 2. MESSAGGIO AI (Assistant) -> SINISTRA & GRIGIO */
div[data-testid="stChatMessage"]:has(div[data-role="assistant"]) {
    border: 0px
    color: #e9edef !important;
    border-radius: 0px 15px 15px 15px !important;
    
    /* Forza larghezza all'89% e spinge a sinistra */
    margin-right: 10px!important;
    margin-left: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
    
    flex-direction: row !important;
    text-align: left;
}

/* Assicura che il contenitore interno occupi tutto lo spazio della bolla */
div[data-testid="stChatMessageContent"] {
    width: 100% !important;
    flex: 1 !important;
}

/* SELECTBOX */
div[data-baseweb="select"] > div {
    background-color: var(--input-bg) !important;
    border-color: #444 !important;
    color: white !important;
}
div[data-baseweb="popover"], div[data-baseweb="menu"], ul[data-baseweb="menu"] {
    background-color: #1e2329 !important;
    border: 1px solid #444 !important;
}
li[role="option"] {
    color: white !important;
    background-color: #1e2329 !important;
}
li[role="option"]:hover {
    background-color: var(--accent-color) !important;
    color: white !important;
}
li[aria-selected="true"] {
    background-color: var(--input-bg) !important;
    color: var(--accent-color) !important;
    font-weight: bold;
}

/* CASELLA NUMERICA CYBERPUNK */
div[data-testid="stNumberInput"] * { background-color: transparent !important; }
div[data-testid="stNumberInput"] > div > div { background-color: var(--cyber-gray) !important; border: 1px solid var(--neon-purple) !important; border-radius: 8px !important; color: white !important; }
div[data-testid="stNumberInput"] div[data-baseweb="input"] { background-color: var(--cyber-gray) !important; border: 1px solid var(--neon-purple) !important; border-radius: 8px !important; color: white !important; }
div[data-testid="stNumberInput"] input { 
    background-color: transparent !important; color: white !important; 
    font-family: 'Courier New', monospace !important; font-weight: bold !important; 
    text-align: center !important; border: none !important; 
    -webkit-text-fill-color: white !important; caret-color: var(--neon-red) !important; min-height: 40px; 
}
div[data-testid="stNumberInput"] button { border: none !important; color: #a0a0a0 !important; border-left: 1px solid #444 !important; }
div[data-testid="stNumberInput"] button:first-of-type { border-left: none !important; border-right: 1px solid #444 !important; }
div[data-testid="stNumberInput"]:hover > div > div { border-color: var(--neon-red) !important; box-shadow: 0 0 10px rgba(255, 0, 85, 0.3) !important; }

/* ============================================================
   FIX VISUALIZZAZIONE CODICE (PULIZIA TOTALE)
   ============================================================ */

/* 1. BLOCCHI DI CODICE GRANDI (quelli con ``` ) */
div[data-testid="stMarkdownContainer"] pre {
    background-color: #1e1e1e !important;   /* Sfondo Grigio Scuro (tipo VS Code) */
    border: 1px solid #444444 !important;   /* Bordo Grigio Sottile (NO VIOLA) */
    border-radius: 8px !important;
    padding: 15px !important;
}

/* 2. IL TESTO DENTRO I BLOCCHI */
div[data-testid="stMarkdownContainer"] code {
    background-color: transparent !important;
    color: #ffffff !important;              /* TESTO BIANCO */
    font-family: 'Consolas', 'Courier New', monospace !important;
    text-shadow: none !important;
}

/* 3. CODICE INLINE (quello singolo con ` ) */
div[data-testid="stMarkdownContainer"] :not(pre) > code {
    background-color: #2d2d2d !important;   /* Sfondo grigio leggermente più chiaro */
    color: #ffffff !important;              /* Testo Bianco */
    border: 1px solid #444 !important;      /* Bordo grigio */
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

/* 4. WIDGET st.code (Se usato manualmente) */
div[data-testid="stCode"] {
    background-color: #1e1e1e !important;
    border: 1px solid #444444 !important;
    border-radius: 8px !important;
}
/* Forza il testo bianco anche qui */
div[data-testid="stCode"] code,
div[data-testid="stCode"] span,
div[data-testid="stCode"] pre {
    color: #ffffff !important;
    background-color: transparent !important;
}

/* 5. BOTTONE COPIA (in alto a destra nel codice) */
div[data-testid="stCode"] button {
    color: #aaaaaa !important;
}
div[data-testid="stCode"] button:hover {
    color: #ffffff !important;
    background-color: rgba(255,255,255,0.1) !important;
}

/* --- TASTI MINIMAL (PIN & COPY) DENTRO LA CHAT --- */
/* Rende i bottoni trasparenti, senza bordi e compatti */
div[data-testid="stChatMessage"] button {
    background-color: transparent !important;
    border: none !important;
    padding: 0px !important;
    min-height: 0px !important;
    height: auto !important;
    color: rgba(255, 255, 255, 0.4) !important; /* Icona semitrasparente */
    font-size: 1.2rem !important;
    transition: all 0.2s !important;
}

/* Quando passi sopra col mouse diventano bianchi e luminosi */
div[data-testid="stChatMessage"] button:hover {
    color: #ffffff !important;
    text-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
    transform: scale(1.2); /* Leggero zoom */
}

/* Nasconde bordo focus rosso */
div[data-testid="stChatMessage"] button:focus {
    box-shadow: none !important;
    border: none !important;
}
/* --- CONTAINER MICROFONO FLUTTUANTE --- */

/* Rimpiccioliamo un po' il player audio nativo */
.floating-audio-container .stAudioInput {
    margin-top: -20px !important; 
    z-index: 99999;
}
/* ============================================================
   FIX MOBILE: SCROLLBAR NASCOSTA & NO TASTO COPIA
   ============================================================ */

@media (max-width: 768px) {
    
    /* 1. NASCONDI LA BARRA DI SCORRIMENTO (SCROLLBAR) */
    /* Funziona su Chrome/Safari/Android/iOS */
    ::-webkit-scrollbar {
        display: none !important;
        width: 0px !important;
        background: transparent !important;
    }
    /* Funziona su Firefox Mobile */
    * {
        scrollbar-width: none !important;
    }

    /* 2. NASCONDI IL TASTO COPIA (📑) NEI MESSAGGI */
    /* Spiegazione: Cerca dentro il messaggio (stChatMessage) il PRIMO bottone che trova.
       Dato che le tue colonne sono [Testo, Copia, Pin], il Copia è il primo bottone fisico. */
    div[data-testid="stChatMessage"] button:first-of-type {
        display: none !important;
    }
}
/* ============================================================
   FIX MOBILE "NUCLEARE": DISTRUZIONE LAYOUT FLEX
   ============================================================ */
@media (max-width: 768px) {

    /* 1. CAMBIA IL COMPORTAMENTO DEL PADRE */
    /* Da 'flex' (oggetti affiancati) a 'block' (uno sopra l'altro o unico) */
    div[data-testid="stChatMessage"] {
        display: block !important; 
        background-color: transparent !important; /* Fix estetico */
    }

    /* 2. ELIMINA COMPLETAMENTE L'AVATAR */
    div[data-testid="stChatMessageAvatar"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* 3. FORZA IL CONTENUTO A PRENDERSI TUTTO */
    div[data-testid="stChatMessageContent"] {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        margin-left: 0 !important;
        padding-left: 0 !important;
    }

    /* 4. FIX SPECIFICO PER I TUOI MESSAGGI UTENTE */
    /* Dato che nel tuo codice Python usi un div interno per il colore verde/grigio,
       dobbiamo assicurarci che anche lui si allarghi */
    div[data-testid="stChatMessageContent"] > div {
        width: 100% !important;
    }
}
/* ============================================================
   FIX DEFINITIVO BARRA INPUT: 
   1. NO "PEZZETTO" COLORATO (Scrollbar nascosta)
   2. NO ARCOBALENI/OMBRE (Stile piatto)
   ============================================================ */

/* 1. Uccidiamo la scrollbar colorata SOLO dentro l'input */
div[data-testid="stChatInput"] textarea::-webkit-scrollbar {
    display: none !important;
    width: 0px !important;
    background: transparent !important;
}


</style>
""", unsafe_allow_html=True)
# ... (DOPO I TUOI IMPORT E PRIMA DEL CSS) ...

# ==============================================================================
# 🔐 SISTEMA DI AUTO-LOGIN (SECRETS + MAGIC LINK)
# ==============================================================================

# 1. Caricamento Automatico API KEY dai Secrets (se esiste)
if "api_key" not in st.session_state:
    if "general" in st.secrets and "api_key" in st.secrets["general"]:
        st.session_state.api_key = st.secrets["general"]["api_key"]
    else:
        st.session_state.api_key = None

# 2. Funzione Controllo Accesso
def check_password():
    """Gestisce il login automatico tramite Link o Manuale"""
    
    # Se siamo già loggati nella sessione, ok
    if st.session_state.get("password_correct", False):
        return True

    # Recupera la password vera dai Secrets (o usa un default se non impostata)
    # NOTA: Imposta i secrets su Streamlit Cloud come spiegato sopra!
    REAL_PASSWORD = st.secrets["general"]["password"] if "general" in st.secrets else "patop"

    # A. CONTROLLO "MAGIC LINK" (Query Params)
    # Permette di entrare con: https://tua-app.streamlit.app/?p=password
    params = st.query_params
    if "p" in params and params["p"] == REAL_PASSWORD:
        st.session_state["password_correct"] = True
        return True

    # B. LOGIN MANUALE (Se non c'è il link magico)
    def password_entered():
        if st.session_state["password_input"] == REAL_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    st.markdown("### 🔒 Accesso Riservato")
    st.text_input(
        "Password", 
        type="password", 
        on_change=password_entered, 
        key="password_input"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("⛔ Password errata")

    return False

# BLOCCA TUTTO SE NON LOGGATO
if not check_password():
    st.stop()





# ==============================================================================

# 5. FUNZIONI DI UTILITY: GESTIONE CHAT

# ==============================================================================

def ottieni_lista_chat():
    files = glob.glob(os.path.join(CARTELLA_CHAT, f"*{EXT}"))
    # Filtro Anti-Meta
    files = [f for f in files if not f.endswith(f"_meta{EXT}")]
    
    chat_list = []
    for f in files:
        name = os.path.basename(f).replace(EXT, "")
        mtime = os.path.getmtime(f)
        pinned = is_chat_pinned(name) # Usa la funzione creata sopra
        chat_list.append({"name": name, "mtime": mtime, "pinned": pinned})
    
    # ORDINAMENTO: Prima per Pinned (True > False), poi per mtime (Newest > Oldest)
    # Python ordina i booleani come False=0, True=1. Reverse=True mette prima i True.
    chat_list.sort(key=lambda x: (x["pinned"], x["mtime"]), reverse=True)
    
    return [c["name"] for c in chat_list]

def carica_chat(nome_chat):

    filepath = os.path.join(CARTELLA_CHAT, nome_chat + EXT)

    if os.path.exists(filepath):

        try:

            with open(filepath, "r") as f:

                data = json.load(f)

                for msg in data:

                    if "pinned" not in msg:

                        msg["pinned"] = False

                return data

        except:

            return []

    return []



def salva_chat(nome_chat, messages):
    path_chat = os.path.join(CARTELLA_CHAT, nome_chat + EXT)
    with open(path_chat, "w") as f:
        serializable_messages = []
        for m in messages:
            # Salviamo tutto, inclusa la lista dei percorsi delle immagini se c'è
            msg_export = {
                "role": m["role"], 
                "content": str(m["content"]), 
                "pinned": m.get("pinned", False),
                # Se c'è la chiave 'generated_images', la salviamo (sono stringhe di percorsi ora)
                "generated_images": m.get("generated_images", []) 
            }
            serializable_messages.append(msg_export)
        json.dump(serializable_messages, f)



# ==============================================================================

# 6. FUNZIONI DI UTILITY: CALCOLO COSTI E TOKEN

# ==============================================================================



def conta_token(history, model_id):

    try:

        model = genai.GenerativeModel(model_id)

        return model.count_tokens(history).total_tokens

    except:

        return 0
    
def registra_costo(nome_chat, model_id, response_obj=None, manual_in=0, manual_out=0, image_count=0, video_seconds=0):
    """
    Calcola e registra il costo esatto basandosi sulla PRICING_TABLE.
    Accetta o l'oggetto response di Google (per precisione assoluta) o conteggi manuali.
    """
    costo_totale = 0.0
    
    # 1. Recupera Configurazione Prezzi (o Default)
    pricing = PRICING_TABLE.get(model_id, PRICING_TABLE["default"])
    type_calc = pricing.get("type", "text_flat")

    # 2. Determina Token Input/Output (da API o Manuali)
    t_in = manual_in
    t_out = manual_out
    
    if response_obj and hasattr(response_obj, 'usage_metadata'):
        try:
            t_in = response_obj.usage_metadata.prompt_token_count
            t_out = response_obj.usage_metadata.candidates_token_count
        except:
            pass # Usa i manuali se fallisce
            
    # 3. CALCOLO COSTI IN BASE AL TIPO
    
    # --- A. TESTO FLAT (Flash, Lite) ---
    if type_calc == "text_flat":
        c_in = (t_in / 1_000_000) * pricing["input"]
        c_out = (t_out / 1_000_000) * pricing["output"]
        costo_totale = c_in + c_out

    # --- B. TESTO A SCAGLIONI (Pro Models) ---
    elif type_calc == "text_tier":
        limit = pricing["tier_limit"]
        # Prezzo Input dipende se il prompt supera il limite
        p_in = pricing["input_2"] if t_in > limit else pricing["input_1"]
        # Prezzo Output dipende se il prompt (contesto) supera il limite
        p_out = pricing["output_2"] if t_in > limit else pricing["output_1"]
        
        c_in = (t_in / 1_000_000) * p_in
        c_out = (t_out / 1_000_000) * p_out
        costo_totale = c_in + c_out

    # --- C. GENERAZIONE IMMAGINI (Testo In + Img Out) ---
    elif type_calc == "image_gen":
        # Costo del prompt di testo
        c_in = (t_in / 1_000_000) * pricing["input_price_per_1m"]
        # Costo delle immagini generate
        c_out = image_count * pricing["price_per_img"]
        costo_totale = c_in + c_out

    # --- D. VIDEO ---
    elif type_calc == "video":
        costo_totale = video_seconds * pricing["price_per_sec"]

    # 4. SALVATAGGIO
    if costo_totale > 0:
        aggiorna_contatori_costo(nome_chat, costo_totale)
        
    return costo_totale




# ==============================================================================
# 7. FUNZIONI DI UTILITY: PERSISTENZA COSTI E PIN
# ==============================================================================



def get_meta_data(nome_chat):
    """Legge tutto il file meta json"""
    meta_path = os.path.join(CARTELLA_CHAT, f"{nome_chat}_meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_meta_data(nome_chat, data):
    """Salva i dati nel file meta json"""
    meta_path = os.path.join(CARTELLA_CHAT, f"{nome_chat}_meta.json")
    with open(meta_path, "w") as f:
        json.dump(data, f)

def get_costi_chat(nome_chat):
    data = get_meta_data(nome_chat)
    return data.get("costo", 0.0)

def is_chat_pinned(nome_chat):
    data = get_meta_data(nome_chat)
    return data.get("pinned", False)

def toggle_pin_chat(nome_chat):
    data = get_meta_data(nome_chat)
    current_status = data.get("pinned", False)
    data["pinned"] = not current_status
    save_meta_data(nome_chat, data)
    return data["pinned"]

def get_costo_lifetime():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                return json.load(f).get("total_spent", 0.0)
        except:
            return 0.0
    return 0.0

def aggiorna_contatori_costo(nome_chat, costo_transazione):
    if costo_transazione <= 0: return
    
    # Aggiorna Lifetime
    current_life = get_costo_lifetime()
    with open(STATS_FILE, "w") as f:
        json.dump({"total_spent": current_life + costo_transazione}, f)
      
    # Aggiorna Chat specifica (mantenendo il pin se esiste)
    data = get_meta_data(nome_chat)
    data["costo"] = data.get("costo", 0.0) + costo_transazione
    save_meta_data(nome_chat, data)



# ==============================================================================

# 8. FUNZIONI DI UTILITY: GESTIONE CONTESTO E PIN

# ==============================================================================

def get_context_with_pins(messages, memory_limit):

    if not messages: return []

    total_msgs = len(messages)

    indices_to_include = set()

      

    for i, msg in enumerate(messages):

        if msg.get("pinned", False):

            indices_to_include.add(i)

              

    if memory_limit > 0:

        start_index = max(0, total_msgs - memory_limit)

        for i in range(start_index, total_msgs):

            indices_to_include.add(i)

              

    sorted_indices = sorted(list(indices_to_include))

    return [messages[i] for i in sorted_indices]



# ==============================================================================
# 9. INIZIALIZZAZIONE SESSION STATE
# ==============================================================================
if "current_chat_name" not in st.session_state:
    st.session_state.current_chat_name = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "renaming" not in st.session_state:
    st.session_state.renaming = False
# QUIZ
if "quiz_mode_toggle" not in st.session_state: st.session_state.quiz_mode_toggle = False
if "scroll_target" not in st.session_state: st.session_state.scroll_target = None

# NUOVO: STATO GENERAZIONE IMMAGINI
if "img_gen_mode" not in st.session_state: st.session_state.img_gen_mode = False
# Contatore per resettare il microfono ed evitare loop
if "audio_key_counter" not in st.session_state:
    st.session_state.audio_key_counter = 0
# ... (nella sezione 9)
if "img_gen_mode" not in st.session_state: st.session_state.img_gen_mode = False
if "video_gen_mode" not in st.session_state: st.session_state.video_gen_mode = False # <--- NUOVO
# ==============================================================================
# 10. SIDEBAR: ORGANIZZAZIONE IN QUADRANTI
# ==============================================================================
with st.sidebar:
    
  # --- QUADRANTE 1: API KEY ---
    with st.container(border=True):
        st.caption("🔑 CREDENZIALI")
        # Se la chiave è già caricata dai Secrets, mostriamo solo un semaforo verde
        if st.secrets.get("general", {}).get("api_key"):
            st.success("✅ Chiave API Attiva")
        # Altrimenti mostriamo la barra per inserirla a mano
        else:
            api_key = st.text_input("API Key", type="password", placeholder="sk-...", label_visibility="collapsed")
            if api_key:
                st.session_state.api_key = api_key

    # --- QUADRANTE 2: NAVIGAZIONE CHAT ---
    with st.container(border=True):
        st.caption("🗂️ NAVIGAZIONE")
        with st.expander("➕ Nuova Chat", expanded=False):
            nuovo_nome = st.text_input("Titolo:", placeholder="Nuovo...")
            if st.button("Crea Chat", use_container_width=True):
                if nuovo_nome:
                    nome_pulito = "".join(c for c in nuovo_nome if c.isalnum() or c in (' ', '_', '-')).strip()
                    st.session_state.current_chat_name = nome_pulito
                    st.session_state.messages = []
                    st.session_state.renaming = False
                    salva_chat(nome_pulito, [])
                    st.rerun()
# ... (dentro Quadrante 2) ...
        lista_chat = ottieni_lista_chat()
        if lista_chat:
            idx = 0
            if st.session_state.current_chat_name in lista_chat:
                idx = lista_chat.index(st.session_state.current_chat_name)
            
            # --- FUNZIONE DI FORMATTAZIONE PER LA LISTA ---
            def format_chat_name(name):
                if is_chat_pinned(name):
                    return f"📌 {name}"
                return name
            # ----------------------------------------------

            chat_sel = st.radio(
                "Lista", 
                lista_chat, 
                index=idx, 
                label_visibility="collapsed", 
                key="nav_chat",
                format_func=format_chat_name  # <--- AGGIUNTA QUI
            )
            
            if chat_sel != st.session_state.current_chat_name:
                st.session_state.current_chat_name = chat_sel
                st.session_state.messages = carica_chat(chat_sel)
                st.session_state.renaming = False
                st.rerun()
        else:
            st.caption("Nessuna chat salvata.")

    # --- QUADRANTE 3: GESTIONE CHAT ATTIVA ---
    with st.container(border=True):
        st.caption("⚙️ CONTROLLO CHAT")
        
        # --- MODIFICA: PULSANTE MODALITÀ IMMAGINE ---
        col_mod1, col_mod2 = st.columns([0.80, 0.20])
        
        with col_mod1:
            keys_modelli = list(CONFIG_MODELLI.keys())
            d_idx = st.session_state.get("selected_model_index", 1)
            nome_modello_scelto = st.selectbox("Modello", keys_modelli, index=d_idx, label_visibility="collapsed")
            st.session_state.selected_model_index = keys_modelli.index(nome_modello_scelto)

        with col_mod2:
            # Tasto Toggle Immagini (Verde se attivo)
            btn_type = "primary" if st.session_state.img_gen_mode else "secondary"
            if st.button("🎨", type=btn_type, help="Modalità Generazione Immagini", use_container_width=True):
                st.session_state.img_gen_mode = not st.session_state.img_gen_mode
                st.rerun()

        # LOGICA SOVRASCRITTURA MODELLO SE MODALITÀ ATTIVA
        if st.session_state.img_gen_mode:
            st.info("🎨 Modalità Immagine: Attiva")
            # Forza il modello "Banana" dalla tua lista
            dati_modello = {"id": "gemini-2.5-flash-image", "limit": 2_000_000, "tier": "flash"}
        else:
            dati_modello = CONFIG_MODELLI[nome_modello_scelto]

        model_id, token_limit = dati_modello['id'], dati_modello['limit']
        st.session_state.active_model_id = model_id

        memory_limit = st.number_input("⚡ Context Window (Msg)", min_value=0, max_value=1000000, value=5)
        st.markdown("---")
        st.session_state.quiz_mode_toggle = st.toggle("🎯 Modalità Quiz", value=st.session_state.quiz_mode_toggle)

        # ... (dentro Quadrante 3) ...
        if st.session_state.current_chat_name:
            st.markdown(f"**{st.session_state.current_chat_name}**")
            
            # CREIAMO 3 COLONNE: Rinomina | Pin | Cancella
            c_ren, c_pin, c_del = st.columns([1, 1, 1]) 
            
            with c_ren:
                if st.button("✏️", use_container_width=True, help="Rinomina"): 
                    st.session_state.renaming = not st.session_state.renaming
            
            with c_pin:
                # Determina lo stato attuale per cambiare icona/stile
                is_pinned_now = is_chat_pinned(st.session_state.current_chat_name)
                btn_pin_icon = "📌" if is_pinned_now else "📍"
                # Usiamo type="primary" se è pinnato per evidenziarlo
                btn_pin_type = "primary" if is_pinned_now else "secondary"
                
                if st.button(btn_pin_icon, type=btn_pin_type, use_container_width=True, help="Fissa in alto"):
                    toggle_pin_chat(st.session_state.current_chat_name)
                    st.rerun()

            with c_del:
                if st.button("🗑️", use_container_width=True, help="Elimina"):
                    try:
                        os.remove(os.path.join(CARTELLA_CHAT, st.session_state.current_chat_name + EXT))
                        meta = os.path.join(CARTELLA_CHAT, f"{st.session_state.current_chat_name}_meta.json")
                        if os.path.exists(meta): os.remove(meta)
                    except: pass
                    st.session_state.current_chat_name = None
                    st.session_state.messages = []
                    st.session_state.renaming = False
                    st.rerun()
            if st.session_state.renaming:
                new_title_input = st.text_input("Nuovo nome:", value=st.session_state.current_chat_name)
                if st.button("💾 Salva", use_container_width=True):
                    if new_title_input and new_title_input != st.session_state.current_chat_name:
                        n_clean = "".join(c for c in new_title_input if c.isalnum() or c in (' ', '_', '-')).strip()
                        
                        if n_clean:
                            rename_success = False # Flag di controllo
                            try:
                                old = os.path.join(CARTELLA_CHAT, st.session_state.current_chat_name + EXT)
                                new = os.path.join(CARTELLA_CHAT, n_clean + EXT)
                                
                                # Rinomina file principale
                                os.rename(old, new)
                                
                                # Rinomina meta file se esiste
                                old_meta = os.path.join(CARTELLA_CHAT, f"{st.session_state.current_chat_name}_meta.json")
                                new_meta = os.path.join(CARTELLA_CHAT, f"{n_clean}_meta.json")
                                if os.path.exists(old_meta):
                                    os.rename(old_meta, new_meta)
            
                                # Aggiorna variabili di stato
                                st.session_state.current_chat_name = n_clean
                                st.session_state.renaming = False
                                rename_success = True # Segnala che è andato tutto bene
                                
                            except Exception as e: # Cattura l'errore specifico per stamparlo
                                st.error(f"Errore rinomina: {e}")
                            
                            # Rerun FUORI dal try/except
                            if rename_success:
                                st.rerun()
    # --- QUADRANTE 3.5: ALLEGATI (Nuova Posizione) ---
    with st.container(border=True):
        st.caption("📎 ALLEGATI")
        # File Uploader spostato qui
        uploaded_files = st.file_uploader(
            "Trascina file qui",
            accept_multiple_files=True, 
            type=["png", "jpg", "jpeg", "txt", "py", "md", "csv", "pdf", "docx"], 
            label_visibility="collapsed",
            key="chat_uploader_sidebar" 
        )
        
        if uploaded_files:
            st.info(f"{len(uploaded_files)} file pronti per l'invio")

   # --- QUADRANTE 4: METRICHE ---
    with st.container(border=True):
        st.caption("💰 ECONOMIA")
        # Creiamo i "buchi" vuoti dove la Sezione 13 andrà a scrivere dopo
        ph_lifetime = st.empty()
        ph_chat_cost = st.empty()
        ph_next_est = st.empty()

# ==============================================================================

# 11. MAIN LOGIC: CONTROLLI PRELIMINARI E TITOLO

# ==============================================================================
# ==============================================================================
# 11. MAIN LOGIC: CONTROLLI PRELIMINARI E TITOLO
# ==============================================================================

# 1. Recupera la chiave in modo sicuro (senza errori se la variabile manca)
chiave_da_usare = st.session_state.get("api_key")

# Se non c'è nella sessione, controlliamo se per caso è appena stata digitata nella sidebar
# (Usiamo 'locals' per evitare errori se la variabile api_key non esiste)
if not chiave_da_usare and "api_key" in locals() and api_key:
    chiave_da_usare = api_key
    st.session_state.api_key = api_key # La salviamo per dopo

# 2. Controllo Finale: Abbiamo sta chiave o no?
if not chiave_da_usare:
    st.warning("👈 Inserisci l'API Key nel primo quadrante per iniziare.")
    st.stop()

# 3. Controllo Chat
if not st.session_state.current_chat_name:
    st.info("👈 Crea una chat nel secondo quadrante.")
    st.stop()

# 4. Configurazione
genai.configure(api_key=chiave_da_usare)

# 5. Titolo
st.title(f"{st.session_state.current_chat_name}")

# ==============================================================================
# 12. COMPONENTI UI: INPUT E ALLEGATI + RENDER MESSAGGI
# ==============================================================================

# ==============================================================================
# 12. COMPONENTI UI: INPUT E ALLEGATI + RENDER MESSAGGI
# ==============================================================================


# Lista per tracciare i pin
pinned_indices = []

# --- DEFINIZIONE AVATAR ---
ICON_USER = None
IMG_TRASPARENTE = "https://upload.wikimedia.org/wikipedia/commons/c/ca/1x1.png"

# ==============================================================================
# RENDER CICLO MESSAGGI (FIX VISUALIZZAZIONE IMMAGINI)
# ==============================================================================
for i, message in enumerate(st.session_state.messages):
    role = message["role"]
    
    avatar_to_use = ICON_USER if role == "user" else IMG_TRASPARENTE
    
    with st.chat_message(role, avatar=avatar_to_use):
        st.markdown(f'<div data-role="{role}" style="display:none;"></div>', unsafe_allow_html=True)
        
        c_msg, c_copy, c_pin = st.columns([0.88, 0.06, 0.06], gap="small")
        
        with c_msg:
            st.markdown(f'<div id="msg_{i}" style="position:absolute; top:-10px; height:0; width:0; margin:0; padding:0; overflow:hidden;"></div>', unsafe_allow_html=True)
            
            # 1. MOSTRA IL TESTO
            content_text = str(message["content"])
            # Controllo più generico: se c'è un div o small, abilita HTML
            if "<div" in content_text or "<small>" in content_text: 
                 st.markdown(content_text, unsafe_allow_html=True)
            else:
                 st.markdown(content_text)
            
            # --- FIX: MOSTRA LE IMMAGINI GENERATE ---
            # Questo blocco controlla se nel messaggio ci sono percorsi di immagini salvate
            if "generated_images" in message and message["generated_images"]:
                for img_path in message["generated_images"]:
                    if os.path.exists(img_path):
                        st.image(img_path, width=400) # Mostra l'immagine
                    else:
                        st.error(f"Immagine non trovata: {img_path}")
            # ----------------------------------------

            if st.session_state.get(f"show_copy_{i}", False):
                st.caption("📋 Copia da qui:")
                st.code(content_text, language=None)

        with c_copy:
            if st.button("📑", key=f"copy_btn_{i}"):
                st.session_state[f"show_copy_{i}"] = not st.session_state.get(f"show_copy_{i}", False)
                st.rerun()

        with c_pin:
            is_pinned = message.get("pinned", False)
            if is_pinned: pinned_indices.append(i)
            icon_pin = "📌" if is_pinned else "📍"
            if st.button(icon_pin, key=f"pin_btn_{i}"):
                st.session_state.messages[i]["pinned"] = not is_pinned
                salva_chat(st.session_state.current_chat_name, st.session_state.messages)
                st.rerun()

st.markdown('<div id="end_chat"></div>', unsafe_allow_html=True)



# ==============================================================================
# 13. ANALISI TOKEN E DASHBOARD (Riempie il Quadrante 4)
# ==============================================================================

# 1. CONTA I TOKEN ATTUALI
# (Lo facciamo qui perché la chat è stata caricata/aggiornata sopra)
msgs_source_for_count = get_context_with_pins(st.session_state.messages, memory_limit)
history_for_google = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [str(m["content"])]} for m in msgs_source_for_count]
tot_tokens = conta_token(history_for_google, model_id)

# 2. CALCOLA LE STIME PER IL FUTURO
pricing_current = PRICING_TABLE.get(model_id, PRICING_TABLE["default"])

# Helper per prezzo input
def get_current_input_price(p_table, n_tokens):
    ptype = p_table.get("type", "text_flat")
    if ptype == "text_tier":
        return p_table["input_2"] if n_tokens > p_table["tier_limit"] else p_table["input_1"]
    elif ptype == "image_gen":
        return p_table["input_price_per_1m"]
    else:
        return p_table.get("input", 0.10)

# Stima costo prossimo invio
price_per_m = get_current_input_price(pricing_current, tot_tokens)
costo_next_input = (tot_tokens / 1_000_000) * price_per_m

# 3. RECUPERA I COSTI PASSATI (Dal file JSON)
costo_vita = get_costo_lifetime()
costo_chat_tot = get_costi_chat(st.session_state.current_chat_name)

# 4. RIEMPI I SEGNAPOSTO NEL SIDEBAR (Quadrante 4)
# Ora usiamo le variabili ph_... create prima

with ph_lifetime.container():
    st.metric("💸 Spesa Totale", f"${costo_vita:.4f}", help="Totale storico speso")

with ph_chat_cost.container():
    c1, c2 = st.columns(2)
    with c1:
        st.metric("💬 Chat Attuale", f"${costo_chat_tot:.4f}")
    with c2:
        st.metric("🔮 Prox Invio", f"${costo_next_input:.5f}", help="Stima costo solo input se invii ora")

with ph_next_est.container():
    # Barra Memoria
    perc_mem = min(tot_tokens / token_limit, 1.0) if token_limit > 0 else 0
    st.progress(perc_mem, text=f"🧠 Memoria: {tot_tokens/1000:.1f}k / {token_limit/1000:.0f}k")
    if perc_mem > 0.9: st.error("⚠️ Memoria critica!")
# ==============================================================================
# 14. LOGICA DI INPUT E ROUTING (LITE OPTIMIZED PER TUTTO)
# ==============================================================================

# Definisci label input
label_input = f"Scrivi a {model_id}..."
if st.session_state.img_gen_mode:
    label_input = "🎨 Descrivi l'immagine da generare..."

# --- 1. SETUP INPUT E VARIABILI ---
if "audio_key_counter" not in st.session_state:
    st.session_state.audio_key_counter = 0

audio_input_val = None
prompt = None
was_audio = False 

# A. Widget Audio Fluttuante
with st.container():
    st.markdown('<div class="floating-audio-container">', unsafe_allow_html=True)
    audio_key = f"mic_{st.session_state.audio_key_counter}" 
    audio_input_val = st.audio_input("Voce", label_visibility="collapsed", key=audio_key)
    st.markdown('</div>', unsafe_allow_html=True)

# B. Widget Testo Standard
text_input_val = st.chat_input(label_input)

# --- 2. ELABORAZIONE INPUT (TRASCRIZIONE IMMEDIATA) ---
if audio_input_val:
    with st.status("🎧 Ascolto e Trascrizione (Gemini Flash)...", expanded=False) as status:
        try:
            transcriber = genai.GenerativeModel("gemini-2.5-flash")
            audio_bytes = audio_input_val.getvalue()
            # Prompt specifico per ottenere solo il testo parlato
            response_transcription = transcriber.generate_content([
                "Trascrivi esattamente le parole dette in questo audio in italiano. Non aggiungere commenti.",
                {"mime_type": "audio/wav", "data": audio_bytes}
            ])
            prompt = response_transcription.text
            was_audio = True
            status.update(label="✅ Trascrizione completata!", state="complete", expanded=False)
        except Exception as e:
            st.error(f"Errore trascrizione audio: {e}")
            prompt = None

elif text_input_val:
    prompt = text_input_val
    was_audio = False

# --- 3. ESECUZIONE ---
if prompt:

   # --- A. PREPARAZIONE DATI COMUNI (FILE & ALLEGATI) ---
    import hashlib # Necessario per calcolare l'impronta digitale dei dati

    # 1. Inizializzazione Cache (Se non esiste)
    if "file_cache" not in st.session_state: 
        st.session_state.file_cache = {} # Dizionario {nome_file: testo_estratto}
    if "last_summary_hash" not in st.session_state: 
        st.session_state.last_summary_hash = "" # Hash dell'ultimo riassunto fatto
    if "cached_summary_text" not in st.session_state:
        st.session_state.cached_summary_text = "" # Il testo del riassunto salvato

    api_content_parts = []         
    images_list = []               
    text_content_accumulated = ""  
    file_names = []                
    has_files = False
    
    # Variabile per contenere il riassunto dei file
    file_summary_text = "" 

    # Elaborazione File Caricati
    if uploaded_files: 
        has_files = True
        
        # Iteriamo sui file caricati
        for uploaded_file in uploaded_files:
            file_names.append(uploaded_file.name)
            file_type = uploaded_file.type
            file_name_lower = uploaded_file.name.lower()
            
            # Creiamo una chiave unica per il file (Nome + Dimensione)
            file_unique_key = f"{uploaded_file.name}_{uploaded_file.size}"

            # --- GESTIONE IMMAGINI (Sempre caricate in RAM per l'invio) ---
            if "image" in file_type:
                try: images_list.append(Image.open(uploaded_file))
                except: pass
            
            # --- GESTIONE TESTO (CON CACHE) ---
            else:
                # Se il file è già in cache, lo recuperiamo GRATIS
                if file_unique_key in st.session_state.file_cache:
                    text_content_accumulated += st.session_state.file_cache[file_unique_key]
                
                # Se è nuovo, lo leggiamo e lo salviamo in cache
                else:
                    extracted_text = ""
                    if file_type == "application/pdf" or file_name_lower.endswith(".pdf"):
                        try:
                            pdf_reader = PdfReader(uploaded_file)
                            for page in pdf_reader.pages: extracted_text += page.extract_text() + "\n"
                        except: pass
                    elif "word" in file_type or file_name_lower.endswith(".docx"):
                        try:
                            doc = Document(uploaded_file)
                            extracted_text += "\n".join([p.text for p in doc.paragraphs])
                        except: pass
                    else:
                        try: extracted_text += uploaded_file.getvalue().decode("utf-8")
                        except: pass
                    
                    # Salviamo in cache per il futuro
                    st.session_state.file_cache[file_unique_key] = extracted_text
                    text_content_accumulated += extracted_text
        
        # --- COMPRESSIONE INTELLIGENTE (EVITA CHIAMATE API INUTILI) ---
        if text_content_accumulated:
            # Calcoliamo l'hash MD5 di tutto il testo accumulato
            current_content_hash = hashlib.md5(text_content_accumulated.encode("utf-8")).hexdigest()
            
            # Se l'hash è uguale all'ultima volta, USIAMO LA COPIA CACHATA (Costo: 0 Token)
            if current_content_hash == st.session_state.last_summary_hash:
                file_summary_text = st.session_state.cached_summary_text
                # Opzionale: decommenta per debug
                # st.toast("♻️ Riassunto caricato dalla cache (0 token)", icon="💾")
            
            # Se l'hash è diverso (nuovi file o modifiche), CHIAMIAMO L'AI
            else:
                try:
                    with st.spinner("📑 Analisi nuovi documenti in corso (Flash-Lite)..."):
                        lite_model = genai.GenerativeModel(ID_MODELLO_LITE)
                        # Prompt ottimizzato per estrazione dati
                        file_summary_resp = lite_model.generate_content(
                            f"Estrai tutti i dati tecnici, le date e i punti chiave dal seguente testo per un utilizzo futuro. Sii estremamente dettagliato:\n{text_content_accumulated[:30000]}"
                        )
                        file_summary_text = file_summary_resp.text
                        
                        # --- [NUOVO] REGISTRAZIONE COSTO FILE ---
                        registra_costo(st.session_state.current_chat_name, ID_MODELLO_LITE, response_obj=file_summary_resp)
                        # ----------------------------------------
                        
                        # Aggiorniamo la cache
                        st.session_state.last_summary_hash = current_content_hash
                        st.session_state.cached_summary_text = file_summary_text
                except Exception as e:
                    file_summary_text = "Impossibile riassumere i file."
                    st.error(f"Errore riassunto file: {e}")

    # Reset cache se non ci sono file (per evitare che rimanga memoria vecchia)
    else:
        st.session_state.last_summary_hash = ""
        st.session_state.cached_summary_text = ""
        # Non puliamo file_cache per permettere ricaricamenti veloci se l'utente rimette lo stesso file

    msg_context_text = f"<system_context>RIASSUNTO FILE:\n{file_summary_text}</system_context>" if file_summary_text else ""
    # --- B. ROUTING FUNZIONI ---

# ==========================================
    # 1. QUIZ MODE (LITE OPTIMIZED: CHAT-STYLE LOGIC)
    # ==========================================
    if st.session_state.quiz_mode_toggle:
        
        # 1. Recupero contesto esattamente come la Chat
        msgs_raw = get_context_with_pins(st.session_state.messages, memory_limit)
        history_text_block = "\n".join([f"{m['role'].upper()}: {str(m['content'])}" for m in msgs_raw])
        
        final_quiz_context = ""

        # 2. Compressione "Stile Chat"
        # Usiamo file_summary_text che è già stato calcolato ed è sicuro (non il raw file)
        with st.status("📚 Ottimizzazione contesto per il Quiz...", expanded=False):
            try:
                # Prompt ricalcato sulla compressione chat, ma orientato all'estrazione dati
                prompt_compressione = f"""
                SEI UN MOTORE DI ESTRAZIONE DATI (RAG). NON SEI UNA CHATBOT.
                
                IL TUO UNICO OBIETTIVO:
                Analizza il testo fornito qui sotto e restituisci SOLO un elenco strutturato di fatti, numeri, definizioni e concetti chiave.
                
                REGOLE FERREE:
                1. NON conversare con l'utente.
                2. NON scrivere frasi come "Ecco il riassunto" o "In base alla tua richiesta".
                3. Se non ci sono dati sufficienti (chat vuota e nessun file), rispondi SOLO: "NESSUNA CONOSCENZA DISPONIBILE".
                4. se ti viene chiesto di riassumere la chat, e la chat ha pochi elementi, fai semplicemente un riassunto puntato di quegli elementi e non scrivere altro.

                --- INIZIO DATI DA ESTRARRE ---
                
                [CRONOLOGIA CHAT]
                {history_text_block}
                
                [CONTENUTO FILE]
                {file_summary_text}
                
                --- FINE DATI ---
                """
                lite_compressor = genai.GenerativeModel(ID_MODELLO_LITE)
                
                # Questa chiamata è sicura perché file_summary_text è già ridotto
                summary_resp = lite_compressor.generate_content(prompt_compressione)
                # --- [NUOVO] REGISTRAZIONE COSTO QUIZ ---
                registra_costo(st.session_state.current_chat_name, ID_MODELLO_LITE, response_obj=summary_resp)
                # ----------------------------------------
                final_quiz_context =  summary_resp.text
               

            except Exception as e:
                # Fallback: se fallisce la compressione, usiamo i dati grezzi ma tagliati
                final_quiz_context = f"DATI GREZZI (FALLBACK):\n{history_text_block[-5000:]}\n{file_summary_text}"
        
        # 3. Invio alla pagina Quiz
        final_source_for_quiz = f"il TEMA del quiz: {prompt} \n i seguenti contenuti, potrebbero aiutarti a costruire il quiz. utilizza solo i contenuti rilevanti al tema descritto e, qualora nulla fosse rilevante, NON UTILIZZARLI e crea il quiz tramite le tue conoscienze: {final_quiz_context}"
        
        st.session_state.quiz_source_text = final_source_for_quiz
        st.session_state.quiz_images_list = images_list
        st.session_state.refresh_quiz = True 
        st.session_state.quiz_mode_toggle = False
        st.switch_page("pages/quiz_mode.py")

    # ==========================================
    # 2. CHAT / IMAGE GEN (VERSIONE GOLD: FIX 1 + 2 + 5 UNIFICATI)
    # ==========================================
    # ==========================================
    # 2. CHAT / IMAGE GEN (VERSIONE IBRIDA: OLD STYLE SAVING + NEW SAFETY)
    # ==========================================
    else:
        display_text = f"🎤 {prompt}" if was_audio else prompt

        # --- REVERT AL TUO METODO ORIGINALE ---
        # Salviamo il riassunto del file DIRETTAMENTE nel messaggio (div nascosto).
        # Questo mantiene il file "inciso" nella storia del messaggio.
        full_mem = f"{display_text}\n\n<div style='display:none'>{file_summary_text}</div>"
        
        # Aggiunta tag immagini se presenti
        if images_list and not text_content_accumulated: 
            full_mem += f"\n<small>(📸 {len(images_list)} img)</small>"
        
        # SALVATAGGIO IN SESSION STATE (Versione Pesante come richiesto)
        st.session_state.messages.append({"role": "user", "content": full_mem, "pinned": False})
        
        # Visualizzazione a schermo (Pulita)
        with st.chat_message("user", avatar=ICON_USER):
            st.markdown('<div data-role="user" style="display:none;"></div>', unsafe_allow_html=True)
            st.markdown(display_text + (f" <small>({len(file_names)} file)</small>" if has_files else ""), unsafe_allow_html=True)
            if was_audio: st.audio(audio_input_val)
        
        salva_chat(st.session_state.current_chat_name, st.session_state.messages)
        
        stop_placeholder = st.empty()
        if stop_placeholder.button("🛑 STOP GENERAZIONE", type="primary", use_container_width=True, key="stop_gen_main"):
            stop_placeholder.empty()
            st.stop()

        # --- GENERAZIONE AI ---
        try:
            
            # --- RAMO A: GENERAZIONE IMMAGINI ---
            if st.session_state.img_gen_mode:
                model = genai.GenerativeModel(model_id) 
                
                with st.chat_message("assistant", avatar=IMG_TRASPARENTE):
                    st.markdown('<div data-role="assistant" style="display:none;"></div>', unsafe_allow_html=True)
                    status_container = st.status("🎨 Analisi contesto e generazione artwork...", expanded=True)
                    
                    try:
                        # COMPRESSIONE PER IMMAGINI
                        with status_container:
                            st.write("Configurazione scena...")
                            try:
                                msgs_raw = get_context_with_pins(st.session_state.messages[:-1], memory_limit)
                                history_text = "\n".join([f"{m['role'].upper()}: {str(m['content'])}" for m in msgs_raw])
                                
                                lite = genai.GenerativeModel(ID_MODELLO_LITE)
                                prompt_per_lite = f"""
                                Analizza questi dati per creare un prompt visivo artistico.
                                DOCUMENTI: {file_summary_text}
                                STORIA: {history_text[-4000:]}
                                RICHIESTA: {prompt}
                                Restituisci SOLO il prompt in inglese.
                                """
                                clean_resp = lite.generate_content(prompt_per_lite)
                                # --- [NUOVO] COSTO PROMPT IMMAGINE ---
                                registra_costo(st.session_state.current_chat_name, ID_MODELLO_LITE, response_obj=clean_resp)
                                # -------------------------------------
                                final_img_prompt = clean_resp.text
                            except:
                                final_img_prompt = prompt
                        
                        # GENERAZIONE
                        status_container.write("Generazione in corso...")
                        response = model.generate_content(final_img_prompt)

                        # --- [NUOVO] COSTO GENERAZIONE IMMAGINE ---
                        # Calcoliamo quante immagini sono state generate (di solito 1)
                        num_img_gen = 0
                        if hasattr(response, 'parts'): num_img_gen = 1 
                        # Nota: passiamo image_count perché i metadati per le immagini sono spesso vuoti
                        registra_costo(st.session_state.current_chat_name, model_id, response_obj=response, image_count=num_img_gen)
                        # ------------------------------------------
                        
                        # ... Gestione Output Immagine ...
                        full_resp = ""
                        saved_image_paths = [] 
                        descrizione_visiva_nascosta = ""
                        img_save_dir = os.path.join(CARTELLA_CHAT, "generated_images")
                        if not os.path.exists(img_save_dir): os.makedirs(img_save_dir)

                        if hasattr(response, 'parts'):
                            for part in response.parts:
                                if part.text:
                                    st.markdown(part.text)
                                    full_resp += part.text + "\n"
                                if part.inline_data:
                                    img_filename = f"{uuid.uuid4()}.png"
                                    img_path = os.path.join(img_save_dir, img_filename)
                                    with open(img_path, "wb") as f: f.write(part.inline_data.data)
                                    st.image(img_path, caption="Generata con Gemini")
                                    full_resp += "\n[🖼️ IMMAGINE GENERATA]"
                                    saved_image_paths.append(img_path)
                                    try:
                                        analyzer = genai.GenerativeModel("gemini-2.0-flash")
                                        img_obj = Image.open(img_path)
                                        anl = analyzer.generate_content(["Descrivi brevemente:", img_obj])
                                        descrizione_visiva_nascosta += f"\n[IMG_ANALYSIS]: {anl.text}\n"
                                    except: pass

                        status_container.update(label="Fatto!", state="complete")
                        memory_block = f"{full_resp}<div style='display:none'>PROMPT: {final_img_prompt}\n{descrizione_visiva_nascosta}</div>"
                        st.session_state.messages.append({"role": "assistant", "content": memory_block, "generated_images": saved_image_paths, "pinned": False})

                    except Exception as e:
                        status_container.update(label="Errore", state="error")
                        st.error(f"Errore Img: {e}")

            # --- RAMO B: CHAT STANDARD (CON FRENO DI EMERGENZA MA STORIA COMPLETA) ---
            else:
                model = genai.GenerativeModel(model_id)
                # Recuperiamo la storia (Che ora contiene i DIV nascosti come volevi)
                msgs_raw = get_context_with_pins(st.session_state.messages[:-1], memory_limit)
                
                final_history = []
                final_prompt_to_send = ""

                # Decidiamo se comprimere (Utile perché ora la storia pesa di più!)
                should_compress = len(msgs_raw) > 4 or has_files or (model_id in IDS_PESANTI)

                if should_compress:
                    # MANTENIAMO IL FRENO DI EMERGENZA (Fondamentale se la storia è pesante)
                    with st.status("⚡ Compressione Contesto (Flash-Lite)...", expanded=False) as status:
                        try:
                            history_text_block = "\n".join([f"{m['role'].upper()}: {str(m['content'])}" for m in msgs_raw])
                            
                            prompt_compressione = f"""
                            Sei un assistente efficiente.
                            Usa i dati seguenti per rispondere alla richiesta utente: "{prompt}"
                            
                            STORIA CHAT (Include dati precedenti):
                            {history_text_block}
                            
                            DATI FILE ATTUALI:
                            {file_summary_text}
                            """

                            lite_compressor = genai.GenerativeModel(ID_MODELLO_LITE)
                            summary_resp = lite_compressor.generate_content(prompt_compressione)

                            # --- [NUOVO] COSTO COMPRESSIONE STORIA ---
                            registra_costo(st.session_state.current_chat_name, ID_MODELLO_LITE, response_obj=summary_resp)
                            # -----------------------------------------
                            
                            final_prompt_to_send = f"[CONTESTO OTTIMIZZATO]\n{summary_resp.text}\n[FINE CONTESTO]\n\n[RICHIESTA]:\n{prompt}"
                            status.update(label="✅ Compressione riuscita!", state="complete")
                        
                        except Exception as e:
                            # FRENO DI EMERGENZA ATTIVO
                            status.update(label="⚠️ Errore Compressione - Freno Attivo", state="error")
                            st.warning(f"Ottimizzazione fallita. File ignorati per sicurezza.")
                            
                            msgs_emergency = msgs_raw[-5:] 
                            final_history = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [str(m["content"])]} for m in msgs_emergency]
                            final_prompt_to_send = f"[SYSTEM: File non disponibili per errore tecnico]\nDOMANDA: {prompt}"
                
                else:
                    # Chat breve
                    final_history = [{"role": ("user" if m["role"]=="user" else "model"), "parts": [str(m["content"])]} for m in msgs_raw]
                    # Qui non serve incollare file_summary_text in final_prompt_to_send se è già in full_mem
                    # Ma per sicurezza lo lasciamo nel caso sia il primo messaggio
                    final_prompt_to_send = prompt

                # --- INVIO ---
                chat = model.start_chat(history=final_history)
                payload_api = []
                if images_list: payload_api.extend(images_list)
                payload_api.append(final_prompt_to_send)
                
                response_stream = chat.send_message(payload_api, stream=True)

                with st.chat_message("assistant", avatar=IMG_TRASPARENTE):
                    st.markdown('<div data-role="assistant" style="display:none;"></div>', unsafe_allow_html=True)
                    ph = st.empty()
                    full_resp = ""
                    for chunk in response_stream:
                        if chunk.text:
                            full_resp += chunk.text
                            ph.markdown(full_resp + "▌")
                    ph.markdown(full_resp)

                st.session_state.messages.append({"role": "assistant", "content": full_resp, "pinned": False})
                try:
                    # 1. Contiamo l'input (Storia inviata + File/Prompt)
                    t_input = model.count_tokens(final_history).total_tokens
                    # 2. Contiamo l'output (La risposta completa dell'AI)
                    t_output = model.count_tokens(full_resp).total_tokens
                    
                    # Registriamo usando i valori manuali
                    registra_costo(
                        st.session_state.current_chat_name, 
                        model_id, 
                        manual_in=t_input, 
                        manual_out=t_output
                    )
                except Exception as e_cost:
                    print(f"Errore calcolo costo chat: {e_cost}")
            
            # --- CHIUSURA COMUNE ---
            salva_chat(st.session_state.current_chat_name, st.session_state.messages)
            
        except Exception as e:
            stop_placeholder.empty()
            st.error(f"Errore generazione: {e}")
# ==============================================================================
# 17. NAVIGAZIONE PIN (SOLUZIONE ANCHOR LINK - NO RELOAD)
# ==============================================================================

with st.sidebar:
    st.divider()
    st.markdown("### 🧭 Bookmark")

    if 'pinned_indices' in locals() and pinned_indices:
        for idx in pinned_indices:
            # 1. Preparazione anteprima testo
            raw_text = str(st.session_state.messages[idx]['content'])
            if "<div" in raw_text: raw_text = "📄 [Dati Sistema]"
            
            # Pulizia testo per l'anteprima
            clean_text = raw_text.replace('\n', ' ').replace('#', '').strip()
            preview = (clean_text[:25] + "...") if len(clean_text) > 25 else clean_text
            
            # 2. CREAZIONE LINK HTML (Nessun Rerun Python!)
            # Punta all'ID "msg_{idx}" che hai già creato nel ciclo dei messaggi
            st.markdown(
                f"""
                <a href="#msg_{idx}" class="nav-btn">
                    📌 {idx+1}. {preview}
                </a>
                """, 
                unsafe_allow_html=True
            )
    else:
        st.caption("Nessun pin attivo.")

    st.write("") # Spaziatore
            
    # BOTTONE FONDO (Anchor Link anche qui)
    st.markdown(
        """
        <a href="#end_chat" class="nav-btn">
            ⬇️ Vai in fondo
        </a>
        """, 
        unsafe_allow_html=True
    )

