# **Assistant de Suivi Financier - Génération d'Emails et Analyse Client**

## 📖 **Description**
Ce projet est un assistant financier intelligent conçu pour aider les équipes financières à suivre les paiements clients, analyser leur comportement et générer des emails de relance personnalisés. Il utilise des technologies avancées comme **watsonx.data**, **watsonx.ai**, et **Code Engine**, offrant une solution complète et déployable.

## 🚀 **Fonctionnalités**
- **Analyse Client** : Génération de rapports détaillés sur le comportement de paiement des clients.
- **Relance Automatisée** : Création d'emails professionnels et personnalisés pour le suivi des factures.
- **Visualisation des Données** : Exploitation des données client via des transformations en **watsonx.data**.
- **Rapidité et Performance** : API multithreadée pour des réponses rapides.
- **Assistant Intelligent** : Intégration avec **watsonx.assistant** pour une interaction fluide avec l'utilisateur.

---

## 🛠 **Technologies Utilisées**
- **watsonx.data** : Pour la préparation et l’analyse des données, avec stockage en format Parquet dans COS et transformations via le moteur Presto.
- **watsonx.ai** : Utilisation de modèles GenAI pour la génération de contenu (emails, rapports).
- **Flask** : Développement de l'API backend pour la gestion des routes.
- **IBM Code Engine** : Déploiement scalable de l'application.
- **GitHub** : Gestion du code source et documentation.
- **OpenAPI** : Documentation des routes de l’API.

---

## 📋 **Étapes du Projet**

### 1️⃣ **Préparation des Données**
Les données utilisées sont confidentielles et ont été anonymisées. 
- Chargement des données dans **watsonx.data**.
- Conversion au format **Parquet** pour une meilleure performance.
- Application de transformations à l’aide de **Presto**.
- Exemple de capture de l’interface watsonx.data et du code utilisé :

*Ajoutez ici des captures d'écran ou du code pertinent.*

---

### 2️⃣ **Développement de l'API**
- Création de plusieurs routes pour des fonctionnalités spécifiques, comme :
  - `/get_client` : Récupération des informations client.
  - `/generate_follow_up_email` : Génération d'emails personnalisés.
  - `/get_invoice_status` : Consultation du statut des factures.
  - `/get_collector` : Informations sur les collecteurs de factures.
- Utilisation du **multithreading** pour assurer des réponses rapides.
- Exemple de fichier **OpenAPI.yaml** inclus pour documenter les endpoints.

---

### 3️⃣ **Génération Automatique d'Emails**
- Intégration avec **watsonx.ai** pour utiliser un modèle de génération de texte.
- Exemple de prompt utilisé :
  ```plaintext
  Génère un e-mail de relance pour la facture suivante :
  - Client : {client}
  - Numéro de la facture : {invoice_number}
  - Date de la facture : {invoice_date}
  - Date d'échéance : {due_date}
  - Montant dû : {amount_due}

---

### 4️⃣ **Déploiement**
- Déploiement de l'application sur **IBM Code Engine** pour une gestion scalable et rapide des requêtes.
- Configuration de l'URL API pour une utilisation globale.
- Intégration de l'API avec les services cloud pour permettre un accès à faible latence et haute disponibilité.

---

### 5️⃣ **Assistant Intelligent**
- Développement avec **watsonx.assistant** pour permettre aux utilisateurs finaux d’interagir facilement avec les données et fonctionnalités du projet.
- Simulations rédigées pour montrer l'utilisation des fonctionnalités dans un environnement sans accès aux données réelles.

---

## 📌 $$Utilisation**

1. Clonez ce dépôt :
'''bash
git clone https://github.com/username/assistant-financier.git
cd assistant-financier
'''

2. Exécutez le script pour lancer le serveur en interne:
'''bash
./install_local_standalone.sh
./run_local_standalone.sh
'''

3. Exécutez le script pour lancer le serveur en Docker:
'''bash
./run_local_container.sh
'''