import streamlit as st
import requests
import numpy as np
import time
import plotly.graph_objects as go

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Santander | Simulation Prêt",
    page_icon="🏦",
    layout="centered"
)

API_URL = "http://127.0.0.1:5000/predict"

# --- CSS (JUSTE POUR RÉPARER LES INPUTS ET LES BOUTONS ROUGES) ---
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
    
    /* CORRECTION INPUTS : Bordures et fond blanc pour bien les voir */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
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
    
    /* Cadre blanc autour du formulaire (Version stable) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- GESTION DE L'ÉTAT ---
# On garde les données en mémoire
defaults = {
    'step': 0,
    'type_projet': "Achat Véhicule",
    'montant': 10000,
    'duree': 24,
    'civilite': "Monsieur",
    'age': 35,
    'situation_familiale': "Célibataire",
    'logement': "Locataire",
    'emploi': "CDI",
    'revenus': 2500,
    'charges': 800
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- FONCTIONS DE NAVIGATION (CORRIGÉES) ---
def next_step(): 
    st.session_state.step += 1
    st.rerun() # Force le rechargement immédiat

def prev_step(): 
    st.session_state.step -= 1
    st.rerun()

def restart(): 
    st.session_state.step = 0
    st.session_state.user_data = {}
    st.rerun()

def get_gauge_chart(probability):
    score = int((1 - probability) * 1000)
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Score de Solvabilité"},
        gauge = {
            'axis': {'range': [0, 1000], 'tickwidth': 1},
            'bar': {'color': "#e2001a"},
            'bgcolor': "white",
            'steps': [
                {'range': [0, 500], 'color': '#ffebee'},
                {'range': [500, 1000], 'color': '#e8f5e9'}
            ],
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig


# --- DÉBUT DU FORMULAIRE ---
# On utilise un conteneur natif pour faire la "carte blanche" sans bug
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
        
        # Image locale ou icône pour éviter les erreurs de chargement
        st.info("👋 Bienvenue sur votre espace client sécurisé.")
        
        if st.button("Commencer ma simulation 🚀"):
            next_step()

    # ==========================================
    # ÉTAPE 1 : LE PROJET
    # ==========================================
    elif st.session_state.step == 1:
        st.markdown("<div class='header-style'>1. Votre Projet</div>", unsafe_allow_html=True)
        
        st.session_state.type_projet = st.selectbox(
            "Quel est votre projet ?",
            ["Achat Véhicule", "Travaux / Déco", "Trésorerie / Loisirs", "Rachat de crédit"],
            index=["Achat Véhicule", "Travaux / Déco", "Trésorerie / Loisirs", "Rachat de crédit"].index(st.session_state.type_projet)
        )
        
        st.session_state.montant = st.number_input(
            "Montant souhaité (€)", 
            min_value=1000, max_value=75000, value=st.session_state.montant, step=500
        )
        
        st.session_state.duree = st.select_slider(
            "Durée de remboursement (mois)",
            options=[12, 24, 36, 48, 60, 72, 84],
            value=st.session_state.duree
        )
        
        mensualite_estimee = (st.session_state.montant / st.session_state.duree) * 1.04
        st.info(f"Mensualité estimée (hors assurance) : **{mensualite_estimee:.2f} € / mois**")
        
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
            st.session_state.age = st.number_input("Votre âge", 18, 90, st.session_state.age)
            
        with col2:
            st.session_state.situation_familiale = st.selectbox(
                "Situation familiale", 
                ["Célibataire", "Marié(e) / Pacsé(e)", "Divorcé(e)", "Veuf(ve)"],
                index=["Célibataire", "Marié(e) / Pacsé(e)", "Divorcé(e)", "Veuf(ve)"].index(st.session_state.situation_familiale)
            )
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
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Retour"): prev_step()
        with c2:
            if st.button("Suivant →"): next_step()

    # ==========================================
    # ÉTAPE 3 : VOS FINANCES
    # ==========================================
    elif st.session_state.step == 3:
        st.markdown("<div class='header-style'>3. Vos Finances</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.revenus = st.number_input("Revenus mensuels nets (€)", 0, 20000, st.session_state.revenus)
        with col2:
            st.session_state.charges = st.number_input("Charges mensuelles (€)", 0, 10000, st.session_state.charges)
            
        st.markdown("---")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Retour"): prev_step()
        with c2:
            if st.button("Analyser ma demande"):
                # Simulation d'attente
                progress = st.progress(0)
                for i in range(100):
                    time.sleep(0.01)
                    progress.progress(i + 1)
                
                # APPEL API (Simulation avec données aléatoires pour l'exemple)
                fake_features = np.random.randn(200).tolist()
                
                try:
                    response = requests.post(API_URL, json={'features': fake_features})
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.result_proba = result['probability']
                        next_step()
                    else:
                        st.error("Erreur technique API")
                        
                except Exception as e:
                    # Fallback pour la démo
                    st.session_state.result_proba = np.random.uniform(0.1, 0.9)
                    next_step()

    # ==========================================
    # ÉTAPE 4 : RÉSULTAT
    # ==========================================
    elif st.session_state.step == 4:
        proba = st.session_state.result_proba
        
        if proba < 0.5:
            st.balloons()
            st.success("### ✅ Crédit Pré-Accordé !")
            st.write("Félicitations, votre profil financier correspond à nos critères d'excellence.")
            st.write(f"Vous pouvez emprunter **{st.session_state.montant} €** sur **{st.session_state.duree} mois**.")
            st.plotly_chart(get_gauge_chart(proba), use_container_width=True)
        else:
            st.error("### ❌ Demande Refusée")
            st.write("Votre dossier ne répond pas aux critères d'éligibilité actuels.")
            st.plotly_chart(get_gauge_chart(proba), use_container_width=True)
            
        if st.button("Nouvelle simulation"):
            restart()