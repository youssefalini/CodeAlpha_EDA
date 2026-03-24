import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Retail Analytics Pro",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Tableau de Bord interactif : Performance Retail")

# ─────────────────────────────────────────────
# NETTOYAGE COMPLET DES DONNÉES
# ─────────────────────────────────────────────
@st.cache_data
def load_and_clean_data():
    df = pd.read_csv('retail_store_inventory_messy.csv')

    # ── 1. DOUBLONS ──────────────────────────
    # Suppression des doublons exacts (50 lignes identiques détectées)
    df = df.drop_duplicates()
    # Suppression des doublons partiels (même date + magasin + produit)
    df = df.drop_duplicates(subset=['Date', 'Store ID', 'Product ID'], keep='first')

    # ── 2. DATES ─────────────────────────────
    # Le fichier contient deux formats : DD/MM/YYYY et YYYY-MM-DD
    # dayfirst=True gère les deux proprement
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    # Suppression des dates futures aberrantes (2024 détectées)
    df = df[df['Date'].dt.year <= 2023]

    # ── 3. CATÉGORIES ────────────────────────
    # Suppression des espaces parasites + harmonisation de la casse
    # "TOYS" → "Toys", " electronics " → "Electronics"
    df['Category'] = df['Category'].str.strip().str.title()

    # ── 4. INVENTORY LEVEL ───────────────────
    # 100 valeurs à -150 détectées → valeur sentinelle d'erreur (≠ vrai stock)
    # Remplacement par la médiane des valeurs positives uniquement
    df['Inventory Level'] = pd.to_numeric(df['Inventory Level'], errors='coerce')
    median_inv = df.loc[df['Inventory Level'] > 0, 'Inventory Level'].median()
    df.loc[df['Inventory Level'] <= 0, 'Inventory Level'] = None
    df['Inventory Level'] = df['Inventory Level'].fillna(median_inv).astype(int)

    # ── 5. PRIX ──────────────────────────────
    # 51 valeurs à -99.99 détectées → valeur sentinelle (≠ vrai prix)
    # Remplacement par la médiane des prix positifs
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
    median_price = df.loc[df['Price'] > 0, 'Price'].median()
    df.loc[df['Price'] <= 0, 'Price'] = None
    df['Price'] = df['Price'].fillna(median_price)

    # ── 6. UNITS SOLD ────────────────────────
    # 252 valeurs manquantes → remplacement par la médiane
    df['Units Sold'] = pd.to_numeric(df['Units Sold'], errors='coerce')
    df['Units Sold'] = df['Units Sold'].fillna(df['Units Sold'].median()).abs().astype(int)

    # ── 7. DEMAND FORECAST ───────────────────
    # 49 valeurs négatives → impossibles, remplacement par la médiane
    df['Demand Forecast'] = pd.to_numeric(df['Demand Forecast'], errors='coerce')
    median_forecast = df.loc[df['Demand Forecast'] > 0, 'Demand Forecast'].median()
    df.loc[df['Demand Forecast'] < 0, 'Demand Forecast'] = None
    df['Demand Forecast'] = df['Demand Forecast'].fillna(median_forecast)

    # ── 8. COMPETITOR PRICING ────────────────
    df['Competitor Pricing'] = pd.to_numeric(df['Competitor Pricing'], errors='coerce')
    df['Competitor Pricing'] = df['Competitor Pricing'].fillna(df['Competitor Pricing'].median())

    # ── 9. MÉTRIQUES CALCULÉES ───────────────
    df['Revenue'] = df['Price'] * df['Units Sold']

    # Stock restant : maintenant fiable car Inventory Level est propre
    # Les cas où Units Sold > Inventory Level après nettoyage sont rares
    # et représentent de vraies ruptures → on garde clip(lower=0)
    df['Stock_Restant'] = (df['Inventory Level'] - df['Units Sold']).clip(lower=0).astype(int)

    # Indicateur de rupture
    df['Statut_Stock'] = df['Stock_Restant'].apply(
        lambda x: '🔴 Rupture' if x < 10 else ('🟡 Critique' if x < 20 else '🟢 OK')
    )

    # Avantage concurrentiel sur le prix
    df['Prix_Avantage'] = df['Competitor Pricing'] - df['Price']

    return df


