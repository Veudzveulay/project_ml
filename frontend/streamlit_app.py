import streamlit as st
import requests
import numpy as np
import time
import plotly.graph_objects as go
import json
from pathlib import Path
from datetime import date

TOP_VARS = ["var_139","var_81","var_110","var_6","var_12","var_76","var_26","var_146","var_190","var_53"]
TOP_IDX = [int(v.split("_")[1]) for v in TOP_VARS]

DIRECTION_CACHE_PATH = Path("direction_cache.json")


# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Santander | Simulation Prêt",
    page_icon="🏦",
    layout="centered",
    initial_sidebar_state="collapsed"
)

API_URL = "http://127.0.0.1:5000/predict"

# --- 2. STYLE CSS ---
st.markdown("""
    <style>
    /* Fond de la page */
    .main {
        background-color: #f5f7f9;
    }
    
    /* Boutons en Rouge Santander */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #e2001a;
        color: white;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #cc0018;
        color: white;
    }
    
    /* CORRECTION INPUTS : Bordures et fond blanc */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"], .stDateInput input {
        background-color: white !important;
        border: 1px solid #ced4da !important;
        color: black !important;
        border-radius: 5px;
    }
    
    /* Style des titres */
    .header-style {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
        color: #e2001a;
        border-bottom: 2px solid #e2001a;
        padding-bottom: 10px;
    }
    
    /* Cadre blanc autour du formulaire */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. GESTION DE L'ÉTAT ---
if 'step' not in st.session_state:
    st.session_state.step = 0

# Ajout des nouveaux champs (apport, assurance, date, banque, etc.)
defaults = {
    'type_projet': "Achat Véhicule",
    'montant': 10000,
    'apport': 0,
    'duree': 24,
    'assurance': False,
    'civilite': "Monsieur",
    'date_naissance': date(1990, 1, 1),
    'situation_familiale': "Célibataire",
    'logement': "Locataire",
    'emploi': "CDI",
    'anciennete': 2,
    'revenus': 2500,
    'charges': 800,
    'autres_credits': 0,
    'banque': "Autre"
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 4. FONCTIONS MÉTIER ---
def generate_smart_features(montant, apport, duree, revenus, charges, autres_credits, assurance):
    """Features déterministes + ajustement sur TOP features (SHAP)"""

    duree = max(int(duree), 1)

    montant_finance = max(montant - apport, 1000)

    taux_interet = 0.039
    taux_assurance = 0.005 if assurance else 0.0

    mensualite = (montant_finance / duree) * (1 + (taux_interet + taux_assurance) / 12 * duree)

    total_charges = charges + autres_credits + mensualite
    taux_endettement = (total_charges / revenus) * 100 if revenus > 0 else 100.0
    reste_a_vivre = revenus - total_charges

    seed = (
        int(montant) * 31
        + int(apport) * 17
        + int(duree) * 13
        + int(revenus) * 7
        + int(charges) * 5
        + int(autres_credits) * 3
        + (1 if assurance else 0) * 11
    )
    rng = np.random.default_rng(seed)
    features = rng.normal(0, 1, 200)

    # IMPORTANT : directions apprises sur une base fixe
    direction_map = get_or_build_direction_map()

    # Risk métier [0..1]
    risk = 0.0
    if taux_endettement <= 33:
        risk += 0.0
    elif taux_endettement <= 45:
        risk += 0.5
    else:
        risk += 1.0

    if reste_a_vivre < 600:
        risk += 1.0
    elif reste_a_vivre < 1200:
        risk += 0.5
    else:
        risk += 0.0

    risk = min(max(risk / 2.0, 0.0), 1.0)

    amplitude = 2.0 + 4.0 * risk

    for idx in TOP_IDX:
        sign = direction_map.get(idx, 1)  # +1 => +delta augmente proba ; -1 => +delta diminue proba

        if risk <= 0.25:
            # bon profil -> on cherche à baisser la proba
            features[idx] -= sign * amplitude
        elif risk >= 0.75:
            # profil risqué -> on cherche à augmenter la proba
            features[idx] += sign * amplitude
        else:
            # zone intermédiaire
            features[idx] += sign * (amplitude * 0.35)

    return features.tolist(), taux_endettement, mensualite, reste_a_vivre

def next_step(): st.session_state.step += 1; st.rerun()
def prev_step(): st.session_state.step -= 1; st.rerun()
def restart():
    st.session_state.step = 0
    st.session_state.user_data = {}
    st.rerun()

def get_gauge_chart(probability):
    score = int((1 - probability) * 100)
    bar_color = "#22c55e" if probability < 0.5 else "#ef4444"
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Score de Solvabilité"},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': bar_color},
            'bgcolor': "white",
            'steps': [
                {'range': [0, 30], 'color': '#ffebee'},
                {'range': [30, 70], 'color': '#fff7ed'},
                {'range': [70, 100], 'color': '#e8f5e9'},
            ],
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig

def api_predict_proba(features: list) -> float:
    """Appelle l'API et renvoie probability (float)."""
    r = requests.post(API_URL, json={"features": features}, timeout=8)
    r.raise_for_status()
    data = r.json()
    return float(data["probability"])


def load_direction_cache():
    """Charge DIRECTION depuis un JSON si dispo."""
    if DIRECTION_CACHE_PATH.exists():
        try:
            data = json.loads(DIRECTION_CACHE_PATH.read_text(encoding="utf-8"))
            # clés en str -> int
            return {int(k): int(v) for k, v in data.items()}
        except Exception:
            return None
    return None


def save_direction_cache(direction: dict):
    """Sauvegarde DIRECTION dans un JSON (optionnel mais pratique)."""
    try:
        DIRECTION_CACHE_PATH.write_text(json.dumps(direction, indent=2), encoding="utf-8")
    except Exception:
        pass


def learn_directions_via_api(base_features: list, indices: list, delta: float = 0.35) -> dict:
    """
    Apprend direction[idx] = +1 si augmenter idx augmente la proba (plus risqué),
    sinon -1.
    """
    base = np.array(base_features, dtype=float)

    # proba de référence
    p0 = api_predict_proba(base.tolist())

    direction = {}
    for idx in indices:
        test = base.copy()
        test[idx] += delta
        p1 = api_predict_proba(test.tolist())

        # +delta augmente la proba => direction +1 ; sinon -1
        direction[idx] = 1 if (p1 > p0) else -1

    return direction


def get_or_build_direction_map(_features_seeded_unused=None) -> dict:
    """
    1) Si session_state a déjà DIRECTION: return
    2) Sinon si JSON existe: load + stock session_state + return
    3) Sinon: sonde l'API 1 fois, stock, save JSON, return
    """
    if "DIRECTION" in st.session_state and isinstance(st.session_state["DIRECTION"], dict):
        # Si le dict est incomplet, on retombe sur rebuild
        if all(idx in st.session_state["DIRECTION"] for idx in TOP_IDX):
            return st.session_state["DIRECTION"]

    cached = load_direction_cache()
    if cached and all(idx in cached for idx in TOP_IDX):
        st.session_state["DIRECTION"] = cached
        return cached

    # base fixe : direction stable et indépendante des inputs user
    base_features = [0.0] * 200

    try:
        direction = learn_directions_via_api(base_features, TOP_IDX, delta=0.35)
        st.session_state["DIRECTION"] = direction
        save_direction_cache(direction)
        return direction
    except Exception as e:
        # fallback : alternance stable
        direction = {idx: (1 if i % 2 == 0 else -1) for i, idx in enumerate(TOP_IDX)}
        st.session_state["DIRECTION"] = direction

        # Option debug (à activer si besoin)
        # st.warning(f"Calibration directions en fallback (API indisponible). Détail: {e}")

        return direction

# --- 5. EN-TÊTE ---
if st.session_state.step < 4:
    st.progress((st.session_state.step) / 3)

# --- 6. LE FORMULAIRE ---
with st.container(border=True):

    # ==========================================
    # ÉTAPE 0 : ACCUEIL
    # ==========================================
    if st.session_state.step == 0:
        st.title("Simulez votre Prêt Personnel")
        st.write("Réalisez vos projets en quelques minutes. Obtenez une réponse de principe immédiate.")
        
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        col1.metric("Taux à partir de", "3.90 %")
        col2.metric("Montant jusqu'à", "75 000 €")
        col3.metric("Durée jusqu'à", "84 mois")
        st.markdown("---")
        
        st.info("👋 Bienvenue sur votre espace client sécurisé.")
        
        if st.button("Commencer ma simulation 🚀"):
            next_step()

    # ==========================================
    # ÉTAPE 1 : LE PROJET
    # ==========================================
    elif st.session_state.step == 1:
        st.markdown("<div class='header-style'>1. Votre Projet</div>", unsafe_allow_html=True)
        
        c_proj, c_assur = st.columns([2, 1])
        with c_proj:
            st.session_state.type_projet = st.selectbox(
                "Quel est votre projet ?",
                ["Achat Véhicule", "Travaux / Déco", "Trésorerie / Loisirs", "Rachat de crédit"],
                index=["Achat Véhicule", "Travaux / Déco", "Trésorerie / Loisirs", "Rachat de crédit"].index(st.session_state.type_projet)
            )
        with c_assur:
            st.write("") # Spacer
            st.write("") 
            st.session_state.assurance = st.checkbox("Assurance emprunteur ?", value=st.session_state.assurance)

        col1, col2 = st.columns(2)
        with col1:
            st.session_state.montant = st.number_input(
                "Montant du projet (€)", min_value=1000, max_value=75000, value=st.session_state.montant, step=500
            )
        with col2:
            st.session_state.apport = st.number_input(
                "Votre apport personnel (€)", min_value=0, max_value=75000, value=st.session_state.apport, step=500
            )
        
        st.session_state.duree = st.select_slider(
            "Durée de remboursement (mois)",
            options=[12, 24, 36, 48, 60, 72, 84],
            value=st.session_state.duree
        )
        
        # Calcul intermédiaire pour l'affichage
        montant_a_financer = max(st.session_state.montant - st.session_state.apport, 0)
        mensualite_estimee = (montant_a_financer / st.session_state.duree) * 1.045
        
        st.info(f"Montant à financer : **{montant_a_financer} €** | Mensualité estimée : **{mensualite_estimee:.2f} € / mois**")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Retour"): prev_step()
        with c2:
            if st.button("Suivant →"): next_step()

    # ==========================================
    # ÉTAPE 2 : VOTRE PROFIL
    # ==========================================
    elif st.session_state.step == 2:
        st.markdown("<div class='header-style'>2. Votre Profil</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.civilite = st.radio("Civilité", ["Madame", "Monsieur"], horizontal=True, index=0 if st.session_state.civilite=="Madame" else 1)
            st.session_state.date_naissance = st.date_input("Date de naissance", value=st.session_state.date_naissance, min_value=date(1940,1,1), max_value=date(2005,12,31))
            st.session_state.situation_familiale = st.selectbox(
                "Situation familiale", 
                ["Célibataire", "Marié(e) / Pacsé(e)", "Divorcé(e)", "Veuf(ve)"],
                index=0
            )
            
        with col2:
            st.session_state.logement = st.selectbox(
                "Statut logement",
                ["Propriétaire", "Locataire", "Logé par la famille"],
                index=["Propriétaire", "Locataire", "Logé par la famille"].index(st.session_state.logement)
            )
            st.session_state.emploi = st.selectbox(
                "Situation professionnelle",
                ["CDI", "CDD", "Fonctionnaire", "Indépendant", "Retraité", "Sans emploi"],
                index=["CDI", "CDD", "Fonctionnaire", "Indépendant", "Retraité", "Sans emploi"].index(st.session_state.emploi)
            )
            st.session_state.anciennete = st.number_input("Ancienneté (années)", 0, 50, st.session_state.anciennete)

        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Retour"): prev_step()
        with c2:
            if st.button("Suivant →"): next_step()

    # ==========================================
    # ÉTAPE 3 : VOS FINANCES & CALCUL
    # ==========================================
    elif st.session_state.step == 3:
        st.markdown("<div class='header-style'>3. Vos Finances</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.revenus = st.number_input("Revenus mensuels nets (€)", 0, 20000, st.session_state.revenus)
            st.session_state.banque = st.selectbox("Banque principale", ["Crédit Agricole", "BNP Paribas", "Société Générale", "Boursorama", "Autre"], index=4)

        with col2:
            st.session_state.charges = st.number_input("Loyer / Crédit immo (€)", 0, 10000, st.session_state.charges)
            st.session_state.autres_credits = st.number_input("Autres crédits en cours (€/mois)", 0, 5000, st.session_state.autres_credits)
            
        st.markdown("---")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Retour"): prev_step()
        with c2:
            if st.button("Analyser ma demande"):
                # 1. Simulation d'attente "Traitement"
                progress = st.progress(0)
                for i in range(100):
                    time.sleep(0.015)
                    progress.progress(i + 1)
                
                # 2. Génération des features intelligentes + Calcul du taux réel
                # On passe tous les nouveaux champs à la fonction
                smart_features, taux_endettement, mensualite_finale, reste_a_vivre = generate_smart_features(
                    st.session_state.montant, st.session_state.apport, st.session_state.duree,
                    st.session_state.revenus, st.session_state.charges, 
                    st.session_state.autres_credits, st.session_state.assurance
                )
                
                # On sauvegarde les résultats pour l'étape 4
                st.session_state.taux_endettement = taux_endettement
                st.session_state.mensualite_finale = mensualite_finale
                st.session_state.reste_a_vivre = reste_a_vivre
                
                # 3. Appel API
                try:
                    response = requests.post(API_URL, json={'features': smart_features})
                    
                    if response.status_code == 200:
                        proba_modele = response.json()['probability']
                        
                        # --- 4. COUCHE DE COHÉRENCE MÉTIER ---
                        final_proba = proba_modele

                        if taux_endettement < 33:
                            final_proba = min(proba_modele, 0.30) # Vert foncé
                        elif taux_endettement > 45:
                            final_proba = max(proba_modele, 0.70) # Rouge
                        else:
                            # Entre 33% et 45%, on laisse une zone orange/grise selon le modèle
                            # mais on s'assure de ne pas être trop optimiste
                            final_proba = max(proba_modele, 0.45) 

                        st.session_state.result_proba = final_proba
                        next_step() # Go to step 4
                    else:
                        st.error("Erreur technique API")
                        
                except Exception as e:
                    # Fallback si l'API est éteinte
                    st.session_state.result_proba = 0.8 if taux_endettement > 35 else 0.1
                    next_step()
    # ==========================================
    # ÉTAPE 4 : RÉSULTAT
    # ==========================================
    elif st.session_state.step == 4:
        proba = st.session_state.result_proba
        taux = st.session_state.get('taux_endettement', 0)
        mens = st.session_state.get('mensualite_finale', 0)
        rav = st.session_state.get("reste_a_vivre", 0)
        
        # Décision (Seuil 0.5)
        accord = proba < 0.5 
        
        if accord:
            st.balloons()
            st.success("### ✅ Accord de Principe")
            st.write(f"Félicitations, votre demande de **{st.session_state.montant - st.session_state.apport} €** est pré-approuvée.")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Mensualité", f"{mens:.2f} €")
            c2.metric("Taux d'endettement", f"{taux:.1f} %")
            c3.metric("Durée", f"{st.session_state.duree} mois")
            st.metric("Reste à vivre", f"{rav:.0f} €")
            
            st.info("Un conseiller va vous contacter sous 24h pour finaliser le contrat.")
        else:
            st.error("### ❌ Demande Refusée")
            st.write("Compte tenu des éléments fournis, nous ne pouvons donner une suite favorable.")
            st.metric("Taux d'endettement après projet", f"{taux:.1f} %", delta="- Trop élevé", delta_color="inverse")
            st.metric("Reste à vivre", f"{rav:.0f} €")
            
        if st.button("Nouvelle simulation"):
            restart()