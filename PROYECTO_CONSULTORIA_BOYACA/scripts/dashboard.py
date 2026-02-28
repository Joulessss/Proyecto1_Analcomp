import pandas as pd
import numpy as np
import json
import unicodedata
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State
import scipy.stats as stats
import warnings
from app_instance import app          
import tab1_bilingue                  
from tab1_bilingue import tab1_content
import tab2_csociales
import urllib3
from urllib3.exceptions import NotOpenSSLWarning

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.NotOpenSSLWarning)

#cargar datos ────────────────────────────────────────────────────────────────────────
Data = pd.read_csv('PROYECTO_CONSULTORIA_BOYACA/data/cleaned_data.csv')

cols_used = ['cole_area_ubicacion', 'cole_caracter','cole_naturaleza','cole_jornada', #barplots apilados y donas y geograficos
             'cole_mcpio_ubicacion', 'cole_nombre_establecimiento',                          
             'punt_matematicas','punt_c_naturales'] # histograma kde

Data_used = Data[cols_used].copy()
Data_used['punt_prom_mcn'] = (Data_used['punt_matematicas'] + Data_used['punt_c_naturales'])/2

with open('PROYECTO_CONSULTORIA_BOYACA/data/gadm41_COL_2.json', 'r', encoding='utf-8') as f:
    geojson_data = json.load(f)
    
with open('PROYECTO_CONSULTORIA_BOYACA/data/gadm41_COL_1.json', 'r', encoding='utf-8') as f:
    geojson_dpto = json.load(f)
    

#Funciones secundarias Datos ────────────────────────────────────────────────────────────────────────
def normalizar(name):
    name = name.lower().strip()
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = name.replace(' ', '')
    name = name.replace('cienega', 'cienaga')
    name = name.replace('guicandelasierra', 'guican')
    name = name.replace('pisva', 'pisba')
    name = name.replace('tutasa', 'tutaza')
    return name    

# creacion vars ────────────────────────────────────────────────────────────────────────
boyaca_dpto = next(f for f in geojson_dpto['features'] if normalizar(f['properties']['NAME_1']) == 'boyaca')            
todos_municipios = Data_used['cole_mcpio_ubicacion'].dropna().unique().tolist()

mapa_norm_a_real = {}
for m in todos_municipios:
    norm = normalizar(m)
    if norm not in mapa_norm_a_real:
        mapa_norm_a_real[norm] = m
    else:
        existente = mapa_norm_a_real[norm]
        count_nuevo = len(Data_used[Data_used['cole_mcpio_ubicacion'] == m])
        count_existente = len(Data_used[Data_used['cole_mcpio_ubicacion'] == existente])
        if count_nuevo > count_existente:
            mapa_norm_a_real[norm] = m

geos_coinc = [feature for feature in geojson_data['features'][212:335] if normalizar(feature['properties']['NAME_2']) in mapa_norm_a_real]
filt_geojson = {"type": "FeatureCollection", "features": geos_coinc}

for i, feature in enumerate(filt_geojson['features']): feature['id'] = i

plot_df = pd.DataFrame([{"id": i, "name": f['properties']['NAME_2'], "nombre_real": mapa_norm_a_real.get(normalizar(f['properties']['NAME_2']))} for i, f in enumerate(filt_geojson['features'])])

coords_centr = geos_coinc[0]['geometry']['coordinates'][0][0][0]
latids_bordes, longs_bordes = [], []
geom = boyaca_dpto['geometry']
polys = geom['coordinates'] if geom['type'] == 'Polygon' else geom['coordinates']
for poly in polys:
    ring = poly[0]
    longs_bordes.extend([p[0] for p in ring] + [None])
    latids_bordes.extend([p[1] for p in ring] + [None])

plot_df['nombre_real'] = plot_df['name'].apply(
    lambda x: mapa_norm_a_real.get(normalizar(x))
)

vars_cat = {
    'Sin filtro': None,
    'Área de Ubicación': 'cole_area_ubicacion',
    'Naturaleza': 'cole_naturaleza',
    'Jornada': 'cole_jornada',
    'Carácter': 'cole_caracter'
}

puntajes = {
    'Matemáticas': 'punt_matematicas',
    'Ciencias Naturales': 'punt_c_naturales',
    'Promedio Mates y Cienc. Nat.': 'punt_prom_mcn'
}

# Funciones secundarias plot ────────────────────────────────────────────────────────────────────────
def format_hover(r):
    nombre = r['cole_mcpio_ubicacion'] if pd.notna(r.get('cole_mcpio_ubicacion')) else r['name']
    promedio = f"{r['promedio']:.1f}" if pd.notna(r.get('promedio')) else 'N/D'
    colegios = int(r['num_colegios']) if pd.notna(r.get('num_colegios')) else 'N/D'
    estudiantes = int(r['num_estudiantes']) if pd.notna(r.get('num_estudiantes')) else 'N/D'
    return (f"<b>{nombre}</b><br>"
            f"Puntaje promedio: {promedio}<br>"
            f"N° Colegios: {colegios}<br>"
            f"N° Estudiantes: {estudiantes}")
    
def agrup_municp(df, col_puntaje, col_cat=None, cat_valor=None):
    df = df.copy()
    df['cole_mcpio_ubicacion'] = df['cole_mcpio_ubicacion'].map(
        lambda x: mapa_norm_a_real.get(normalizar(x), x)
    )
    if col_cat and cat_valor:
        df = df[df[col_cat] == cat_valor]
    agg = df.groupby('cole_mcpio_ubicacion').agg(
        promedio = (col_puntaje, 'mean'),
        num_colegios = ('cole_nombre_establecimiento', 'nunique'),
        num_estudiantes = (col_puntaje, 'count')
    ).reset_index()
    agg['mcpio_norm'] = agg['cole_mcpio_ubicacion'].apply(normalizar)
    return agg    


