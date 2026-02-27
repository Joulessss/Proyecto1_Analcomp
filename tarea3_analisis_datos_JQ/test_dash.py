"""
Mapa a la izquierda; panel derecho con 4 pestañas:
1) Distribución (histograma del indicador)
2) Ranking (barras horizontales; brecha usa Top 12)
3) Box/Violin (toggle Inglés/Global)
4) ECDF (toggle Inglés/Global)
"""
import json, re, unicodedata, importlib.util
import pandas as pd
import folium
import branca.colormap as cm
import plotly.express as px
from dash import Dash, dcc, html, Input, Output

LABEL_BILI = {"S": "Bilingüe", "N": "No bilingüe"}
ORDER_BILI = ["No bilingüe", "Bilingüe"]
COLOR_MAP = {"Bilingüe": "#1A6B5A", "No bilingüe": "#C4783B"}
HAS_SM = importlib.util.find_spec("statsmodels") is not None

datos = pd.read_csv("DataAWS.csv")


def norm_text(x):
    if pd.isna(x):
        return ""
    x = str(x).upper().strip()
    x = "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn")
    x = re.sub(r"[^A-Z ]", " ", x)
    return re.sub(r"\s+", " ", x).strip()


def build_agg(df: pd.DataFrame) -> pd.DataFrame:
    dg = df[["cole_mcpio_ubicacion", "cole_bilingue", "punt_ingles"]].dropna().copy()
    dg["muni_key"] = dg["cole_mcpio_ubicacion"].map(norm_text)
    dg["bili_flag"] = dg["cole_bilingue"].map({"S": 1, "N": 0})
    rows = []
    for muni, grp in dg.groupby("muni_key"):
        vals = grp["punt_ingles"]
        mean_all = vals.mean()
        s_vals = vals[grp["cole_bilingue"] == "S"]
        n_vals = vals[grp["cole_bilingue"] == "N"]
        gap = s_vals.mean() - n_vals.mean() if len(s_vals) and len(n_vals) else 0
        rows.append({
            "muni_key": muni,
            "mean_all": mean_all,
            "gap_ing": gap,
            "pct_bilingue": 100 * grp["bili_flag"].mean(),
            "n_total": len(vals),
        })
    agg = pd.DataFrame(rows).set_index("muni_key").fillna(0)
    # conteos extremos
    sc = df[["cole_mcpio_ubicacion", "punt_ingles"]].dropna().copy()
    sc["muni_key"] = sc["cole_mcpio_ubicacion"].map(norm_text)
    agg["cnt_gt85"] = agg.index.map(sc[sc["punt_ingles"] > 85].groupby("muni_key").size()).fillna(0).astype(int)
    agg["cnt_lt10"] = agg.index.map(sc[sc["punt_ingles"] < 10].groupby("muni_key").size()).fillna(0).astype(int)
    return agg.round(2)


agg_muni = build_agg(datos)
df_base = datos[["cole_bilingue", "punt_ingles", "punt_global"]].dropna().copy()
df_base["Tipo"] = df_base["cole_bilingue"].map(LABEL_BILI)
# Carácter en scatter (si existe)
df_base["Caracter"] = datos.get("caracter_lbl", datos.get("cole_caracter", pd.Series(index=df_base.index)))
df_base["Caracter"] = df_base["Caracter"].reindex(df_base.index).fillna("No reporta")

MAP_OPTIONS = {
    "mean_all": "Promedio puntaje inglés",
    "gap_ing": "Brecha bilingüe (S - N)",
    "cnt_gt85": "# estudiantes >85",
    "cnt_lt10": "# estudiantes <10",
}


def build_folium_html(metric: str) -> str:
    metric = metric if metric in agg_muni.columns else "mean_all"
    label = MAP_OPTIONS.get(metric, metric)
    with open("boyaca_geojson_123_municipios.geojson", encoding="utf-8") as f:
        geo = json.load(f)
    for ft in geo["features"]:
        key = norm_text(ft["properties"].get("MPIO_CNMBR", ""))
        if key in agg_muni.index:
            for col, val in agg_muni.loc[key].items():
                ft["properties"][col] = float(val)
        else:
            for col in agg_muni.columns:
                ft["properties"][col] = 0.0
    vmin, vmax = agg_muni[metric].min(), agg_muni[metric].max()
    if vmin == vmax:
        vmax = vmin + 1
    cmap = cm.linear.RdBu_11.scale(vmin, vmax) if metric == "gap_ing" else cm.linear.YlGnBu_09.scale(vmin, vmax)
    m = folium.Map(location=[5.6, -73.0], zoom_start=8, tiles="CartoDB positron")
    folium.GeoJson(
        geo,
        name=label,
        style_function=lambda ft: {
            "fillColor": cmap(ft["properties"].get(metric, 0)),
            "color": "#1f2937",
            "weight": 0.35,
            "fillOpacity": 0.85,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["MPIO_CNMBR", metric],
            aliases=["Municipio:", label],
            localize=True,
        ),
    ).add_to(m)
    cmap.add_to(m)
    return m.get_root().render()