df = load_and_clean_data()

# ─────────────────────────────────────────────
# SIDEBAR — FILTRES
# ─────────────────────────────────────────────
st.sidebar.header("Filtres 🔎")

region_filter = st.sidebar.multiselect(
    "Région :",
    options=sorted(df['Region'].unique()),
    default=sorted(df['Region'].unique())
)

category_filter = st.sidebar.multiselect(
    "Catégorie :",
    options=sorted(df['Category'].unique()),
    default=sorted(df['Category'].unique())
)

# Filtre par année si la colonne Date est disponible
years = sorted(df['Date'].dt.year.dropna().unique().astype(int))
year_filter = st.sidebar.multiselect(
    "Année :",
    options=years,
    default=years
)

df_filtered = df[
    (df['Region'].isin(region_filter)) &
    (df['Category'].isin(category_filter)) &
    (df['Date'].dt.year.isin(year_filter))
]

# ─────────────────────────────────────────────
# KPI — INDICATEURS CLÉS
# ─────────────────────────────────────────────
st.subheader("📈 Indicateurs Clés de Performance")

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    "💰 Chiffre d'Affaires",
    f"{df_filtered['Revenue'].sum():,.0f} $"
)
col2.metric(
    "📦 Unités Vendues",
    f"{df_filtered['Units Sold'].sum():,.0f}"
)
col3.metric(
    "🏷️ Remise Moyenne",
    f"{df_filtered['Discount'].mean():.1f} %"
)
col4.metric(
    "⚠️ Stocks Critiques (< 20)",
    len(df_filtered[df_filtered['Stock_Restant'] < 20])
)
col5.metric(
    "🔴 Ruptures (< 10)",
    len(df_filtered[df_filtered['Stock_Restant'] < 10])
)

st.divider()

# ─────────────────────────────────────────────
# GRAPHIQUES — LIGNE 1
# ─────────────────────────────────────────────
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Ventes par Catégorie")
    fig_cat = px.bar(
        df_filtered.groupby('Category', as_index=False)['Units Sold'].sum(),
        x='Category', y='Units Sold',
        color='Category',
        template='plotly_white',
        text_auto=True
    )
    fig_cat.update_traces(textposition='outside')
    st.plotly_chart(fig_cat, use_container_width=True)