def datos_trazar(punt_col, col_cat=None, cat_valor=None):
    agg = agrup_municp(Data_used, punt_col, col_cat, cat_valor)
    
    munic_df = plot_df.copy()
    munic_df['name_norm'] = munic_df['name'].apply(normalizar)
    munic_df = munic_df.merge(agg, left_on='name_norm', right_on='mcpio_norm', how='left')

    def hover(r):
        nombre = r['nombre_real'] if pd.notna(r.get('nombre_real')) else r['name']
        promedio = f"{r['promedio']:.1f}" if pd.notna(r.get('promedio')) else 'N/D'
        colegios = int(r['num_colegios']) if pd.notna(r.get('num_colegios')) else 'N/D'
        estudiantes = int(r['num_estudiantes']) if pd.notna(r.get('num_estudiantes')) else 'N/D'
        return (f"<b>{nombre}</b><br>"
                f"Puntaje promedio: {promedio}<br>"
                f"N° Colegios: {colegios}<br>"
                f"N° Estudiantes: {estudiantes}")

    munic_df['hover'] = munic_df.apply(hover, axis=1)
    return munic_df['promedio'].tolist(), munic_df['hover'].tolist(), plot_df['nombre_real'].tolist()

# estilos ────────────────────────────────────────────────────────────────────────

COLORS = {
    'primary': '#003876',
    'secondary':  '#009640',
    'accent': '#E8B400',
    'background': '#F0F4F8',
    'surface': '#FFFFFF',
    'text': '#1A2B3C',
    'muted': '#6B7C93',
    'border': '#DDE3EA',
}

CARD_STYLE = {
    'backgroundColor': COLORS['surface'],
    'borderRadius': '12px',
    'padding': '24px',
    'boxShadow': '0 2px 12px rgba(0,0,0,0.06)',
    'border': f'1px solid {COLORS["border"]}',
    'marginBottom': '20px',
}

LABEL_STYLE = {
    'fontSize': '11px',
    'fontWeight': '700',
    'letterSpacing': '0.08em',
    'color': COLORS['muted'],
    'textTransform': 'uppercase',
    'marginBottom': '6px',
    'display': 'block',
}

DROPDOWN_STYLE = {
    'fontSize': '13px',
    'borderRadius': '8px',
    'border': f'1px solid {COLORS["border"]}',
}

tab_base = {
    'padding': '14px 28px',
    'fontFamily': '"Segoe UI", sans-serif',
    'fontWeight': '600',
    'fontSize': '13px',
    'letterSpacing': '0.04em',
    'color': COLORS['muted'],
    'backgroundColor': COLORS['background'],
    'border': 'none',
    'borderBottom': f'2px solid {COLORS["border"]}',
}

tab_selected = {
    **tab_base,
    'color': COLORS['primary'],
    'backgroundColor': COLORS['surface'],
    'borderBottom': f'3px solid {COLORS["secondary"]}',
}

# helperslayout ────────────────────────────────────────────────────────────────────────
def make_kpi(label, value, icon='📊', color=COLORS['primary']):
    return html.Div([
        html.Div(icon, style={'fontSize': '28px', 'marginBottom': '8px'}),
        html.Div(value, style={
            'fontSize': '26px', 'fontWeight': '800',
            'color': color, 'lineHeight': '1',
        }),
        html.Div(label, style={
            'fontSize': '11px', 'color': COLORS['muted'],
            'fontWeight': '600', 'letterSpacing': '0.06em',
            'textTransform': 'uppercase', 'marginTop': '6px',
        }),
    ], style={
        **CARD_STYLE,
        'textAlign': 'center',
        'padding': '20px 16px',
        'flex': '1',
        'marginBottom': '0',
        'borderTop': f'4px solid {color}',
    })


def seccion_pregunta(numero, titulo, descripcion):
    return html.Div([
        html.Div([
            html.Span(f"Pregunta {numero}", style={
                'backgroundColor': COLORS['secondary'],
                'color': 'white',
                'fontSize': '11px',
                'fontWeight': '700',
                'letterSpacing': '0.08em',
                'padding': '4px 12px',
                'borderRadius': '20px',
                'textTransform': 'uppercase',
            }),
            html.H3(titulo, style={
                'color': COLORS['primary'],
                'fontWeight': '800',
                'fontSize': '20px',
                'margin': '12px 0 8px',
            }),
            html.P(descripcion, style={
                'color': COLORS['text'],
                'fontSize': '15px',
                'lineHeight': '1.7',
                'margin': '0',
            }),
        ], style={
            **CARD_STYLE,
            'borderLeft': f'5px solid {COLORS["secondary"]}',
        })
    ])

# ────────────────────────────────────────────────────────────────────────
# contenido tabs ─────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────


