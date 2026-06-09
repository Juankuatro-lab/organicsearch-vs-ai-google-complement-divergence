# Prétraitement des données GSC : impressions organiques vs IA
## Mode d'emploi
### Étape 1 — Récupérez vos exports GSC
Allez dans **Google Search Console → Performances → Résultats de recherche**, définissez votre plage de dates, puis cliquez sur **Exporter → Télécharger au format CSV ou Excel**. Faites-le deux fois :
- **Rapport standard** — clics, impressions, CTR, position par page
- **Rapport des fonctionnalités IA** — basculez le type de recherche sur « Fonctionnalités IA » et exportez à nouveau
### Étape 2 — Ouvrez Google Colab
Allez sur [colab.research.google.com](https://colab.research.google.com) → Nouveau notebook, collez le script dans une seule cellule et exécutez-le.
### Étape 3 — Importez vos fichiers
Lorsque vous y êtes invité, cliquez sur **Choisir les fichiers** et sélectionnez les deux exports en même temps. Le script détectera automatiquement quel fichier est lequel d'après la structure de leurs feuilles.
### Étape 4 — Ajustez les seuils (facultatif)
| Variable | Valeur par défaut | Description |
|----------|---------|-------------|
| `CLICKS_PERCENTILE` | `0.25` | Ce qui compte comme « faible nombre de clics » pour la détection du zéro-clic |
| `AI_PERCENTILE` | `0.75` | Ce qui compte comme « impressions IA élevées » |
### Étape 5 — Clustering et graphiques
Pour les segments GSC uniquement, GSC IA uniquement et zéro-clic, le script :
- Supprime le domaine de chaque URL et tokenise le chemin
- Exécute un clustering HDBSCAN
- Applique un encodage one-hot pour étiqueter chaque cluster
- Trace des graphiques en barres Plotly montrant les impressions par catégorie
## Résultats
### Fichiers CSV
| Fichier | Segment | Description |
|------|---------|-------------|
| `gsc_ai_all_pages.csv` | Toutes les pages | Jeu de données fusionné complet avec étiquettes de segment |
| `gsc_ai_user_ai_signals.csv` | Signaux utilisateur et IA | Pages présentes à la fois dans GSC standard et GSC IA |
| `gsc_ai_gsc_only.csv` | GSC uniquement | Pages organiques absentes de l'IA — intention BOFU ou lacune technique d'éligibilité à l'IA ? |
| `gsc_ai_ai_only.csv` | IA uniquement | Pages visibles dans l'IA hors du top GSC — intention TOFU ou informationnelle ? |
| `gsc_ai_zero_click.csv` | Proche du zéro-clic | Pages où l'IA répond à la requête, générant peu de clics |
