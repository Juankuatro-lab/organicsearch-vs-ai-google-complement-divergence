"""
GSC Organic vs AI Impressions — Application Streamlit
=====================================================
Adaptation du script Google Colab pour un déploiement Streamlit.

Lancement local :
    pip install -r requirements.txt
    streamlit run app.py
"""

import io
import re
import warnings

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
import hdbscan

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION DE LA PAGE
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GSC Organic vs AI Impressions",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 GSC Organic vs AI Impressions")
st.caption(
    "Croisez vos exports Google Search Console standard et « Fonctionnalités IA » "
    "pour segmenter vos pages et détecter le zéro-clic."
)


# ──────────────────────────────────────────────────────────────────────────────
#  FONCTIONS UTILITAIRES (mises en cache)
# ──────────────────────────────────────────────────────────────────────────────
def extract_path(url: str) -> str:
    """Retire le domaine et tokenise le chemin de l'URL."""
    url = re.sub(r"https?://[^/]+", "", str(url))
    url = re.sub(r"\.(html|htm|php)$", "", url)
    url = url.strip("/")
    return re.sub(r"[-/]", " ", url).strip()


@st.cache_data(show_spinner=False)
def detect_and_load(file_bytes_map: dict):
    """Auto-détecte le fichier standard vs IA et charge la feuille 'Pages'."""
    gsc_file = ai_file = None
    for fname, content in file_bytes_map.items():
        xl = pd.ExcelFile(io.BytesIO(content))
        if "Queries" in xl.sheet_names:
            gsc_file = fname
        else:
            ai_file = fname

    # Repli : tri alphabétique si la détection échoue
    if not gsc_file or not ai_file:
        names = sorted(file_bytes_map.keys())
        gsc_file, ai_file = names[0], names[1]

    gsc = pd.read_excel(io.BytesIO(file_bytes_map[gsc_file]), sheet_name="Pages")
    gsc_ai = pd.read_excel(io.BytesIO(file_bytes_map[ai_file]), sheet_name="Pages")
    return gsc_file, ai_file, gsc, gsc_ai


@st.cache_data(show_spinner=False)
def run_clustering(df: pd.DataFrame, impression_col: str):
    """Clustering HDBSCAN sur les chemins d'URL + one-hot encoding des clusters."""
    df = df.copy()

    if df.empty:
        return df, pd.DataFrame(columns=["category", "impressions"])

    df["path_tokens"] = df["page"].apply(extract_path)

    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    tfidf_matrix = tfidf.fit_transform(df["path_tokens"])

    n_components = min(10, tfidf_matrix.shape[1] - 1, tfidf_matrix.shape[0] - 1)
    n_components = max(n_components, 1)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    reduced = svd.fit_transform(tfidf_matrix)

    clusterer = hdbscan.HDBSCAN(min_cluster_size=3, min_samples=1, metric="euclidean")
    df["cluster"] = clusterer.fit_predict(reduced)

    def get_cluster_label(cluster_id, cluster_df):
        if cluster_id == -1:
            return "non catégorisé"
        tokens = " ".join(cluster_df["path_tokens"].tolist())
        word_freq = pd.Series(tokens.split()).value_counts()
        stopwords = {"html", "www", "co", "uk"}
        word_freq = word_freq[~word_freq.index.isin(stopwords)]
        return word_freq.index[0] if len(word_freq) > 0 else f"cluster_{cluster_id}"

    cluster_labels = {
        cid: get_cluster_label(cid, df[df["cluster"] == cid])
        for cid in df["cluster"].unique()
    }
    df["cluster_label"] = df["cluster"].map(cluster_labels)

    ohe = pd.get_dummies(df["cluster_label"], prefix="category").astype(int)
    df = pd.concat([df, ohe], axis=1)

    chart_data = (
        df.groupby("cluster_label")[impression_col]
        .sum()
        .reset_index()
        .sort_values(impression_col, ascending=False)
    )
    chart_data.columns = ["category", "impressions"]
    return df, chart_data


