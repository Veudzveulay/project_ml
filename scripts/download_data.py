import os
from kaggle.api.kaggle_api_extended import KaggleApi
import zipfile

def download_santander_data():
    # 1. Authentification
    api = KaggleApi()
    api.authenticate()
    
    print("✅ Authentification Kaggle réussie.")

    # 2. Définition des chemins
    competition_name = 'santander-customer-transaction-prediction'
    # On remonte d'un niveau (..) pour aller dans data depuis scripts/
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Création du dossier data s'il n'existe pas
    if not os.path.exists(data_path):
        os.makedirs(data_path)

    # 3. Téléchargement
    print(f"⬇️ Téléchargement des données dans {data_path}...")
    try:
        api.competition_download_files(competition_name, path=data_path)
        
        # 4. Décompression
        zip_path = os.path.join(data_path, f"{competition_name}.zip")
        print("📦 Décompression des fichiers...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(data_path)
            
        # Nettoyage du zip (optionnel)
        os.remove(zip_path)
        print("🎉 Terminé ! Les fichiers train.csv et test.csv sont prêts.")
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        print("💡 Astuce : As-tu accepté les règles de la compétition sur le site Kaggle ?")

if __name__ == "__main__":
    download_santander_data()