#!/bin/bash

# 1. Lancer l'API Flask en arrière-plan (&) sur le port 5000
# On utilise gunicorn pour la performance
echo "🚀 Démarrage de l'API Flask..."
gunicorn api.app:app --bind 127.0.0.1:5000 --daemon

# Petit temps de pause pour être sûr que l'API est prête
sleep 5

# 2. Lancer Streamlit au premier plan
# Streamlit doit écouter sur le port fourni par Render ($PORT)
echo "🚀 Démarrage de Streamlit..."
streamlit run frontend/streamlit_app.py --server.port $PORT --server.address 0.0.0.0