# ---------- Figures ----------
def fig_hist(metric: str):
    label = MAP_OPTIONS.get(metric, metric)
    df = agg_muni.reset_index()
    if metric not in df.columns:
        metric, label = "mean_all", MAP_OPTIONS["mean_all"]
    fig = px.histogram(df, x=metric, nbins=22, opacity=0.85,
                       labels={metric: label},
                       title=f"Distribución municipal · {label}")
    fig.update_traces(marker_line_color="white", marker_line_width=0.5)
    fig.add_vline(x=df[metric].mean(), line_dash="dash", line_width=1.8,
                  annotation_text=f"Media dept.: {df[metric].mean():.1f}",
                  annotation_font=dict(size=10))
    fig.update_layout(template="plotly_white")
    return fig


def fig_bar_top(metric: str):
    label = MAP_OPTIONS.get(metric, metric)
    df = agg_muni.reset_index()
    if metric not in df.columns:
        metric, label = "mean_all", MAP_OPTIONS["mean_all"]
    if metric == "gap_ing":
        df = df[df["gap_ing"] > 0]
    top_n = 12 if metric == "gap_ing" else 10
    top = df.sort_values(metric, ascending=False).head(top_n)
    title = "Top 12 municipios · Mayor brecha bilingüe" if metric == "gap_ing" else f"Top {top_n} municipios · Mayor {label}"
    fig = px.bar(top, x=metric, y="muni_key",
                 labels={"muni_key": "Municipio", metric: label},
                 title=title,
                 text_auto=".1f",
                 orientation="h",
                 color_discrete_sequence=["#1A6B5A"])
    fig.update_traces(marker_line_color="white", marker_line_width=0.4,
                      textfont_size=9, textposition="outside")
    fig.update_layout(yaxis_categoryorder="total ascending", template="plotly_white")
    return fig


def fig_box_violin(col: str, label: str):
    fig_box = px.box(df_base, x="Tipo", y=col, color="Tipo",
                     category_orders={"Tipo": ORDER_BILI},
                     points="outliers",
                     labels={"Tipo": "", col: label},
                     title=f"Boxplot {label}")
    fig_box.update_traces(jitter=0.3, marker_opacity=0.2, marker_size=3, boxmean="sd")
    fig_box.update_layout(template="plotly_white")

    fig_vio = px.violin(df_base, x="Tipo", y=col, color="Tipo",
                        category_orders={"Tipo": ORDER_BILI},
                        box=True, points=False,
                        labels={"Tipo": "", col: label},
                        title=f"Violin {label}")
    fig_vio.update_layout(template="plotly_white")
    return fig_box, fig_vio


def fig_ecdf(col: str, label: str):
    fig = px.ecdf(
        df_base[["Tipo", col]], x=col, color="Tipo",
        color_discrete_map=COLOR_MAP, category_orders={"Tipo": ORDER_BILI},
        labels={col: label, "Tipo": ""},
        title=f"ECDF {label} · Bilingüe vs No"
    )
    fig.update_layout(template="plotly_white")
    return fig


fig_box_ing, fig_vio_ing = fig_box_violin("punt_ingles", "Puntaje Inglés")
fig_box_glob, fig_vio_glob = fig_box_violin("punt_global", "Puntaje Global")
fig_ecdf_ing = fig_ecdf("punt_ingles", "Puntaje Inglés")
fig_ecdf_glob = fig_ecdf("punt_global", "Puntaje Global")

def fig_scatter_filtered(thresh_low=None, thresh_high=None):
    df_s = df_base.copy()
    if thresh_high is not None:
        df_s = df_s[df_s["punt_ingles"] > thresh_high]
    if thresh_low is not None:
        df_s = df_s[df_s["punt_ingles"] < thresh_low]
    df_s = df_s.sample(min(len(df_s), 6000), random_state=42) if len(df_s) > 6000 else df_s
    fig = px.scatter(
        df_s,
        x="punt_ingles", y="punt_ingles",  # ambos ejes puntaje inglés
        color="Caracter",            # color distingue carácter (Acad/Téc/Téc-Acad/No reporta)
        symbol="cole_bilingue",      # forma distingue bilingüe S/N
        opacity=0.55,
        labels={
            "punt_ingles": "Puntaje Inglés",
            "cole_bilingue": "Bilingüe",
            "Caracter": "Carácter",
        },
        title="Puntaje Inglés · color por carácter, forma por bilingüe",
    )
    fig.update_traces(selector=dict(mode="markers"), marker_size=8)
    symbol_map = {"S": "diamond", "N": "circle-open"}
    for bili, sym in symbol_map.items():
        fig.update_traces(marker_symbol=sym, selector=dict(symbol=bili))
    fig.update_layout(template="plotly_white", yaxis_title="Puntaje Inglés", showlegend=True)
    return fig

