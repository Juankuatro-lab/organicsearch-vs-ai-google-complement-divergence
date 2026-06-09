# GSC Organic vs AI Impressions — Application Streamlit

Croisez vos exports Google Search Console **standard** et **« Fonctionnalités IA »** pour segmenter vos pages, détecter le zéro-clic et visualiser les clusters d'URL.

## Mode d'emploi

### Étape 1 — Récupérez vos exports GSC
Allez dans **Google Search Console → Performances → Résultats de recherche**, définissez votre plage de dates, puis cliquez sur **Exporter → Télécharger au format Excel**. Faites-le deux fois :
- **Rapport standard** — clics, impressions, CTR, position par page
- **Rapport des fonctionnalités IA** — basculez le type de recherche sur « Fonctionnalités IA » et exportez à nouveau

### Étape 2 — Lancez l'application
En local :
```bash
pip install -r requirements.txt
streamlit run app.py
```
L'application s'ouvre automatiquement dans votre navigateur.

### Étape 3 — Importez vos fichiers
Dans la barre latérale, glissez vos **deux** exports `.xlsx` dans la zone d'import. L'application détecte automatiquement quel fichier est le standard et lequel est le rapport IA d'après la structure de leurs feuilles.

### Étape 4 — Ajustez les seuils (facultatif)
Deux sliders dans la barre latérale recalculent toute l'analyse en direct :

| Seuil | Défaut | Description |
|-------|--------|-------------|
| Percentile « faible nombre de clics » | `0.25` | Ce qui compte comme peu de clics pour la détection du zéro-clic |
| Percentile « impressions IA élevées » | `0.75` | Ce qui compte comme un fort volume d'impressions IA |

### Étape 5 — Clustering et graphiques
Pour les segments GSC uniquement et GSC IA uniquement, l'application :
- Supprime le domaine de chaque URL et tokenise le chemin
- Exécute un clustering HDBSCAN
- Applique un encodage one-hot pour étiqueter chaque cluster
- Affiche des graphiques en barres Plotly montrant les impressions par catégorie, répartis dans des onglets

## Fonctionnalités

- **Auto-détection** des fichiers standard vs IA
- **Métriques en temps réel** : impressions totales, part IA vs GSC, recouvrement, pages zéro-clic
- **Sliders interactifs** pour les seuils de segmentation
- **Onglets** séparant graphiques GSC, graphiques IA et tableau complet filtrable
- **Mise en cache** (`@st.cache_data`) : pas de recalcul tant que fichiers et seuils restent identiques
- **Export CSV** en un clic pour chaque segment

## Résultats — Exports CSV

| Fichier | Segment | Description |
|---------|---------|-------------|
| `gsc_ai_all_pages.csv` | Toutes les pages | Jeu de données fusionné complet avec étiquettes de segment |
| `gsc_ai_user_ai_signals.csv` | Signaux utilisateur et IA | Pages présentes à la fois dans GSC standard et GSC IA |
| `gsc_ai_gsc_only.csv` | GSC uniquement | Pages organiques absentes de l'IA — intention BOFU ou lacune technique d'éligibilité à l'IA ? |
| `gsc_ai_ai_only.csv` | IA uniquement | Pages visibles dans l'IA hors du top GSC — intention TOFU ou informationnelle ? |
| `gsc_ai_zero_click.csv` | Proche du zéro-clic | Pages où l'IA répond à la requête, générant peu de clics |

## Déploiement sur Streamlit Community Cloud

1. Poussez `app.py` et `requirements.txt` dans un dépôt GitHub
2. Rendez-vous sur [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Pointez vers votre dépôt et le fichier `app.py`, puis déployez

> **Note :** `hdbscan` nécessite parfois une compilation. Si le build échoue sur le cloud, ajoutez un fichier `packages.txt` contenant `build-essential`, ou pinnez une version compatible de `hdbscan`.

## Dépendances

Listées dans `requirements.txt` : `streamlit`, `pandas`, `numpy`, `plotly`, `scikit-learn`, `hdbscan`, `openpyxl`.