# tab pregunta 3 ─────────────────────────────────────────────────────────────
def tab3_content():
    return html.Div([

        seccion_pregunta(
            3,
            "Vocación Científica y Entornos Académicos",
            "La Gobernación de Boyacá necesita conocer ¿qué tipos de entornos académicos dentro del "
            "departamento de Boyacá presentan menor desempeño en Matemáticas y Ciencias Naturales según "
            "Saber 11, y dónde tendría mayor impacto una campaña de motivación hacia la investigación "
            "científica como estrategia para fortalecer competencias en cuestión."
        ),

        html.Div(id='tab3-kpis', style={'display': 'flex', 'gap': '16px', 'marginBottom': '20px'}),

        
        # fila 1 — Mapa - rankingimpacto ─────────────────────────────────────────────────
        html.Div([

            # Card Mapa ─────────────────────────────────────────────────
            html.Div([
                html.Div([
                    html.Span("Mapa por Municipio", style={
                        "fontWeight": "700", "color": COLORS["primary"],
                        "fontSize": "14px", "letterSpacing": "0.04em",
                    }),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

                # Dropdowns mapa
                html.Div([
                    html.Div([
                        html.Span("Variable del colegio", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="dd-cat",
                            options=[{"label": k, "value": k} for k in vars_cat.keys()],
                            value="Naturaleza",
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1", "marginRight": "12px"}),
                    html.Div([
                        html.Span("Valor de variable", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="dd-val",
                            options=[{"label": "Todos", "value": "Todos"}],
                            value="Todos",
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1", "marginRight": "12px"}),
                    html.Div([
                        html.Span("Puntaje a visualizar", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="dd-punt",
                            options=[{"label": k, "value": k} for k in puntajes.keys()],
                            value="Promedio Mates y Cienc. Nat.",
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1"}),
                ], style={
                    "display": "flex", "alignItems": "flex-end",
                    "marginBottom": "16px", "paddingBottom": "16px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                }),

                dcc.Graph(id="mapa", style={"height": "490px"}, config={"displayModeBar": False}),

                # ── overlay municp ─────────────────────────────────────
                html.Div(
                    id="overlay-panel",
                    children=[
                        html.Div([
                            html.Div([
                                html.Span(id="overlay-titulo", style={
                                    "fontWeight": "700", "color": COLORS["primary"], "fontSize": "14px",
                                }),
                            ], style={"display": "flex", "alignItems": "center"}),
                            html.Button("✕", id="overlay-close", n_clicks=0, style={
                                "background": "none", "border": "none", "fontSize": "18px",
                                "cursor": "pointer", "color": COLORS["muted"], "padding": "0 4px",
                            }),
                        ], style={
                            "display": "flex", "justifyContent": "space-between",
                            "alignItems": "center", "marginBottom": "12px",
                            "paddingBottom": "10px",
                            "borderBottom": f"1px solid {COLORS['border']}",
                        }),
                        html.Div([
                            html.Button("Violín", id="tab-violin-btn", n_clicks=0, style={
                                "padding": "6px 16px", "marginRight": "8px",
                                "border": f"1px solid {COLORS['primary']}",
                                "borderRadius": "20px", "cursor": "pointer",
                                "backgroundColor": COLORS["primary"], "color": "white",
                                "fontSize": "12px", "fontWeight": "600",
                            }),
                            html.Button("Histograma", id="tab-hist-btn", n_clicks=0, style={
                                "padding": "6px 16px",
                                "border": f"1px solid {COLORS['border']}",
                                "borderRadius": "20px", "cursor": "pointer",
                                "backgroundColor": COLORS["surface"], "color": COLORS["muted"],
                                "fontSize": "12px", "fontWeight": "600",
                            }),
                        ], style={"marginBottom": "14px"}),
                        html.Div([
                            html.Div(id="div-modal-dd-cat", children=[
                                html.Span("Variable del colegio", style=LABEL_STYLE),
                                dcc.Dropdown(
                                    id="modal-dd-cat",
                                    options=[
                                        {"label": "Naturaleza", "value": "cole_naturaleza"},
                                        {"label": "Zona de Ubicación", "value": "cole_area_ubicacion"},
                                        {"label": "Jornada", "value": "cole_jornada"},
                                        {"label": "Carácter", "value": "cole_caracter"},
                                    ],
                                    value="cole_naturaleza",
                                    clearable=False,
                                    style=DROPDOWN_STYLE,
                                ),
                            ], style={"flex": "1", "marginRight": "12px"}),
                            html.Div([
                                html.Span("Puntaje", style=LABEL_STYLE),
                                dcc.Dropdown(
                                    id="modal-dd-punt",
                                    options=[{"label": k, "value": v} for k, v in puntajes.items()],
                                    value="punt_prom_mcn",
                                    clearable=False,
                                    style=DROPDOWN_STYLE,
                                ),
                            ], style={"flex": "1"}),
                        ], style={"display": "flex", "alignItems": "flex-end", "marginBottom": "14px"}),
                        dcc.Store(id="tab-activo", data="violin"),
                        html.Div(id="panel-violin", children=[
                            dcc.Graph(id="violin-plot", style={"height": "295px"},
                                      config={"displayModeBar": False})
                        ]),
                        html.Div(id="panel-hist", children=[
                            dcc.Graph(id="hist-plot", style={"height": "295px"},
                                      config={"displayModeBar": False})
                        ], style={"display": "none"}),
                    ],
                    style={
                        "display": "none",
                        "position": "absolute", "top": "0", "left": "0",
                        "width": "100%", "height": "100%",
                        "backgroundColor": COLORS["surface"],
                        "borderRadius": "12px", "padding": "24px",
                        "boxSizing": "border-box", "overflowY": "auto",
                        "zIndex": "10",
                        "boxShadow": "0 4px 24px rgba(0,56,118,0.13)",
                    }
                ),

            ], style={
                **CARD_STYLE,
                "flex": "1.3",
                "marginBottom": "0",
                "marginRight": "20px",
                "position": "relative",
                "minHeight": "640px",
            }),

            # ── card ranking ───────────────────────────────────
            html.Div([
                html.Div([
                    html.Span("Municipios de Mayor Impacto Potencial", style={
                        "fontWeight": "700", "color": COLORS["primary"],
                        "fontSize": "14px", "letterSpacing": "0.04em",
                    }),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),

                html.Div(
                    "Municipios por debajo del promedio departamental, ordenados por retorno estimado de intervención.",
                    style={"fontSize": "11px", "color": COLORS["muted"],
                           "lineHeight": "1.5", "marginBottom": "8px"}
                ),
                html.Div([
                    html.Div([
                        html.Span("Brecha", style={"fontWeight": "700", "color": COLORS["primary"], "fontSize": "11px"}),
                        html.Span(" — pts por debajo del promedio Boyacá.",
                                  style={"fontSize": "11px", "color": COLORS["muted"]}),
                    ], style={"marginBottom": "4px"}),
                    html.Div([
                        html.Span("Índice de impacto", style={"fontWeight": "700", "color": COLORS["primary"], "fontSize": "11px"}),
                        html.Span(" — brecha × N° estudiantes. Estima el retorno de una campaña focalizada.",
                                  style={"fontSize": "11px", "color": COLORS["muted"]}),
                    ], style={"marginBottom": "16px"}),
                ]),

                html.Div([
                    html.Div([
                        html.Span("Puntaje", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="rank-dd-punt",
                            options=[{"label": k, "value": v} for k, v in puntajes.items()],
                            value="punt_prom_mcn",
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1", "marginRight": "12px"}),
                    html.Div([
                        html.Span("Top municipios", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="rank-dd-top",
                            options=[
                                {"label": "Top 10", "value": 10},
                                {"label": "Top 15", "value": 15},
                                {"label": "Top 20", "value": 20},
                            ],
                            value=15,
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1"}),
                ], style={
                    "display": "flex", "alignItems": "flex-end",
                    "marginBottom": "16px", "paddingBottom": "16px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                }),

                dcc.Graph(id="rank-bar-plot", style={"height": "490px"},
                          config={"displayModeBar": False}),

            ], style={
                **CARD_STYLE,
                "flex": "1",
                "marginBottom": "0",
                "minHeight": "640px",
            }),

        ], style={"display": "flex", "alignItems": "stretch", "marginBottom": "20px"}),

        # fila 3 — comparativo departamental - tabla ────────────────────────────

        html.Div([

            #  card comparativo depto ────────────────────────────
            html.Div([
                html.Div([
                    html.Span("Comparativo Departamental por Tipo de Entorno", style={
                        "fontWeight": "700", "color": COLORS["primary"],
                        "fontSize": "14px", "letterSpacing": "0.04em",
                    }),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),

                html.Div(
                    "Promedio departamental por categoría de colegio. Rojo: por debajo del promedio Boyacá. Verde: por encima.",
                    style={"fontSize": "11px", "color": COLORS["muted"],
                           "lineHeight": "1.5", "marginBottom": "16px"}
                ),

                html.Div([
                    html.Div([
                        html.Span("Variable del colegio", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="comp-dd-cat",
                            options=[
                                {"label": "Naturaleza", "value": "cole_naturaleza"},
                                {"label": "Zona de Ubicación", "value": "cole_area_ubicacion"},
                                {"label": "Jornada", "value": "cole_jornada"},
                                {"label": "Carácter", "value": "cole_caracter"},
                            ],
                            value="cole_naturaleza",
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1", "marginRight": "12px"}),
                    html.Div([
                        html.Span("Puntaje", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="comp-dd-punt",
                            options=[{"label": k, "value": v} for k, v in puntajes.items()],
                            value="punt_prom_mcn",
                            clearable=False,
                            style=DROPDOWN_STYLE,
                        ),
                    ], style={"flex": "1"}),
                ], style={
                    "display": "flex", "alignItems": "flex-end",
                    "marginBottom": "16px", "paddingBottom": "16px",
                    "borderBottom": f"1px solid {COLORS['border']}",
                }),

                dcc.Graph(id="comp-bar-plot", style={"height": "340px"},
                          config={"displayModeBar": False}),

            ], style={
                **CARD_STYLE,
                "flex": "1",
                "marginBottom": "0",
                "marginRight": "20px",
            }),

            # ── card tabla ─────────────────────────────────
            html.Div([
                html.Div([
                    html.Span("Entorno Crítico por Municipio — Top 5", style={
                        "fontWeight": "700", "color": COLORS["primary"],
                        "fontSize": "14px", "letterSpacing": "0.04em",
                    }),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}),

                html.Div([
                    html.Div(
                        "¿Cómo se identifica el entorno crítico?",
                        style={"fontWeight": "700", "fontSize": "11px",
                               "color": COLORS["text"], "marginBottom": "4px"}
                    ),
                    html.Div(
                        "Para cada municipio del top 5, se evalúan las 4 variables categóricas "
                        "(Naturaleza, Zona, Jornada, Carácter). Dentro de cada variable se calcula "
                        "el promedio de cada categoría y se identifica la que presenta mayor brecha "
                        "negativa respecto al promedio del municipio. Se reporta la variable y categoría "
                        "con la brecha interna más grande.",
                        style={"fontSize": "11px", "color": COLORS["muted"],
                               "lineHeight": "1.6", "marginBottom": "14px"}
                    ),
                    html.Div([
                        html.Span("Color de brecha: ", style={"fontSize": "11px", "color": COLORS["muted"]}),
                        html.Span(" > 5 pts ", style={"fontSize": "11px", "color": "#D63031", "fontWeight": "700"}),
                        html.Span(" 2–5 pts ", style={"fontSize": "11px", "color": COLORS["accent"], "fontWeight": "700"}),
                        html.Span(" < 2 pts", style={"fontSize": "11px", "color": COLORS["secondary"], "fontWeight": "700"}),
                    ], style={"marginBottom": "16px"}),
                ], style={
                    "backgroundColor": COLORS["background"],
                    "borderRadius": "8px",
                    "padding": "12px 14px",
                    "marginBottom": "16px",
                    "borderLeft": f"4px solid {COLORS['primary']}",
                }),

                html.Div(id="tabla-entorno", style={"overflowX": "auto"}),

            ], style={
                **CARD_STYLE,
                "flex": "1",
                "marginBottom": "0",
            }),

        ], style={"display": "flex", "alignItems": "stretch", "marginBottom": "0"}),

        dcc.Store(id="municipio-store"),
    ])

# ── dashboard layout ───────────────────────────────────────────────────────────────
app.layout = html.Div(
    style={
        'backgroundColor': COLORS['background'],
        'fontFamily': '"Plus Jakarta Sans", "Segoe UI", sans-serif',
        'minHeight': '100vh',
    },
    children=[        
        html.Div([
            html.Div([
               
                html.Div("💼", style={'fontSize': '40px', 'marginRight': '18px'}),
                html.Div([
                    html.H1("Consultoría Chocotejazos", style={
                        'margin': '0', 'fontSize': '30px',
                        'fontWeight': '800', 'color': 'white',
                        'letterSpacing': '-0.02em',
                    }),
                    html.P("Análisis Educativo · Resultados Saber 11 - Boyacá", style={
                        'margin': '2px 0 0', 'fontSize': '24px',
                        'color': 'rgba(255,255,255,0.7)', 'fontWeight': '500',
                    }),
                ]),
            ], style={'display': 'flex', 'alignItems': 'center'}),

            html.Div("Proyecto 1", style={
                'backgroundColor': COLORS['secondary'],
                'color': 'white', 'fontSize': '13px',
                'fontWeight': '700', 'padding': '6px 16px',
                'borderRadius': '20px', 'letterSpacing': '0.04em',
            }),
        ], style={
            'background': f'linear-gradient(135deg, {COLORS["primary"]} 0%, #005199 100%)',
            'padding': '22px 48px',
            'display': 'flex',
            'justifyContent': 'space-between',
            'alignItems': 'center',
            'boxShadow': '0 4px 20px rgba(0,56,118,0.3)',
        }),

        # ── tabs ──────────────────────────────────────────────────────────
        html.Div([
            dcc.Tabs(
                id='tabs-botones',
                value='tab-1',
                children=[
                    dcc.Tab(label='🌐  Bilingüismo', value='tab-1', style=tab_base, selected_style=tab_selected),
                    dcc.Tab(label='🤝  Focalización Social', value='tab-2', style=tab_base, selected_style=tab_selected),
                    dcc.Tab(label='🔬  Entornos Científicos', value='tab-3', style=tab_base, selected_style=tab_selected),
                ],
                style={'borderBottom': f'1px solid {COLORS["border"]}'},
            ),
            html.Div(id='contenido-tab', style={'padding': '28px 48px'}),
        ]),
    ]
)    

#────────────────────────────────────────────────────────────────────    
# callbacks ────────────────────────────────────────────────────────────────────
#────────────────────────────────────────────────────────────────────

# ── renderizar contenido tab  ──────────────────────────────────
@app.callback(Output('contenido-tab', 'children'), Input('tabs-botones', 'value'))
def render_tab(tab):
    if tab == 'tab-1':
        return tab1_content()
    elif tab == 'tab-2':
        return tab2_csociales.tab2_content()
    else:
        return tab3_content()


# ── actualizar dropdown valor ──────────────────────────────────
@app.callback(
    Output('dd-val', 'options'),
    Output('dd-val', 'value'),
    Input('dd-cat', 'value'),
)
def update_val_options(cat_key):
    col = vars_cat.get(cat_key)
    if not col:
        return [{'label': 'Todos', 'value': 'Todos'}], 'Todos'
    vals = Data_used[col].dropna().unique().tolist()
    opts = [{'label': 'Todos', 'value': 'Todos'}] + [{'label': v, 'value': v} for v in sorted(vals)]
    return opts, 'Todos'


# ── KPIs tab 3 ───────────────────────────────────────────────────────────────
@app.callback(
    Output('tab3-kpis', 'children'),
    Input('dd-punt', 'value'),
)
def update_kpis(punt_key):
    col = puntajes.get(punt_key, 'punt_prom_mcn')
    promedio = Data_used[col].mean()
    maximo = Data_used[col].max()
    minimo = Data_used[col].min()
    n_munic = Data_used['cole_mcpio_ubicacion'].nunique()
    agg_munic = Data_used.groupby('cole_mcpio_ubicacion')[col].mean()
    n_bajo = (agg_munic < promedio).sum()
    return [
        make_kpi("Promedio Dpto.", f"{promedio:.0f}", "📊", COLORS['primary']),
        make_kpi("Puntaje Máximo", f"{maximo:.0f}", "🏆", COLORS['secondary']),
        make_kpi("Puntaje Mínimo", f"{minimo:.0f}", "⚠️",  '#D63031'),
        make_kpi("Bajo promedio", f"{n_bajo} / {n_munic}", "📍", COLORS['accent']),
    ]


# ── guardar municipio click ────────────────────────────────────
@app.callback(
    Output('municipio-store', 'data'),
    Input('mapa', 'clickData'),
    prevent_initial_call=True
)
def guardar_municipio(clickData):
    if clickData is None:
        return None
    return clickData['points'][0].get('customdata')

# ── mostrar/ocultar overlay al click municipio o cerrar ──────────
@app.callback(
    Output('overlay-panel',  'style'),
    Input('municipio-store', 'data'),
    Input('overlay-close',   'n_clicks'),
    prevent_initial_call=True,
)
def toggle_overlay(municipio, close_clicks):
    base = {
        'position': 'absolute', 'top': '0', 'left': '0',
        'width': '100%', 'height': '100%',
        'backgroundColor': COLORS['surface'],
        'borderRadius': '12px',
        'padding': '24px', 'boxSizing': 'border-box',
        'overflowY': 'auto', 'zIndex': '10',
        'boxShadow': '0 4px 24px rgba(0,56,118,0.13)',
    }
    triggered = dash.callback_context.triggered[0]['prop_id']
    if 'overlay-close' in triggered or not municipio:
        return {**base, 'display': 'none'}
    return {**base, 'display': 'block'}

# ── título del overlay ─────────────────────────────────────────────
@app.callback(
    Output('overlay-titulo', 'children'),
    Input('municipio-store', 'data'),
    prevent_initial_call=True,
)
def update_overlay_titulo(municipio):
    if not municipio:
        return ''
    return f"{municipio.title()} — Análisis de Desempeño"
    
# ── actualizar mapa ─────────────────────────────────────────────────
@app.callback(
    Output('mapa', 'figure'),
    Input('dd-cat', 'value'),
    Input('dd-val', 'value'),
    Input('dd-punt', 'value'),
)
def update_mapa(cat_label, cat_val, punt_label):
    col_cat = vars_cat.get(cat_label)
    punt_col = puntajes.get(punt_label, 'punt_prom_mcn')
    cat_filtro = cat_val if (cat_val and cat_val != 'Todos') else None

    z, text, municipios_reales = datos_trazar(punt_col, col_cat=col_cat, cat_valor=cat_filtro)

    titulo = punt_label
    if col_cat:
        titulo += f" | {cat_label}" + (f": {cat_val}" if cat_val != 'Todos' else '')

    fig = go.Figure()
    fig.add_trace(go.Choroplethmap(
        geojson = filt_geojson,
        locations = plot_df['id'],
        z = z,
        customdata = municipios_reales,
        colorscale = "RdYlGn",
        zmin = Data_used[punt_col].quantile(0.05),
        zmax = Data_used[punt_col].quantile(0.95),
        marker_opacity   = 0.75,
        marker_line_width= 0.5,
        text = text,
        hovertemplate = "%{text}<extra></extra>",
        colorbar = dict(title="Puntaje<br>promedio"),
    ))
    fig.add_trace(go.Scattermap(
        lat = latids_bordes,
        lon = longs_bordes,
        mode = 'lines',
        line = dict(width=2, color='#003876'),
        hoverinfo = 'skip',
        showlegend = False,
    ))
    fig.update_layout(
        map_style = "carto-positron",
        map_zoom = 7,
        map_center = {"lat": coords_centr[1], "lon": coords_centr[0]},
        margin = {"r": 0, "t": 0, "l": 0, "b": 0},
    )
    return fig

# ── toggle tabs ───────────────────
@app.callback(
    Output('tab-activo', 'data'),
    Output('panel-hist', 'style'),
    Output('panel-violin', 'style'),
    Output('tab-hist-btn', 'style'),
    Output('tab-violin-btn','style'),
    Input('tab-hist-btn', 'n_clicks'),
    Input('tab-violin-btn', 'n_clicks'),
    State('tab-activo', 'data'),
    prevent_initial_call=True,
)
def toggle_tab(click_hist, click_violin, tab_actual):
    triggered = dash.callback_context.triggered[0]['prop_id']

    btn_activo = {
        'padding': '7px 18px', 'marginRight': '8px',
        'border': f'1px solid {COLORS["primary"]}',
        'borderRadius': '20px', 'cursor': 'pointer',
        'backgroundColor': COLORS['primary'], 'color': 'white',
        'fontSize': '12px', 'fontWeight': '600',
    }
    btn_inactivo = {
        'padding': '7px 18px',
        'border': f'1px solid {COLORS["border"]}',
        'borderRadius': '20px', 'cursor': 'pointer',
        'backgroundColor': COLORS['surface'], 'color': COLORS['muted'],
        'fontSize': '12px', 'fontWeight': '600',
    }
    if 'tab-hist-btn' in triggered:
        return 'hist', {}, {'display': 'none'}, {**btn_inactivo, 'marginRight': '8px'}, btn_activo
    return 'violin', {'display': 'none'}, {}, btn_activo, {**btn_inactivo}
    
    

# ── ocultar dropdown variable cuando tab es hist ──────────────────
@app.callback(
    Output('div-modal-dd-cat', 'style'),
    Input('tab-activo', 'data'),
)
def toggle_dd_cat(tab):
    if tab == 'hist':
        return {'flex': '1', 'marginRight': '12px', 'display': 'none'}
    return {'flex': '1', 'marginRight': '12px'}

# ── gráfica comparativa departamental  ───────────────
@app.callback(
    Output('comp-bar-plot', 'figure'),
    Input('comp-dd-cat', 'value'),
    Input('comp-dd-punt', 'value'),
)
def update_comp_bar(var_col, punt_col):
    map_vars = {
        'cole_area_ubicacion': 'Zona de Ubicación',
        'cole_naturaleza': 'Naturaleza',
        'cole_jornada': 'Jornada',
        'cole_caracter': 'Carácter',
    }
    df = Data_used.copy()
    agg = df.groupby(var_col)[punt_col].agg(['mean', 'count']).reset_index()
    agg.columns = [var_col, 'promedio', 'n']
    agg = agg.sort_values('promedio')

    promedio_dpto = df[punt_col].mean()
    val_min = agg['promedio'].iloc[0]
    val_max = agg['promedio'].iloc[-1]        
    brecha = val_max - val_min    
    y_top = max(val_max * 1.22, promedio_dpto * 1.22, 70)
    
    fig = go.Figure()
    fig.add_hrect(
        y0=val_min, y1=val_max,
        fillcolor='rgba(180,180,180,0.10)',
        line_width=0,
        layer='below',
    )
    fig.add_hline(
        y=val_min,
        line_color='#D63031', line_width=1,
        line_dash='solid',opacity=0.7,
    )
    fig.add_hline(
        y=val_max,
        line_color=COLORS['secondary'], line_width=1,
        line_dash='solid',
        opacity=0.7,
    )
    fig.add_trace(go.Bar(
        x=agg[var_col],
        y=agg['promedio'],
        text=agg['promedio'].apply(lambda v: f"{v:.1f}"),
        textposition='outside',
        textfont=dict(size=12, color=COLORS['text'], family='Arial Black, sans-serif'),
        marker_color=[
            COLORS['secondary'] if v >= promedio_dpto else '#D63031'
            for v in agg['promedio']
        ],
        marker_line_width=0,
        customdata=list(zip(
            agg['n'],
            [f"+{v - promedio_dpto:.1f}" if v >= promedio_dpto
             else f"{v - promedio_dpto:.1f}" for v in agg['promedio']],
        )),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Promedio: %{y:.1f} pts<br>"
            "vs Boyacá: %{customdata[1]} pts<br>"
            "N° estudiantes: %{customdata[0]:,}<extra></extra>"
        ),
    ))
    fig.add_hline(
        y=promedio_dpto,
        line_dash='dash', line_color=COLORS['primary'], line_width=2,
        annotation_text=f"Boyacá: {promedio_dpto:.1f}",
        annotation_font=dict(color='black', size=11, weight='bold'),
        annotation_position="top right", opacity=0.75
    )
    
    if brecha >= 0.3:
        n_bajo  = (agg['promedio'] < promedio_dpto).sum()
        n_total = len(agg)
        fig.add_annotation(
            xref='paper', yref='paper',
            x=0.01, y=0.99,
            xanchor='left', yanchor='top',
            text=(
                f"<b>Brecha máx–mín: {brecha:.1f} pts</b><br>"
                f"<span style='font-size:10px;color:#666'>"
            ),
            showarrow=False,
            font=dict(size=12, color=COLORS['text']),
            bgcolor='white',
            bordercolor=COLORS['border'],
            borderwidth=1.5,
            borderpad=8,
            opacity=0.95,
        )

    fig.update_layout(
        yaxis=dict(
            title='Puntaje promedio',
            range=[0, y_top],
            gridcolor='#f0f0f0',
            zeroline=False,
        ),
        xaxis=dict(title=map_vars.get(var_col, var_col), tickfont=dict(size=12)),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=55, r=30, t=30, b=45),
        font=dict(family='"Plus Jakarta Sans", Arial', size=11),
        bargap=0.4,
    )
    return fig

# ── histograma ─────────────────────────────────────────────────────
@app.callback(
    Output('hist-plot', 'figure'),
    Input('municipio-store', 'data'),
    Input('modal-dd-punt', 'value'),
    prevent_initial_call=True
)
def update_hist(municipio, punt_col):
    map_puntajes = {
        'punt_matematicas': 'Matemáticas',
        'punt_c_naturales': 'Ciencias Naturales',
        'punt_prom_mcn': 'Promedio Mates y Cienc. Nat.'
    }
    if not municipio or punt_col not in map_puntajes:
        return go.Figure()

    municipio_canonico = mapa_norm_a_real.get(normalizar(municipio), municipio)
    df_canon = Data_used.copy()
    df_canon['mcpio_canon'] = df_canon['cole_mcpio_ubicacion'].map(
        lambda x: mapa_norm_a_real.get(normalizar(x), x)
    )
    data_mcpio  = df_canon[df_canon['mcpio_canon'] == municipio_canonico][punt_col].dropna()
    data_boyaca = df_canon[punt_col].dropna()

    if data_mcpio.empty:
        return go.Figure()

    n_bins = 30
    bin_width = 100 / n_bins
    x_range = np.linspace(0, 100, 500)
    kde = stats.gaussian_kde(data_boyaca)
    y_scaled  = kde(x_range) * len(data_mcpio) * bin_width

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=data_mcpio,
        name=municipio.title(),
        marker=dict(color=COLORS['primary'], line=dict(color='white', width=0.5)),
        opacity=0.76,
        xbins=dict(start=0, end=100, size=bin_width),
        hovertemplate='Puntaje: %{x}<br>Estudiantes: %{y}<extra></extra>'
    ))
    fig.add_trace(go.Scatter(
        x=x_range, y=y_scaled,
        mode='lines',
        name='Tendencia Boyacá',
        line=dict(color=COLORS['secondary'], width=3, shape='spline'),
        fill='tozeroy', fillcolor=f'rgba(239,85,59,0.08)',
        hoverinfo='skip'
    ))
    fig.update_layout(
        xaxis=dict(title="Puntaje (0 – 100)", range=[0, 100], gridcolor='#f0f0f0'),
        yaxis=dict(title="N° Estudiantes", gridcolor='#f0f0f0'),
        template='plotly_white',
        bargap=0.05,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=40, b=50),
        font=dict(family='"Plus Jakarta Sans", Arial', size=11),
        hovermode='x unified',
        title=dict(
            text=f"{municipio.title()} — {map_puntajes[punt_col]}",
            x=0.5, font=dict(size=13, color=COLORS['primary'])
        ),
    )
    return fig


# ── violín ─────────────────────────────────────────────────────────
@app.callback(
    Output('violin-plot', 'figure'),
    Input('municipio-store', 'data'),
    Input('modal-dd-cat', 'value'),
    Input('modal-dd-punt', 'value'),
    prevent_initial_call=True
)
def update_violin(municipio, col_cat, punt_col):
    map_cole_vars = {
        'cole_area_ubicacion': 'Zona de Ubicación',
        'cole_naturaleza': 'Naturaleza',
        'cole_caracter': 'Carácter',
        'cole_jornada': 'Jornada'
    }
    map_puntajes = {
        'punt_matematicas': 'Matemáticas',
        'punt_c_naturales': 'Ciencias Naturales',
        'punt_prom_mcn': 'Promedio Mats. Ciencias Nat.'
    }
    if not municipio:
        return go.Figure()

    municipio_canonico = mapa_norm_a_real.get(normalizar(municipio), municipio)
    df_mun = Data_used.copy()
    df_mun['mcpio_canon'] = df_mun['cole_mcpio_ubicacion'].map(
        lambda x: mapa_norm_a_real.get(normalizar(x), x)
    )
    df_mun = df_mun[df_mun['mcpio_canon'] == municipio_canonico].dropna(subset=[col_cat, punt_col])

    if df_mun.empty:
        return go.Figure()

    categorias = sorted(df_mun[col_cat].unique())
    fig = go.Figure()

    for cat in categorias:
        df_cat = df_mun[df_mun[col_cat] == cat]
        proporcion = len(df_cat) / len(df_mun) * 100
        mean_val = df_cat[punt_col].mean()
        fig.add_trace(go.Violin(
            y=df_cat[punt_col],
            name=f"{cat}<br>{proporcion:.1f}%",
            box_visible=True,
            meanline_visible=True,
            points=False,
            hoveron='violins',
            hovertemplate=(
                f"<b>{cat}</b><br>"
                f"Promedio: {mean_val:.1f}<br>"
                f"Proporción: {proporcion:.1f}%<br>"
                f"N°: {len(df_cat)}<extra></extra>"
            )
        ))

    fig.update_layout(
        showlegend=False,
        yaxis_title=map_puntajes.get(punt_col, punt_col),
        xaxis_title=map_cole_vars.get(col_cat, col_cat),
        margin=dict(l=50, r=20, t=40, b=60),
        plot_bgcolor='white',
        yaxis=dict(gridcolor='#f0f0f0'),
        font=dict(family='"Plus Jakarta Sans", Arial', size=11),
        hovermode='closest',
        title=dict(
            text=f"{municipio.title()} — {map_cole_vars.get(col_cat, col_cat)}",
            x=0.5, font=dict(size=13, color=COLORS['primary'])
        ),
    )
    return fig

# ── ranking de impacto  ───────────────────────────────────
@app.callback(
    Output('rank-bar-plot', 'figure'),
    Input('rank-dd-punt', 'value'),
    Input('rank-dd-top', 'value'),
)
def update_ranking(punt_col, top_n):
    map_puntajes = {
        'punt_matematicas': 'Matemáticas',
        'punt_c_naturales': 'Ciencias Naturales',
        'punt_prom_mcn': 'Promedio Mates y Cienc. Nat.'
    }
    df = Data_used.copy()
    df['mcpio_canon'] = df['cole_mcpio_ubicacion'].map(
        lambda x: mapa_norm_a_real.get(normalizar(x), x)
    )
    promedio_dpto = df[punt_col].mean()

    agg = df.groupby('mcpio_canon').agg(
        promedio = (punt_col, 'mean'),
        n_estudiantes = (punt_col, 'count'),
    ).reset_index()

    agg['brecha'] = promedio_dpto - agg['promedio']
    agg['impacto_potencial'] = agg['brecha'] * agg['n_estudiantes']
    agg = agg[agg['brecha'] > 0].sort_values('impacto_potencial', ascending=True).tail(top_n)

    norm_brecha = (agg['brecha'] - agg['brecha'].min()) / (agg['brecha'].max() - agg['brecha'].min() + 1e-9)
    colors = [f'rgba({int(214+41*n)},{int(48-48*n)},{int(49-49*n)},0.85)' for n in norm_brecha]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=agg['impacto_potencial'],
        y=agg['mcpio_canon'].str.title(),
        orientation='h',
        marker_color=colors,
        marker_line_width=0,
        customdata=list(zip(
            agg['promedio'].round(1),
            agg['n_estudiantes'],
            agg['brecha'].round(1),
            agg['impacto_potencial'].round(0),
        )),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "─────────────────────<br>"
            "Promedio municipio: <b>%{customdata[0]}</b> pts<br>"
            f"Promedio Boyacá: <b>{promedio_dpto:.1f}</b> pts<br>"
            "Brecha: <b>%{customdata[2]} pts</b> por debajo<br>"
            "Estudiantes afectados: <b>%{customdata[1]:,}</b><br>"
            "─────────────────────<br>"
            "Índice de impacto: <b>%{customdata[3]:,.0f}</b><br>"
            "<i>brecha × estudiantes — mayor valor = mayor</i><br>"
            "<i>retorno potencial de una campaña focalizada</i>"
            "<extra></extra>"
        ),
        text=agg['n_estudiantes'].apply(lambda n: f"{n:,} est."),
        textposition='outside',
        textfont=dict(size=10, color=COLORS['muted']),
    ))

    umbral = agg['impacto_potencial'].min()

    fig.add_vline(
        x=umbral,
        line_dash='dash',
        line_color=COLORS['primary'],
        line_width=1.5,        
    )
    fig.add_annotation(
        text=f"Umbral top {top_n}",
        xref="x", yref="paper",
        x=umbral, y=1.04,
        showarrow=False,
        font=dict(size=9, color=COLORS['muted']),
        xanchor='left',
        align='left',
        borderpad=2
    )
    fig.add_annotation(
        text=f"Referencia: promedio Boyacá = {promedio_dpto:.1f} pts ({map_puntajes.get(punt_col, '')})",
        xref="paper", yref="paper",
        x=0, y=-0.07,
        showarrow=False,
        font=dict(size=10, color=COLORS['muted']),
        xanchor='left',
    )
    
    fig.update_layout(
        xaxis=dict(title="Índice de Impacto", gridcolor='#f0f0f0', zeroline=False),
        yaxis=dict(title=None, tickfont=dict(size=11)),
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(l=10, r=110, t=20, b=40),
        font=dict(family='"Plus Jakarta Sans", Arial', size=11),
        bargap=0.25,
    )
    return fig

# ──  tabla entorno  ───────────────────────────────────
@app.callback(
    Output('tabla-entorno', 'children'),
    Input('rank-dd-punt', 'value'),
    Input('rank-dd-top',  'value'),
)
def update_tabla_entorno(punt_col, top_n):
    vars_entorno = {
        'cole_naturaleza': 'Naturaleza',
        'cole_area_ubicacion': 'Zona',
        'cole_jornada': 'Jornada',
        'cole_caracter': 'Carácter',
    }

    df = Data_used.copy()
    df['mcpio_canon'] = df['cole_mcpio_ubicacion'].map(
        lambda x: mapa_norm_a_real.get(normalizar(x), x)
    )

    promedio_dpto = df[punt_col].mean()

    agg = df.groupby('mcpio_canon').agg(
        promedio = (punt_col, 'mean'),
        n_estudiantes = (punt_col, 'count'),
    ).reset_index()
    agg['brecha'] = promedio_dpto - agg['promedio']
    agg['impacto_potencial'] = agg['brecha'] * agg['n_estudiantes']
    top5 = (
        agg[agg['brecha'] > 0]
        .sort_values('impacto_potencial', ascending=False)
        .head(5)['mcpio_canon']
        .tolist()
    )

    filas = []
    for mcpio in top5:
        df_m = df[df['mcpio_canon'] == mcpio]
        promedio_mcpio = df_m[punt_col].mean()

        mayor_brecha_val  = None
        mayor_brecha_var  = None
        mayor_brecha_diff = -1

        for col_cat, label_cat in vars_entorno.items():
            if col_cat not in df_m.columns:
                continue
            agg_cat = df_m.groupby(col_cat)[punt_col].mean()
            if agg_cat.empty:
                continue
            min_cat = agg_cat.idxmin()
            diff_cat = promedio_mcpio - agg_cat[min_cat]
            if diff_cat > mayor_brecha_diff:
                mayor_brecha_diff = diff_cat
                mayor_brecha_val  = min_cat
                mayor_brecha_var  = label_cat

        if mayor_brecha_diff > 5:
            color_brecha = '#D63031'
        elif mayor_brecha_diff > 2:
            color_brecha = COLORS['accent']
        else:
            color_brecha = COLORS['secondary']

        filas.append(html.Tr([
            html.Td(
                mcpio.title(),
                style={'padding': '8px 10px', 'fontSize': '12px',
                       'fontWeight': '600', 'color': COLORS['text'],
                       'borderBottom': f'1px solid {COLORS["border"]}'}
            ),
            html.Td(
                f"{mayor_brecha_var}: {mayor_brecha_val.title() if mayor_brecha_val else '—'}",
                style={'padding': '8px 10px', 'fontSize': '12px',
                       'color': COLORS['text'],
                       'borderBottom': f'1px solid {COLORS["border"]}'}
            ),
            html.Td(
                f"−{mayor_brecha_diff:.1f} pts",
                style={'padding': '8px 10px', 'fontSize': '12px',
                       'fontWeight': '700', 'color': color_brecha,
                       'textAlign': 'right',
                       'borderBottom': f'1px solid {COLORS["border"]}'}
            ),
        ]))

    tabla = html.Table([
        html.Thead(html.Tr([
            html.Th("Municipio", style={'padding': '6px 10px', 'fontSize': '11px',
                                               'color': COLORS['muted'], 'fontWeight': '700',
                                               'textTransform': 'uppercase', 'letterSpacing': '0.06em',
                                               'borderBottom': f'2px solid {COLORS["border"]}',
                                               'textAlign': 'left'}),
            html.Th("Entorno crítico", style={'padding': '6px 10px', 'fontSize': '11px',
                                               'color': COLORS['muted'], 'fontWeight': '700',
                                               'textTransform': 'uppercase', 'letterSpacing': '0.06em',
                                               'borderBottom': f'2px solid {COLORS["border"]}',
                                               'textAlign': 'left'}),
            html.Th("Brecha interna", style={'padding': '6px 10px', 'fontSize': '11px',
                                               'color': COLORS['muted'], 'fontWeight': '700',
                                               'textTransform': 'uppercase', 'letterSpacing': '0.06em',
                                               'borderBottom': f'2px solid {COLORS["border"]}',
                                               'textAlign': 'right'}),
        ])),
        html.Tbody(filas),
    ], style={
        'width': '100%',
        'borderCollapse': 'collapse',
        'backgroundColor': COLORS['surface'],
    })

    return tabla
                
if __name__ == '__main__':
    app.run(debug=True, port=8051)