@st.cache_data(show_spinner=False)
def build_dataset(file_bytes_map: dict, clicks_pct: float, ai_pct: float):
    """Pipeline complet : chargement → fusion → segmentation → clustering."""
    gsc_file, ai_file, gsc, gsc_ai = detect_and_load(file_bytes_map)

    # Renommage des colonnes
    gsc = gsc.rename(
        columns={
            "Top pages": "page",
            "Clicks": "gsc_clicks",
            "Impressions": "gsc_impressions",
            "CTR": "gsc_ctr",
            "Position": "gsc_position",
        }
    )
    gsc_ai = gsc_ai.rename(
        columns={"Top pages": "page", "Impressions": "ai_impressions"}
    )

    # Parts d'impressions
    total_gsc = gsc["gsc_impressions"].sum()
    total_ai = gsc_ai["ai_impressions"].sum()
    gsc["gsc_impression_share"] = gsc["gsc_impressions"] / total_gsc
    gsc_ai["ai_impression_share"] = gsc_ai["ai_impressions"] / total_ai

    # Métriques de recouvrement
    overlap = set(gsc["page"]).intersection(set(gsc_ai["page"]))
    ai_vs_gsc_share = (total_ai / total_gsc) * 100 if total_gsc else 0
    total_unique_pages = len(set(gsc["page"]).union(set(gsc_ai["page"])))
    overlap_pct_pages = (
        len(overlap) / total_unique_pages * 100 if total_unique_pages else 0
    )

    # Fusion (full outer join)
    merged = pd.merge(
        gsc,
        gsc_ai[["page", "ai_impressions", "ai_impression_share"]],
        on="page",
        how="outer",
    )
    fill_cols = [
        "gsc_clicks", "gsc_impressions", "gsc_ctr", "gsc_position",
        "gsc_impression_share", "ai_impressions", "ai_impression_share",
    ]
    for col in fill_cols:
        merged[col] = merged[col].fillna(0)

    merged["in_gsc"] = merged["gsc_impressions"] > 0
    merged["in_gsc_ai"] = merged["ai_impressions"] > 0

    # Seuils zéro-clic
    both = merged["in_gsc"] & merged["in_gsc_ai"]
    clicks_threshold = merged.loc[both, "gsc_clicks"].quantile(clicks_pct)
    ai_threshold = merged.loc[both, "ai_impressions"].quantile(ai_pct)

    # Segmentation
    def assign_segment(r):
        ig, ia = r["in_gsc"], r["in_gsc_ai"]
        if (
            ig and ia
            and r["gsc_clicks"] <= clicks_threshold
            and r["ai_impressions"] >= ai_threshold
        ):
            return "zero_click_ai"
        if ig and ia:
            return "user_ai_signals"
        if ig:
            return "gsc_only"
        if ia:
            return "gsc_ai_only"
        return None

    merged["segment"] = merged.apply(assign_segment, axis=1)
    merged["segment_label"] = merged["segment"].map(
        {
            "user_ai_signals": "Signaux utilisateur & IA (GSC + IA)",
            "gsc_only": "GSC uniquement (BOFU / lacunes techniques ?)",
            "gsc_ai_only": "GSC IA uniquement (TOFU / AI-first ?)",
            "zero_click_ai": "Pages proches du zéro-clic IA",
        }
    )

    # Clustering par segment
    gsc_only_df = merged[merged["segment"] == "gsc_only"].copy()
    gsc_ai_only_df = merged[merged["segment"] == "gsc_ai_only"].copy()

    gsc_only_clustered, gsc_only_chart = run_clustering(gsc_only_df, "gsc_impressions")
    gsc_ai_only_clustered, gsc_ai_only_chart = run_clustering(
        gsc_ai_only_df, "ai_impressions"
    )

    stats = {
        "gsc_file": gsc_file,
        "ai_file": ai_file,
        "total_gsc": total_gsc,
        "total_ai": total_ai,
        "ai_vs_gsc_share": ai_vs_gsc_share,
        "overlap": len(overlap),
        "overlap_pct_pages": overlap_pct_pages,
        "gsc_only_count": len(set(gsc["page"]) - overlap),
        "ai_only_count": len(set(gsc_ai["page"]) - overlap),
        "clicks_threshold": clicks_threshold,
        "ai_threshold": ai_threshold,
        "zero_click_count": int((merged["segment"] == "zero_click_ai").sum()),
        "total_pages": len(merged),
    }

    return merged, gsc_only_clustered, gsc_ai_only_clustered, gsc_only_chart, gsc_ai_only_chart, stats


def slim(df: pd.DataFrame, sort_col: str) -> pd.DataFrame:
    """Sélection des colonnes d'export."""
    export_cols = [
        "page", "gsc_clicks", "gsc_impressions",
        "in_gsc", "in_gsc_ai", "segment", "segment_label",
    ]
    cols = [c for c in export_cols if c in df.columns]
    return df[cols].sort_values(sort_col, ascending=False)


# ──────────────────────────────────────────────────────────────────────────────
#  SIDEBAR — UPLOAD + SEUILS
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    uploaded_files = st.file_uploader(
        "Importez vos 2 exports GSC (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Le rapport standard ET le rapport « Fonctionnalités IA ». "
        "La détection du type de fichier est automatique.",
    )

    st.subheader("Seuils de détection")
    clicks_pct = st.slider(
        "Percentile « faible nombre de clics »",
        min_value=0.0,
        max_value=1.0,
        value=0.25,
        step=0.05,
        help="Définit ce qui compte comme peu de clics pour la détection du zéro-clic.",
    )
    ai_pct = st.slider(
        "Percentile « impressions IA élevées »",
        min_value=0.0,
        max_value=1.0,
        value=0.75,
        step=0.05,
        help="Définit ce qui compte comme un fort volume d'impressions IA.",
    )

    st.divider()
    st.caption(
        "💡 Astuce : exportez depuis **GSC → Performances → Résultats de recherche**, "
        "une fois en standard, une fois en basculant sur « Fonctionnalités IA »."
    )


