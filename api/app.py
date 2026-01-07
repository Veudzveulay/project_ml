from flask import Flask, request, jsonify
import joblib
import numpy as np
import pandas as pd
import os
import lightgbm 

app = Flask(__name__)

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, '..', 'models', 'best_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, '..', 'models', 'scaler.pkl')

FEATURE_NAMES = [f"var_{i}" for i in range(200)]

# --- CHARGEMENT ---
model = None
scaler = None

try:
    print("🔄 Chargement du modèle et du scaler...")
    scaler = joblib.load(SCALER_PATH)
    model = joblib.load(MODEL_PATH)
    print(f"✅ Modèle LightGBM chargé avec succès !")
except Exception as e:
    print(f"⚠️ ERREUR CRITIQUE : {e}")

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API online', 'backend': 'LightGBM'})

@app.route('/predict', methods=['POST'])
def predict():
    if not model:
        return jsonify({'error': 'Model not loaded'}), 500
    
    try:
        data = request.get_json()
        features = data.get('features')
        
        # 1. Création d'un DataFrame avec les noms de colonnes (Fix du Warning)
        # On s'assure que c'est une liste de listes (2D)
        features_df = pd.DataFrame([features], columns=FEATURE_NAMES)
        
        # 2. Scaling (Le scaler renvoie un numpy array, on le remet en DF)
        features_scaled = scaler.transform(features_df)
        # LightGBM veut un dataframe si on veut garder les noms, 
        # mais le scaler a enlevé les noms. On les remet.
        features_scaled_df = pd.DataFrame(features_scaled, columns=FEATURE_NAMES)
        
        # 3. Prédiction
        prediction_binary = model.predict(features_scaled_df)[0]
        probability = model.predict_proba(features_scaled_df)[0][1]
        
        return jsonify({
            'prediction': int(prediction_binary),
            'probability': float(probability),
            'risk_level': 'High' if probability > 0.5 else 'Low',
            'message': 'Transaction Suspecte' if probability > 0.5 else 'Transaction Normale'
        })

    except Exception as e:
        # En cas d'erreur, on l'affiche dans le terminal de l'API
        print(f"Erreur de prédiction : {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # ⚠️ IMPORTANT : use_reloader=False empêche l'API de redémarrer en boucle
    print("🚀 Démarrage du serveur Flask sur le port 5000...")
    app.run(debug=True, use_reloader=False, port=5000)