# ---------- Rangos (para >85 / <10) ----------
bins = [0, 30, 50, 70, 85, 101]
labels = ["0-30", "31-50", "51-70", "71-85", "85+"]
df_desemp = datos[["cole_bilingue", "punt_ingles"]].dropna().copy()
df_desemp["Tipo"] = df_desemp["cole_bilingue"].map(LABEL_BILI)
df_desemp["rango_ing"] = pd.cut(df_desemp["punt_ingles"], bins=bins, labels=labels, right=True, include_lowest=True)
pivot = df_desemp.groupby(["Tipo", "rango_ing"]).size().reset_index(name="n")
pivot["pct"] = 100 * pivot["n"] / pivot.groupby("Tipo")["n"].transform("sum")
fig_rangos = px.bar(
    pivot,
    x="Tipo", y="pct", color="rango_ing",
    category_orders={"Tipo": ORDER_BILI, "rango_ing": labels},
    barmode="stack", text_auto=".1f",
    labels={"Tipo": "", "pct": "% de estudiantes", "rango_ing": "Rango puntaje inglés"},
    title="Distribución por rangos de puntaje de inglés",
)
fig_rangos.update_traces(textfont_size=9, textposition="inside")
fig_rangos.update_layout(template="plotly_white")

# ---------------- Layout -----------------
app = Dash(__name__)
app.layout = html.Div(style={"display": "flex", "height": "100vh", "fontFamily": "Georgia"}, children=[
    html.Div(style={"flex": "0 0 55%", "padding": "10px"}, children=[
        html.H4("Mapa municipal", style={"marginBottom": "6px"}),
        dcc.Dropdown(
            id="map-select",
            options=[{"label": lbl, "value": key} for key, lbl in MAP_OPTIONS.items()],
            value="mean_all",
            clearable=False,
            style={"marginBottom": "8px"},
        ),
        html.Iframe(id="map-frame", style={"width": "100%", "height": "90vh", "border": "none"}),
    ]),
    html.Div(style={"flex": "1", "padding": "10px", "overflowY": "auto"}, children=[
        html.H4("Panel relacionado", style={"marginBottom": "8px"}),
        dcc.Tabs(id="tabs", value="tab-dist", children=[
            dcc.Tab(label="Distribución", value="tab-dist", children=[
                dcc.Graph(id="hist-related", style={"height": "42vh"}),
            ]),
            dcc.Tab(label="Ranking", value="tab-top", children=[
                dcc.Graph(id="bar-related", style={"height": "42vh"}),
            ]),
            dcc.Tab(label="Box / Violin", value="tab-box", children=[
                dcc.RadioItems(
                    id="score-radio",
                    options=[{"label": " Puntaje Inglés", "value": "ing"},
                             {"label": " Puntaje Global", "value": "glob"}],
                    value="ing",
                    inline=True,
                    labelStyle={"marginRight": "12px"}
                ),
                dcc.Graph(id="box-fig", style={"height": "36vh"}),
                dcc.Graph(id="vio-fig", style={"height": "36vh"}),
            ]),
            dcc.Tab(label="ECDF", value="tab-ecdf", children=[
                dcc.RadioItems(
                    id="score-radio-ecdf",
                    options=[{"label": " Puntaje Inglés", "value": "ing"},
                             {"label": " Puntaje Global", "value": "glob"}],
                    value="ing",
                    inline=True,
                    labelStyle={"marginRight": "12px"}
                ),
                dcc.Graph(id="ecdf-fig", style={"height": "60vh"}),
            ]),
            dcc.Tab(label="Scatter", value="tab-scatter", children=[
                dcc.Graph(id="scatter-fig", style={"height": "60vh"}),
            ]),
        ]),
    ]),
])

# ---------------- Callbacks ----------------
@app.callback(
    Output("map-frame", "srcDoc"),
    Output("hist-related", "figure"),
    Output("bar-related", "figure"),
    Input("map-select", "value"),
)
def update_dashboard(metric):
    metric = metric if metric in MAP_OPTIONS else "mean_all"
    html_map = build_folium_html(metric)
    if metric in ("mean_all", "gap_ing"):
        hist = fig_hist(metric)
        bar = fig_bar_top(metric)
    else:
        hist = fig_rangos
        bar = fig_bar_top(metric)  # mantiene ranking de conteos extremos
    return html_map, hist, bar


@app.callback(
    Output("box-fig", "figure"),
    Output("vio-fig", "figure"),
    Input("score-radio", "value"),
)
def update_box_violin(score):
    if score == "glob":
        return fig_box_glob, fig_vio_glob
    return fig_box_ing, fig_vio_ing


@app.callback(
    Output("ecdf-fig", "figure"),
    Input("score-radio-ecdf", "value"),
)
def update_ecdf(score):
    return fig_ecdf_glob if score == "glob" else fig_ecdf_ing


@app.callback(
    Output("scatter-fig", "figure"),
    Input("map-select", "value"),
)
def update_scatter(metric):
    if metric == "cnt_gt85":
        return fig_scatter_filtered(thresh_high=85)
    if metric == "cnt_lt10":
        return fig_scatter_filtered(thresh_low=10)
    return fig_scatter_filtered()


if __name__ == "__main__":
    app.run(debug=True, port=8050)