# ──────────────────────────────────────────────────────────────────────────────
#  CORPS PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
if not uploaded_files or len(uploaded_files) < 2:
    st.info("👈 Importez vos **deux** fichiers d'export GSC dans la barre latérale pour démarrer.")
    st.stop()

# Conversion en dict de bytes (clé cachable)
file_bytes_map = {f.name: f.getvalue() for f in uploaded_files}

try:
    with st.spinner("Traitement, fusion et clustering en cours…"):
        (
            merged,
            gsc_only_clustered,
            gsc_ai_only_clustered,
            gsc_only_chart,
            gsc_ai_only_chart,
            stats,
        ) = build_dataset(file_bytes_map, clicks_pct, ai_pct)
except Exception as exc:  # noqa: BLE001
    st.error(
        f"Erreur lors du traitement : {exc}\n\n"
        "Vérifiez que les deux fichiers contiennent bien une feuille « Pages »."
    )
    st.stop()

st.success(
    f"Détecté → **Standard** : `{stats['gsc_file']}` · **IA** : `{stats['ai_file']}`"
)

# ── MÉTRIQUES ─────────────────────────────────────────────────────────────────
st.subheader("Synthèse des parts d'impressions")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Impressions GSC", f"{stats['total_gsc']:,.0f}".replace(",", " "))
c2.metric("Impressions GSC IA", f"{stats['total_ai']:,.0f}".replace(",", " "))
c3.metric("Part IA vs GSC", f"{stats['ai_vs_gsc_share']:.1f} %")
c4.metric(
    "Pages communes",
    f"{stats['overlap']:,}".replace(",", " "),
    f"{stats['overlap_pct_pages']:.1f} % du total",
)

c5, c6, c7 = st.columns(3)
c5.metric("Pages GSC uniquement", f"{stats['gsc_only_count']:,}".replace(",", " "))
c6.metric("Pages IA uniquement", f"{stats['ai_only_count']:,}".replace(",", " "))
c7.metric(
    "Pages proches du zéro-clic",
    f"{stats['zero_click_count']:,}".replace(",", " "),
    f"{stats['zero_click_count'] / stats['total_pages'] * 100:.1f} % du total",
)

st.divider()

# ── GRAPHIQUES + DONNÉES PAR ONGLETS ──────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(
    ["📈 GSC uniquement", "🤖 GSC IA uniquement", "📋 Toutes les données"]
)

with tab1:
    st.markdown("#### Pages GSC absentes des fonctionnalités IA")
    if not gsc_only_chart.empty:
        fig_gsc = px.bar(
            gsc_only_chart.head(25),
            x="impressions",
            y="category",
            orientation="h",
            labels={"impressions": "Impressions GSC", "category": "Catégorie"},
            color="impressions",
            color_continuous_scale="Blues",
            text="impressions",
        )
        fig_gsc.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_gsc.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            height=600,
        )
        st.plotly_chart(fig_gsc, use_container_width=True)
    else:
        st.warning("Aucune page dans ce segment.")

with tab2:
    st.markdown("#### Pages GSC présentes uniquement dans les fonctionnalités IA")
    if not gsc_ai_only_chart.empty:
        fig_ai = px.bar(
            gsc_ai_only_chart.head(25),
            x="impressions",
            y="category",
            orientation="h",
            labels={"impressions": "Impressions IA", "category": "Catégorie"},
            color="impressions",
            color_continuous_scale="Oranges",
            text="impressions",
        )
        fig_ai.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig_ai.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            height=600,
        )
        st.plotly_chart(fig_ai, use_container_width=True)
    else:
        st.warning("Aucune page dans ce segment.")

with tab3:
    st.markdown("#### Jeu de données fusionné complet")
    seg_filter = st.multiselect(
        "Filtrer par segment",
        options=merged["segment_label"].dropna().unique().tolist(),
        default=merged["segment_label"].dropna().unique().tolist(),
    )
    filtered = merged[merged["segment_label"].isin(seg_filter)]
    st.dataframe(
        filtered[
            ["page", "gsc_clicks", "gsc_impressions", "ai_impressions",
             "in_gsc", "in_gsc_ai", "segment_label"]
        ].sort_values("gsc_impressions", ascending=False),
        use_container_width=True,
        height=500,
    )

st.divider()

# ── TÉLÉCHARGEMENTS ───────────────────────────────────────────────────────────
st.subheader("⬇️ Exports CSV")

exports = {
    "gsc_ai_all_pages.csv": slim(merged, "gsc_impressions"),
    "gsc_ai_user_ai_signals.csv": slim(
        merged[merged["segment"] == "user_ai_signals"], "gsc_impressions"
    ),
    "gsc_ai_gsc_only.csv": slim(gsc_only_clustered, "gsc_impressions"),
    "gsc_ai_ai_only.csv": slim(gsc_ai_only_clustered, "gsc_impressions"),
    "gsc_ai_zero_click.csv": slim(
        merged[merged["segment"] == "zero_click_ai"], "gsc_impressions"
    ),
}

dl_cols = st.columns(len(exports))
for col, (filename, df) in zip(dl_cols, exports.items()):
    col.download_button(
        label=f"📄 {filename}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )
