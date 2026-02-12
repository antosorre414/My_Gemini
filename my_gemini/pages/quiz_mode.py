import time
import streamlit as st
import google.generativeai as genai
import json
import streamlit.components.v1 as components 
from google.api_core.exceptions import ResourceExhausted

# CONFIGURAZIONE PAGINA
st.set_page_config(page_title="Gemini Quiz Arena", page_icon="🎲", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# CSS: STILE COMPATTO & CYBERPUNK
# ==============================================================================
st.markdown("""
<style>
    .stApp { background-color: #0b141a; color: #e9edef; }
    
    /* 1. RIDUZIONE DIMENSIONI GENERALI */
    h1 { font-size: 1.8rem !important; color: #00a884 !important; margin-bottom: 0px !important; }
    h3 { font-size: 1.2rem !important; font-weight: normal !important; margin-top: 10px !important; }
    p, div { font-size: 0.95rem !important; }
    
    /* Stile Bottoni più piccoli e compatti */
    div[data-testid="stVerticalBlock"] button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        border: 1px solid #7e22ce !important;
        background-color: #1e2126 !important;
        color: #e9edef !important;
        transition: all 0.2s !important;
        min-height: 45px !important; /* Meno alti */
        padding: 5px 10px !important;
        font-size: 0.9rem !important;
    }
    
    div[data-testid="stVerticalBlock"] button:hover {
        border-color: #ff0055 !important;
        background-color: #262730 !important;
        transform: scale(1.01);
    }

    /* RISPOSTA GIUSTA (Verde) */
    button[kind="primary"] {
        background-color: rgba(0, 255, 0, 0.15) !important;
        border: 2px solid #00FF00 !important;
        color: #00FF00 !important;
    }
    
    /* BOX SPIEGAZIONE COMPATTO */
    .explanation-box {
        background-color: #111b21;
        border-left: 4px solid #00a884;
        padding: 10px 15px;
        border-radius: 6px;
        margin-top: 15px;
        font-size: 0.9rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }
    
    .exp-title {
        color: #00a884;
        font-weight: bold;
        text-transform: uppercase;
        font-size: 0.8rem;
        margin-bottom: 3px;
    }
    
    /* Nasconde padding extra di Streamlit */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎲 Quiz Arena")

# --- CONTROLLI SICUREZZA ---
if "quiz_source_text" not in st.session_state or not st.session_state.quiz_source_text:
    st.warning("⚠️ Nessun dato. Torna alla Chat.")
    if st.button("⬅️ Home"): st.switch_page("app.py")
    st.stop()

if "api_key" not in st.session_state:
    st.error("Chiave API mancante.")
    st.stop()

genai.configure(api_key=st.session_state.api_key)

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

# ==============================================================================
# LOGICA GENERAZIONE (CON TAGLIO DI SICUREZZA)
# ==============================================================================
if "quiz_data" not in st.session_state or st.session_state.get("refresh_quiz", False):
    with st.status("🧠 Generazione Quiz...", expanded=True) as status:
        
        # --- FIX CRUCIALE PER ERRORE 429 ---
        # Prendiamo il testo, ma lo tagliamo preventivamente a 35.000 caratteri.
        # Questo assicura che il payload non sia mai troppo grande per il limite TPM.
        testo_input = st.session_state.get("quiz_source_text", "")
        immagini_input = st.session_state.get("quiz_images_list", [])

        prompt_text = f"""
        Genera un quiz sul tema richiesto dall'utente'
        
        FORMATO JSON RICHIESTO (NON AGGIUNGERE ALTRO):
        [
            {{
                "question": "Domanda...", 
                "options": ["Opzione A", "Opzione B", "Opzione C", "Opzione D"], 
                "answer": "Opzione A",
                "explanation": "Spiegazione breve."
            }}
        ]
        
        informazioni:
        {testo_input}
        """
        
        payload = [prompt_text]
        if immagini_input:
            payload.extend(immagini_input)
        model_name = st.session_state.get("active_model_id", "gemini-2.5-pro")
        model = genai.GenerativeModel(model_name)
        
        # --- BLOCCO RETRY ---
        max_retries = 3
        retry_delay = 2 
        quiz_generato = False
        
        for attempt in range(max_retries):
            try:
                resp = model.generate_content(payload)
                quiz_generato = True
                break 
            except ResourceExhausted:
                status.update(label=f"⚠️ Traffico intenso. Riprovo ({attempt+1}/{max_retries})...", state="running")
                time.sleep(retry_delay)
                retry_delay *= 2 
            except Exception as e:
                st.error(f"Errore tecnico: {e}")
                st.stop()
        
        if not quiz_generato:
            st.error("❌ Impossibile generare il quiz: Il testo è ancora troppo grande per il tuo piano API attuale.")
            if st.button("Torna alla Home"): st.switch_page("app.py")
            st.stop()
            
        # --- PARSING ---
        try:
            json_text = resp.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(json_text)
            
            st.session_state.quiz_data = data
            st.session_state.quiz_index = 0
            st.session_state.user_answers = {} 
            st.session_state.refresh_quiz = False
            status.update(label="Pronto!", state="complete", expanded=False)
            st.rerun()
            
        except Exception as e:
            st.error(f"Errore interpretazione dati: {e}")
            if st.button("Riprova"): 
                st.session_state.refresh_quiz = True
                st.rerun()
            st.stop()

# ==============================================================================
# MOTORE DI GIOCO
# ==============================================================================
q_data = st.session_state.quiz_data
total = len(q_data)
idx = st.session_state.quiz_index
current_q = q_data[idx]

# --- NAVIGAZIONE SUPERIORE ---
c1, c2, c3 = st.columns([1, 8, 1]) 
with c1:
    if st.button("⬅️", disabled=(idx == 0), key="nav_prev", use_container_width=True):
        st.session_state.quiz_index -= 1
        st.rerun()
with c2:
    st.progress((idx + 1) / total)
    st.caption(f"Domanda {idx + 1} / {total}")
with c3:
    if st.button("➡️", disabled=(idx == total - 1), key="nav_next", use_container_width=True):
        st.session_state.quiz_index += 1
        st.rerun()

st.markdown(f"### {current_q['question']}")

risposta_gia_data = st.session_state.user_answers.get(idx)

# --- GRIGLIA OPZIONI ---
cols = st.columns(2)
for i, opt in enumerate(current_q['options']):
    btn_label = opt
    btn_type = "secondary"
    is_disabled = False
    
    if risposta_gia_data:
        is_disabled = True
        if opt == current_q['answer']:
            btn_type = "primary"
            btn_label = f"✅ {opt}"
        elif opt == risposta_gia_data and opt != current_q['answer']:
            btn_type = "secondary"
            btn_label = f"❌ {opt}"
    
    with cols[i % 2]:
        if st.button(btn_label, key=f"q{idx}_opt{i}", type=btn_type, disabled=is_disabled, use_container_width=True):
            st.session_state.user_answers[idx] = opt
            st.rerun()

# --- SPIEGAZIONE ---
if risposta_gia_data:
    explanation_text = current_q.get('explanation', "Nessuna spiegazione.")
    st.markdown(f"""<div class="explanation-box"><div class="exp-title">💡 Info</div>{explanation_text}</div>""", unsafe_allow_html=True)

st.divider()

# --- FOOTER & SALVATAGGIO IN CHAT ---
col_foot1, col_foot2 = st.columns([4, 1])
with col_foot1:
    correct_count = 0
    for k, v in st.session_state.user_answers.items():
        if q_data[k]['answer'] == v: correct_count += 1
    st.markdown(f"**Punti:** {correct_count}/{len(st.session_state.user_answers)}")

with col_foot2:
    # 2. SALVATAGGIO IN CHAT ALL'USCITA
    if st.button("🏠 Esci", use_container_width=True):
        
        # --- A. RECUPERO DATI ESATTI DALLA SESSIONE CORRENTE ---
        dati_quiz_correnti = st.session_state.get('quiz_data', [])
        risposte_utente_correnti = st.session_state.get('user_answers', {})
        
        if not dati_quiz_correnti:
            st.error("Errore: Dati quiz non trovati!")
            st.stop()

        # --- B. CALCOLO PUNTEGGIO ---
        punteggio_finale = 0
        total_questions = len(dati_quiz_correnti)
        
        for k_idx, ans in risposte_utente_correnti.items():
            if k_idx < total_questions:
                if dati_quiz_correnti[k_idx]['answer'] == ans:
                    punteggio_finale += 1
        
        # --- C. COSTRUZIONE DEL LOG PERFETTO ---
        msg_header = f"""
        📊 **Risultati Sessione Quiz**
        - **Punteggio:** {punteggio_finale}/{total_questions}
        """
        
        dettaglio_domande = "\n\n--- 📝 **Recap Domande & Risposte** ---\n"
        
        for i, q in enumerate(dati_quiz_correnti):
            user_ans = risposte_utente_correnti.get(i, "⚠️ *Non risposta*")
            correct_ans = q['answer']
            question_text = q['question']
            explanation = q.get('explanation', 'Nessuna spiegazione.')
            
            # Determinazione Icona
            if user_ans == correct_ans:
                status = "✅ **Corretta**"
                ans_text = f"La tua risposta: **{user_ans}**"
            else:
                status = "❌ **Errata**"
                ans_text = f"La tua risposta: **{user_ans}**\nRisposta giusta: **{correct_ans}**"

            # Formattazione Blocco
            dettaglio_domande += f"""
**{i+1}. {question_text}**
{status}
{ans_text}
> 🎓 *{explanation}*

"""
        
        full_log_content = msg_header + dettaglio_domande

        # --- D. INIEZIONE DIRETTA NELLA CRONOLOGIA CHAT ---
        if "messages" not in st.session_state:
            st.session_state.messages = []
            
        st.session_state.messages.append({
            "role": "assistant", 
            "content": full_log_content, 
            "pinned": False
        })
        
        # --- E. PULIZIA E USCITA ---
        st.session_state.refresh_quiz = False 
        st.switch_page("app.py")

# Riavvio Quiz
if len(st.session_state.user_answers) == total:
    if st.button("🔄 Nuovo Quiz", use_container_width=True):
        st.session_state.refresh_quiz = True
        st.rerun()

# ==============================================================================
# 3. SCRIPT NAVIGAZIONE TASTIERA BLINDATO (ARROW LEFT / RIGHT)
# ==============================================================================
components.html("""
<script>
    const handleQuizNavigation = (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        const keyMap = {
            'ArrowLeft': '⬅️',
            'ArrowRight': '➡️'
        };

        if (keyMap[e.key]) {
            const doc = window.parent.document;
            const buttons = Array.from(doc.querySelectorAll('button'));
            const targetBtn = buttons.find(el => el.innerText.includes(keyMap[e.key]));

            if (targetBtn && !targetBtn.disabled) {
                targetBtn.click();
                e.preventDefault(); 
                e.stopPropagation();
            }
        }
    };

    if (window.parent.quizHandlerAttached) {
        window.parent.document.removeEventListener('keydown', window.parent.quizHandlerAttached);
    }

    window.parent.quizHandlerAttached = handleQuizNavigation;
    window.parent.document.addEventListener('keydown', handleQuizNavigation);
</script>
""", height=0, width=0)