with col_g2:
    st.subheader("Chiffre d'Affaires par Région")
    fig_region = px.pie(
        df_filtered.groupby('Region', as_index=False)['Revenue'].sum(),
        names='Region', values='Revenue',
        template='plotly_white',
        hole=0.4
    )
    st.plotly_chart(fig_region, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────
# GRAPHIQUES — LIGNE 2
# ─────────────────────────────────────────────
col_g3, col_g4 = st.columns(2)

with col_g3:
    st.subheader("Impact des Promotions sur le Revenue")
    fig_promo = px.box(
        df_filtered,
        x='Holiday/Promotion', y='Revenue',
        color='Holiday/Promotion',
        template='plotly_white',
        labels={'Holiday/Promotion': 'Promotion (0=Non, 1=Oui)'}
    )
    st.plotly_chart(fig_promo, use_container_width=True)

with col_g4:
    st.subheader("Évolution mensuelle des ventes")
    df_monthly = (
        df_filtered
        .assign(Mois=df_filtered['Date'].dt.to_period('M').astype(str))
        .groupby('Mois', as_index=False)['Units Sold'].sum()
        .sort_values('Mois')
    )
    fig_trend = px.line(
        df_monthly, x='Mois', y='Units Sold',
        template='plotly_white', markers=True
    )
    fig_trend.update_xaxes(tickangle=45)
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────
# GRAPHIQUES — LIGNE 3
# ─────────────────────────────────────────────
col_g5, col_g6 = st.columns(2)

with col_g5:
    st.subheader("Distribution des Stocks Restants")
    fig_stock = px.histogram(
        df_filtered, x='Stock_Restant',
        nbins=40, template='plotly_white',
        color_discrete_sequence=['#636EFA']
    )
    fig_stock.add_vline(x=10, line_dash="dash", line_color="red",
                        annotation_text="Seuil rupture (10)")
    fig_stock.add_vline(x=20, line_dash="dash", line_color="orange",
                        annotation_text="Seuil critique (20)")
    st.plotly_chart(fig_stock, use_container_width=True)

with col_g6:
    st.subheader("Avantage Prix vs Concurrent (par catégorie)")
    df_prix = df_filtered.groupby('Category', as_index=False)['Prix_Avantage'].mean()
    df_prix['Couleur'] = df_prix['Prix_Avantage'].apply(
        lambda x: 'Avantage' if x > 0 else 'Désavantage'
    )
    fig_prix = px.bar(
        df_prix, x='Category', y='Prix_Avantage',
        color='Couleur',
        color_discrete_map={'Avantage': '#00CC96', 'Désavantage': '#EF553B'},
        template='plotly_white',
        labels={'Prix_Avantage': 'Écart moyen ($)', 'Category': 'Catégorie'}
    )
    fig_prix.add_hline(y=0, line_color='gray', line_width=1)
    st.plotly_chart(fig_prix, use_container_width=True)

st.divider()

# ─────────────────────────────────────────────
# TABLEAUX
# ─────────────────────────────────────────────
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("📋 Aperçu de l'inventaire global")
    cols_inv = ['Product ID', 'Category', 'Region', 'Inventory Level',
                'Units Sold', 'Stock_Restant', 'Statut_Stock']
    st.dataframe(
        df_filtered[cols_inv].head(50),
        use_container_width=True,
        hide_index=True
    )

with col_t2:
    st.subheader("🚨 Audit des stocks critiques (< 20)")
    critiques = df_filtered[df_filtered['Stock_Restant'] < 20][
        ['Product ID', 'Category', 'Region', 'Inventory Level',
         'Units Sold', 'Stock_Restant', 'Statut_Stock']
    ].sort_values(by='Stock_Restant')

    if critiques.empty:
        st.success("✅ Aucun produit en stock critique avec les filtres actuels.")
    else:
        st.dataframe(critiques, use_container_width=True, hide_index=True)
        st.caption(f"⚠️ {len(critiques)} produit(s) nécessitent un réapprovisionnement")

st.divider()

# ─────────────────────────────────────────────
# SECTION QUALITÉ DES DONNÉES (transparence)
# ─────────────────────────────────────────────
with st.expander("🔬 Rapport de qualité des données (après nettoyage)"):
    st.markdown("""
    ### Corrections appliquées au chargement

    | Anomalie détectée | Nombre de lignes | Traitement appliqué |
    |---|---|---|
    | `Inventory Level` à -150 (valeur sentinelle) | ~100 | Remplacé par la **médiane** des valeurs positives |
    | `Price` à -99.99 (valeur sentinelle) | ~51 | Remplacé par la **médiane** des prix positifs |
    | `Demand Forecast` négatif | ~49 | Remplacé par la **médiane** des prévisions positives |
    | `Units Sold` manquant | ~252 | Remplacé par la **médiane** |
    | `Price` manquant | ~248 | Remplacé par la **médiane** |
    | Doublons exacts | 50 | Supprimés |
    | Doublons partiels (Date + Store + Product) | 100 | Premier enregistrement conservé |
    | Formats de date mixtes (DD/MM/YYYY / YYYY-MM-DD) | ~20% | Normalisés avec `dayfirst=True` |
    | Catégories mal formatées ("TOYS", " electronics ") | 2 catégories | Normalisées avec `.strip().title()` |
    | Dates futures (2024) | 2 | Supprimées |
    """)

    col_q1, col_q2, col_q3 = st.columns(3)
    col_q1.metric("Lignes brutes", "5 050")
    col_q2.metric("Lignes après nettoyage", f"{len(df):,}")
    col_q3.metric("Lignes supprimées", f"{5050 - len(df):,}")