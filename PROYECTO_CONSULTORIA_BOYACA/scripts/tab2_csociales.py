import json
import unicodedata
import warnings
import branca.colormap as cm
import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html, Input, Output
from scipy import stats
from app_instance import app

warnings.filterwarnings('ignore')

# estilos ────────────────────────────────────────────────────────────────────────
C = {
    'primary': '#003876',
    'secondary': '#009640',
    'accent': '#E8B400',
    'bg': '#F0F4F8',
    'surface': '#FFFFFF',
    'text': '#1A2B3C',
    'muted': '#6B7C93',
    'border': '#DDE3EA',
    'danger': '#D63031',
}
FONT = '"Plus Jakarta Sans", Arial, sans-serif'

CARD = {
    'backgroundColor': C['surface'],
    'borderRadius': '14px',
    'padding': '22px',
    'boxShadow': '0 2px 14px rgba(0,0,0,0.07)',
    'border': f'1px solid {C["border"]}',
    'marginBottom': '20px',
}
LBL = {
    'fontSize': '11px',
    'fontWeight': '700',
    'letterSpacing': '0.08em',
    'color': C['muted'],
    'textTransform': 'uppercase',
    'marginBottom': '5px',
    'display': 'block',
}
DD = {'fontSize': '13px', 'borderRadius': '8px', 'border': f'1px solid {C["border"]}'}

_TS = {
    'padding': '8px 12px',
    'fontSize': '11.5px',
    'fontWeight': '600',
    'color': C['muted'],
    'backgroundColor': C['bg'],
    'border': 'none',
    'borderBottom': f'2px solid {C["border"]}',
}
_TA = {**_TS, 'color': C['primary'], 'backgroundColor': C['surface'], 'borderBottom': f'3px solid {C["secondary"]}'}

_LAYOUT = dict(
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(family=FONT, size=13, color=C['text']),
    margin=dict(l=60, r=25, t=45, b=55),
    hoverlabel=dict(bgcolor='white', font_size=14, bordercolor=C['border']),
)


# datos ────────────────────────────────────────────────────────────────────────
DATA_PATH = 'PROYECTO_CONSULTORIA_BOYACA/data/cleaned_data.csv'
GEOJSON = 'PROYECTO_CONSULTORIA_BOYACA/data/boyaca_geojson_123_municipios.geojson'


def norm_text(s):
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.upper().strip()


try:
    _raw = pd.read_csv(DATA_PATH)
except FileNotFoundError:
    _raw = pd.DataFrame()

# globals seguros
_df = pd.DataFrame()
_df_valid = pd.DataFrame()
_pivot_sc = pd.DataFrame()
_agg_muni = pd.DataFrame()
_MAP_HTML = '<html><body style="padding:12px;font-family:sans-serif;color:#6B7C93">Sin datos</body></html>'

_FIG_BOX = go.Figure()
_FIG_VIOLIN = go.Figure()
_FIG_HEAT = go.Figure()
_FIG_KDE = go.Figure()


# helpers ────────────────────────────────────────────────────────────────────────
def _sty(fig, **kw):
    fig.update_layout(**{**_LAYOUT, **kw})
    fig.update_xaxes(showgrid=False, linecolor=C['border'], linewidth=1, tickfont=dict(size=13), title_font=dict(size=15))
    fig.update_yaxes(gridcolor='#eef1f5', linecolor='rgba(0,0,0,0)', tickfont=dict(size=13), title_font=dict(size=15))
    return fig

def _nota(texto):
    return html.Div(texto, style={
        'fontSize': '12px', 'color': C['muted'], 'lineHeight': '1.6',
        'backgroundColor': C['bg'], 'borderRadius': '8px',
        'padding': '10px 14px', 'marginBottom': '14px',
        'borderLeft': f'4px solid {C["primary"]}',
    })

# kpis ────────────────────────────────────────────────────────────────────────
def _kpi(label, value, color):
    return html.Div([
        html.Div(value, style={'fontSize': '28px', 'fontWeight': '800', 'color': color, 'lineHeight': '1'}),
        html.Div(label, style={
            'fontSize': '11px', 'color': C['muted'], 'fontWeight': '700',
            'letterSpacing': '0.06em', 'textTransform': 'uppercase', 'marginTop': '8px',
        }),
    ], style={
        **CARD, 'textAlign': 'center', 'padding': '20px 16px',
        'flex': '1', 'marginBottom': '0', 'borderTop': f'4px solid {color}',
    })

# renderizado tablas genericas ────────────────────────────────────────────────────────────────────────
def _render_simple_table(df, max_rows=8):
    if df.empty:
        return html.Div('Sin datos suficientes.', style={'fontSize': '12px', 'color': C['muted']})

    dfv = df.head(max_rows).copy()
    cols = list(dfv.columns)
    header = html.Thead(html.Tr([
        html.Th(c, style={
            'padding': '8px 10px',
            'fontSize': '11px',
            'fontWeight': '700',
            'textTransform': 'uppercase',
            'letterSpacing': '0.05em',
            'color': C['muted'],
            'textAlign': 'left',
            'borderBottom': f'2px solid {C["border"]}',
            'backgroundColor': '#F8FAFC',
        }) for c in cols
    ]))
    rows = []
    for _, row in dfv.iterrows():
        tds = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                txt = f'{v:.2e}' if 'p-valor' in c else f'{v:.2f}'
            else:
                txt = str(v)
            tds.append(html.Td(txt, style={
                'padding': '8px 10px',
                'fontSize': '12px',
                'borderBottom': f'1px solid {C["border"]}',
                'color': C['text'],
                'whiteSpace': 'nowrap',
            }))
        rows.append(html.Tr(tds))

    return html.Div([
        html.Table([header, html.Tbody(rows)], style={
            'width': '100%',
            'borderCollapse': 'separate',
            'borderSpacing': '0',
        })
    ], style={
        'maxHeight': '270px',
        'overflowY': 'auto',
        'overflowX': 'auto',
        'border': f'1px solid {C["border"]}',
        'borderRadius': '10px',
    })

# tabla de prioridades ────────────────────────────────────────────────────────────────────────
def _build_priority_df(df, agg_muni):
    if df.empty or agg_muni.empty:
        return pd.DataFrame()
    mean_dep = float(df['punt_sociales_ciudadanas'].mean())
    p = agg_muni.copy().reset_index().rename(columns={'index': 'muni_key'})
    p['brecha_vs_depto'] = (mean_dep - p['promedio_sc']).round(2)
    p['impacto'] = (p['brecha_vs_depto'].clip(lower=0) * p['n_total']).round(1)
    p = p[p['brecha_vs_depto'] > 0].sort_values('impacto', ascending=False)
    p['municipio'] = p['muni_key'].str.title()
    return p[['municipio', 'promedio_sc', 'brecha_vs_depto', 'n_total', 'segmento_frecuente', 'impacto']]

# tabla de significancia ────────────────────────────────────────────────────────────────────────
def _build_significance_df(df):
    rows = []
    comps = [
        ('OFICIAL', 'NO OFICIAL', 'Naturaleza: Oficial vs No Oficial', 'cole_naturaleza'),
        ('URBANO', 'RURAL', 'Área: Urbano vs Rural', 'cole_area_ubicacion'),
        ('S', 'N', 'PPL: Privados de libertad vs General', 'estu_privado_libertad'),
    ]
    for g1, g2, label, col in comps:
        s1 = df.loc[df[col] == g1, 'punt_sociales_ciudadanas'].dropna()
        s2 = df.loc[df[col] == g2, 'punt_sociales_ciudadanas'].dropna()
        if len(s1) < 5 or len(s2) < 5:
            continue
        _, p = stats.ttest_ind(s1, s2, equal_var=False)
        d = float(s1.mean() - s2.mean())
        se = float(np.sqrt(s1.var(ddof=1)/len(s1) + s2.var(ddof=1)/len(s2)))
        rows.append({
            'Comparación': label,
            'Brecha (A-B)': round(d, 2),
            'IC95 inf': round(d - 1.96*se, 2),
            'IC95 sup': round(d + 1.96*se, 2),
            'p-valor': float(p),
            'Significativo': 'Sí' if p < 0.05 else 'No',
        })
    return pd.DataFrame(rows)

# conclusion ────────────────────────────────────────────────────────────────────────
def _build_conclusion_text(df):
    if df.empty:
        return 'No fue posible construir conclusión por falta de datos.'
    means_nat = df.groupby('cole_naturaleza')['punt_sociales_ciudadanas'].mean()
    means_area = df.groupby('cole_area_ubicacion')['punt_sociales_ciudadanas'].mean()
    means_ppl = df.groupby('estu_privado_libertad')['punt_sociales_ciudadanas'].mean()

    nat_worst = means_nat.idxmin() if not means_nat.empty else 'N/D'
    area_worst = means_area.idxmin() if not means_area.empty else 'N/D'
    ppl_worst = means_ppl.idxmin() if not means_ppl.empty else 'N/D'

    nat_gap = (means_nat.max() - means_nat.min()) if len(means_nat) >= 2 else np.nan
    area_gap = (means_area.max() - means_area.min()) if len(means_area) >= 2 else np.nan
    ppl_gap = (means_ppl.max() - means_ppl.min()) if len(means_ppl) >= 2 else np.nan

    return (
        f'Conclusión directa: el menor desempeño se concentra en {nat_worst} por naturaleza, '
        f'en {area_worst} por ubicación y en el grupo {ppl_worst} para condición de libertad. '
        f'Brechas estimadas: naturaleza {nat_gap:.2f} pts, área {area_gap:.2f} pts y PPL {ppl_gap:.2f} pts.'
    )


# cajas ────────────────────────────────────────────────────────────────────────
def _build_box_figure(df):
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=['Naturaleza del colegio', 'Área de ubicación'],
        horizontal_spacing=0.12,
    )

    for nombre, filtro, colr in [
        ('Oficial (Público)', df['cole_naturaleza'] == 'OFICIAL', C['secondary']),
        ('No Oficial (Privado)', df['cole_naturaleza'] == 'NO OFICIAL', C['danger']),
    ]:
        n_obs = int(filtro.sum())
        fig.add_trace(go.Box(
            y=df.loc[filtro, 'punt_sociales_ciudadanas'],
            name=nombre,
            boxmean='sd',
            marker_color=colr,
            hovertemplate=(
                f'<b>{nombre}</b><br>'
                f'N° observaciones: {n_obs:,}<br>'
                'Puntaje C. Sociales: %{y:.1f}<extra></extra>'
            ),
        ), row=1, col=1)

    for nombre, filtro, colr in [
        ('Urbano', df['cole_area_ubicacion'] == 'URBANO', C['primary']),
        ('Rural', df['cole_area_ubicacion'] == 'RURAL', C['accent']),
    ]:
        n_obs = int(filtro.sum())
        fig.add_trace(go.Box(
            y=df.loc[filtro, 'punt_sociales_ciudadanas'],
            name=nombre,
            boxmean='sd',
            marker_color=colr,
            hovertemplate=(
                f'<b>{nombre}</b><br>'
                f'N° observaciones: {n_obs:,}<br>'
                'Puntaje C. Sociales: %{y:.1f}<extra></extra>'
            ),
            showlegend=False,
        ), row=1, col=2)

    fig.update_layout(height=510, title=dict(text='Distribución de puntajes por naturaleza y territorio', x=0.5))
    return _sty(fig, yaxis_title='Puntaje C. Sociales')

# violin ────────────────────────────────────────────────────────────────────────
def _build_violin_figure(df):
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=['Segmentos combinados', 'Privados de libertad vs población general'],
        horizontal_spacing=0.12,
    )

    seg_order = ['NO OFICIAL_RURAL', 'NO OFICIAL_URBANO', 'OFICIAL_RURAL', 'OFICIAL_URBANO']
    seg_colors = {
        'NO OFICIAL_RURAL': '#D95F02',
        'NO OFICIAL_URBANO': '#1B9E77',
        'OFICIAL_RURAL': '#7570B3',
        'OFICIAL_URBANO': '#E7298A',
    }
    for seg in seg_order:
        n_obs = int((df['segmento'] == seg).sum())
        fig.add_trace(go.Violin(
            y=df.loc[df['segmento'] == seg, 'punt_sociales_ciudadanas'],
            name=seg,
            box_visible=True,
            meanline_visible=True,
            line_color=seg_colors[seg],
            fillcolor=seg_colors[seg],
            opacity=0.6,
            hovertemplate=(
                f'<b>{seg}</b><br>'
                f'N° observaciones: {n_obs:,}<br>'
                'Puntaje C. Sociales: %{y:.1f}<extra></extra>'
            ),
        ), row=1, col=1)

    for nombre, filtro, colr in [
        ('NO', df['estu_privado_libertad'] == 'N', C['primary']),
        ('SI', df['estu_privado_libertad'] == 'S', C['danger']),
    ]:
        n_obs = int(filtro.sum())
        fig.add_trace(go.Violin(
            y=df.loc[filtro, 'punt_sociales_ciudadanas'],
            name=nombre,
            box_visible=True,
            meanline_visible=True,
            line_color=colr,
            fillcolor=colr,
            opacity=0.6,
            hovertemplate=(
                f'<b>{nombre}</b><br>'
                f'N° observaciones: {n_obs:,}<br>'
                'Puntaje C. Sociales: %{y:.1f}<extra></extra>'
            ),
            showlegend=False,
        ), row=1, col=2)

    fig.update_layout(height=520, title=dict(text='Dispersión por segmento social y condición de libertad', x=0.5))
    return _sty(fig, yaxis_title='Puntaje C. Sociales')

# heatmap ────────────────────────────────────────────────────────────────────────
def _build_heatmap_figure(df_valid):
    caracter_valid = ['ACADÉMICO', 'TÉCNICO/ACADÉMICO', 'TÉCNICO']
    pivot_sc = (
        df_valid.groupby(['segmento', 'cole_caracter'])['punt_sociales_ciudadanas']
        .mean()
        .unstack()
        .reindex(columns=caracter_valid)
        .reindex(['NO OFICIAL_RURAL', 'NO OFICIAL_URBANO', 'OFICIAL_RURAL', 'OFICIAL_URBANO'])
        .round(2)
    )
    pivot_n = (
        df_valid.groupby(['segmento', 'cole_caracter'])['punt_sociales_ciudadanas']
        .count()
        .unstack()
        .reindex(columns=caracter_valid)
        .reindex(['NO OFICIAL_RURAL', 'NO OFICIAL_URBANO', 'OFICIAL_RURAL', 'OFICIAL_URBANO'])
        .fillna(0)
        .astype(int)
    )

    fig = go.Figure(go.Heatmap(
        z=pivot_sc.values,
        x=caracter_valid,
        y=pivot_sc.index.tolist(),
        colorscale='RdYlGn',
        zmin=float(np.nanmin(pivot_sc.values)),
        zmax=float(np.nanmax(pivot_sc.values)),
        text=pivot_sc.values,
        texttemplate='%{text:.1f}',
        textfont=dict(size=14),
        customdata=pivot_n.values,
        colorbar=dict(title='Promedio<br>C. Sociales', thickness=14),
        hovertemplate=(
            '<b>%{y} — %{x}</b><br>'
            'Promedio C. Sociales: %{z:.1f} pts<br>'
            'N° estudiantes: %{customdata:,}<extra></extra>'
        ),
    ))
    fig.update_layout(height=560, title=dict(text='Desempeño promedio por segmento y carácter', x=0.5))
    return _sty(fig)

# kde ────────────────────────────────────────────────────────────────────────
def _build_kde_figure(df):
    fig = go.Figure()
    grupos = {
        'Población General': df.loc[df['estu_privado_libertad'] == 'N', 'punt_sociales_ciudadanas'],
        'Privados de Libertad': df.loc[df['estu_privado_libertad'] == 'S', 'punt_sociales_ciudadanas'],
    }
    colors = {'Población General': C['primary'], 'Privados de Libertad': C['danger']}

    for nombre, data in grupos.items():
        if len(data) < 3:
            continue
        kde = stats.gaussian_kde(data, bw_method=0.3)
        kde_x = np.linspace(0, 100, 300)
        fig.add_trace(go.Scatter(
            x=kde_x,
            y=kde(kde_x),
            mode='lines',
            name=f'{nombre} (n={len(data):,})',
            line=dict(width=3, color=colors[nombre]),
            fill='tozeroy',
            opacity=0.45,
            hovertemplate=(
                f'<b>{nombre}</b><br>'
                f'N° estudiantes: {len(data):,}<br>'
                'Puntaje C. Sociales: %{x:.1f}<br>'
                'Densidad estimada: %{y:.4f}<extra></extra>'
            ),
        ))
        fig.add_vline(
            x=float(data.mean()),
            line_dash='dash',
            line_width=1.7,
            line_color=colors[nombre],
            annotation_text=f'μ={data.mean():.1f}',
            annotation_font=dict(size=12, color=colors[nombre]),
            annotation_bgcolor='rgba(255,255,255,0.95)',
            annotation_position='top right',
        )

    fig.update_layout(height=500, title=dict(text='Densidad de puntajes: privados de libertad vs población general', x=0.5))
    return _sty(fig, xaxis_title='Puntaje C. Sociales', yaxis_title='Densidad')

# mapa ────────────────────────────────────────────────────────────────────────
def _build_map_html(agg_muni):
    try:
        with open(GEOJSON, encoding='utf-8') as f:
            geo = json.load(f)
    except FileNotFoundError:
        return ('<html><body style="font-family:sans-serif;padding:30px;color:#6B7C93">'
                f'<b>GeoJSON no encontrado:</b> {GEOJSON}</body></html>')

    geo_c = json.loads(json.dumps(geo))
    for ft in geo_c['features']:
        key = norm_text(ft['properties'].get('MPIO_CNMBR', ''))
        if key in agg_muni.index:
            ft['properties']['promedio_sc'] = float(agg_muni.at[key, 'promedio_sc'])
            ft['properties']['n_total'] = int(agg_muni.at[key, 'n_total'])
            ft['properties']['segmento_frecuente'] = str(agg_muni.at[key, 'segmento_frecuente'])
        else:
            ft['properties']['promedio_sc'] = 0.0
            ft['properties']['n_total'] = 0
            ft['properties']['segmento_frecuente'] = 'Sin datos'

    vmin = float(agg_muni['promedio_sc'].min())
    vmax = float(agg_muni['promedio_sc'].max())
    if vmax == vmin:
        vmax = vmin + 1

    cmap_obj = cm.linear.RdYlGn_11.scale(vmin, vmax)
    cmap_obj.caption = 'Promedio Ciencias Sociales y Ciudadanas'

    m = folium.Map(location=[5.6, -73.0], zoom_start=8, tiles='CartoDB positron')
    folium.GeoJson(
        geo_c,
        name='Promedio C. Sociales',
        style_function=lambda ft: {
            'fillColor': cmap_obj(ft['properties'].get('promedio_sc', 0)),
            'color': '#1f2937',
            'weight': 0.35,
            'fillOpacity': 0.85,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['MPIO_CNMBR', 'promedio_sc', 'n_total', 'segmento_frecuente'],
            aliases=['Municipio:', 'Promedio en C. Sociales:', 'N° estudiantes evaluados:', 'Segmento poblacional predominante:'],
            localize=True,
        ),
        highlight_function=lambda ft: {'weight': 1.5, 'fillOpacity': 0.95},
    ).add_to(m)

    cmap_obj.add_to(m)
    return m.get_root().render()


# preparacion
if not _raw.empty:
    _df = _raw.copy()
    _df['segmento'] = _df['cole_naturaleza'].astype(str) + '_' + _df['cole_area_ubicacion'].astype(str)

    _caracter_valid = ['ACADÉMICO', 'TÉCNICO/ACADÉMICO', 'TÉCNICO']
    _df_valid = _df[_df['cole_caracter'].isin(_caracter_valid)].copy()

    _agg_muni = (
        _df.groupby('cole_mcpio_ubicacion')
        .agg(
            promedio_sc=('punt_sociales_ciudadanas', 'mean'),
            n_total=('punt_sociales_ciudadanas', 'count'),
            segmento_frecuente=('segmento', lambda x: x.value_counts().idxmax()),
        )
        .round({'promedio_sc': 2, 'n_total': 0})
    )
    _agg_muni.index = [norm_text(x) for x in _agg_muni.index]
    _agg_muni = _agg_muni.groupby(level=0).agg(
        promedio_sc=('promedio_sc', 'mean'),
        n_total=('n_total', 'sum'),
        segmento_frecuente=('segmento_frecuente', lambda x: x.value_counts().idxmax()),
    ).round({'promedio_sc': 2})

    _MAP_HTML = _build_map_html(_agg_muni)

    _FIG_BOX = _build_box_figure(_df)
    _FIG_VIOLIN = _build_violin_figure(_df)
    _FIG_HEAT = _build_heatmap_figure(_df_valid)
    _FIG_KDE = _build_kde_figure(_df)


# layout ────────────────────────────────────────────────────────────────────────
def tab2_content():
    if _df.empty:
        return html.Div('No se encontraron datos para la pestaña 2.', style={'padding': '20px', 'color': C['muted']})

    # kpis
    ofi = _df.loc[_df['cole_naturaleza'] == 'OFICIAL', 'punt_sociales_ciudadanas'].mean()
    no_ofi = _df.loc[_df['cole_naturaleza'] == 'NO OFICIAL', 'punt_sociales_ciudadanas'].mean()
    urb = _df.loc[_df['cole_area_ubicacion'] == 'URBANO', 'punt_sociales_ciudadanas'].mean()
    rur = _df.loc[_df['cole_area_ubicacion'] == 'RURAL', 'punt_sociales_ciudadanas'].mean()
    ppl = _df.loc[_df['estu_privado_libertad'] == 'S', 'punt_sociales_ciudadanas'].mean()
    gen = _df.loc[_df['estu_privado_libertad'] == 'N', 'punt_sociales_ciudadanas'].mean()

    n_crit = int((_agg_muni['promedio_sc'] <= _agg_muni['promedio_sc'].quantile(0.25)).sum()) if not _agg_muni.empty else 0

    kpis = html.Div([
        _kpi('Brecha Oficial vs No Oficial', f'{(no_ofi-ofi):+.1f} pts', C['primary']),
        _kpi('Brecha Urbano vs Rural', f'{(urb-rur):+.1f} pts', C['secondary']),
        _kpi('Brecha PPL vs General', f'{(ppl-gen):+.1f} pts', C['danger']),
        _kpi('Municipios críticos (Q1)', f'{n_crit}', C['accent']),
    ], style={'display': 'flex', 'gap': '16px', 'marginBottom': '20px'})

    priority_df = _build_priority_df(_df, _agg_muni)
    signif_df = _build_significance_df(_df)
    conclusion_txt = _build_conclusion_text(_df)

    return html.Div([
        html.Div([
            html.Span('Pregunta 2', style={
                'backgroundColor': C['secondary'], 'color': 'white',
                'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '0.08em',
                'padding': '4px 12px', 'borderRadius': '20px', 'textTransform': 'uppercase'
            }),
            html.H3('Focalización de Esfuerzos Sociales', style={
                'color': C['primary'], 'fontWeight': '800', 'fontSize': '22px', 'margin': '12px 0 8px'
            }),
            html.P(
                'En el marco de la campaña departamental de concientización social, la '
                'Gobernación de Boyacá requiere identificar en qué segmentos poblacionales '
                'debe focalizar sus esfuerzos: ¿los resultados de las pruebas Saber 11 '
                'evidencian que el menor desempeño en el área de Ciencias Sociales y '
                'Ciudadanas se concentra en colegios públicos (OFICIALES) o privados '
                '(NO OFICIALES), en zonas urbanas o rurales, o en población privada de la '
                'libertad, de manera que permita priorizar territorial y poblacionalmente '
                'la intervención?',
                style={'color': C['text'], 'fontSize': '15px', 'lineHeight': '1.7', 'margin': '0'}
            ),
        ], style={**CARD, 'borderLeft': f'5px solid {C["secondary"]}', 'marginBottom': '20px'}),

        kpis,

        html.Div([
            html.Div([
                html.Div('Mapa municipal de desempeño en Ciencias Sociales', style={
                    'fontWeight': '800', 'color': C['primary'], 'fontSize': '22px', 'marginBottom': '12px'
                }),
                _nota('Se visualiza el puntaje promedio municipal y el segmento predominante para focalizar territorios críticos.'),
                html.Iframe(id='t2-map-frame', srcDoc=_MAP_HTML, style={
                    'width': '100%', 'height': '650px', 'border': 'none', 'borderRadius': '8px'
                }),
            ], style={**CARD, 'flex': '1.2', 'marginRight': '20px', 'marginBottom': '0'}),

            html.Div([
                html.Div('Panel analítico segmentado', style={
                    'fontWeight': '800', 'color': C['primary'], 'fontSize': '22px', 'marginBottom': '12px'
                }),
                dcc.Tabs(
                    id='t2-tabs', value='t2-violin',
                    style={'borderBottom': f'1px solid {C["border"]}', 'marginBottom': '16px'},
                    children=[
                        dcc.Tab(label='Violín Segmentos', value='t2-violin', style=_TS, selected_style=_TA),
                        dcc.Tab(label='Box Segmentos', value='t2-box', style=_TS, selected_style=_TA),
                        dcc.Tab(label='Heatmap Segmentos', value='t2-heat', style=_TS, selected_style=_TA),
                        dcc.Tab(label='KDE Poblacional', value='t2-kde', style=_TS, selected_style=_TA),
                    ]
                ),
                html.Div(id='t2-tab-content'),
            ], style={**CARD, 'flex': '1', 'marginBottom': '0'}),
        ], style={'display': 'flex', 'alignItems': 'stretch', 'marginBottom': '20px'}),

        html.Div([
            html.Div([
                html.Div('Conclusión Directa', style={
                    'fontWeight': '800', 'color': C['primary'], 'fontSize': '22px', 'marginBottom': '12px'
                }),
                html.Div(conclusion_txt, style={
                    'fontSize': '14px', 'lineHeight': '1.7', 'color': C['text'],
                    'backgroundColor': C['bg'], 'padding': '12px 14px',
                    'borderRadius': '8px', 'borderLeft': f'4px solid {C["secondary"]}',
                }),
            ], style={**CARD, 'flex': '1', 'marginRight': '20px', 'marginBottom': '0', 'minHeight': '320px'}),

            html.Div([
                html.Div('Tabla de Priorización', style={
                    'fontWeight': '800', 'color': C['primary'], 'fontSize': '22px', 'marginBottom': '12px'
                }),
                _nota('Municipios con mayor brecha frente al promedio departamental y mayor impacto potencial (brecha × volumen).'),
                _render_simple_table(priority_df.rename(columns={
                    'promedio_sc': 'Promedio',
                    'brecha_vs_depto': 'Brecha vs Dpto',
                    'n_total': 'N estudiantes',
                    'segmento_frecuente': 'Segmento pred.',
                    'impacto': 'Índice impacto',
                }), max_rows=8),
            ], style={**CARD, 'flex': '1', 'marginRight': '20px', 'marginBottom': '0', 'minHeight': '320px'}),

            html.Div([
                html.Div('Significancia Estadística', style={
                    'fontWeight': '800', 'color': C['primary'], 'fontSize': '22px', 'marginBottom': '12px'
                }),
                _nota('Pruebas t de Welch e intervalos de confianza al 95% para validar brechas entre segmentos.'),
                _render_simple_table(signif_df, max_rows=6),
            ], style={**CARD, 'flex': '1', 'marginBottom': '0', 'minHeight': '320px'}),
        ], style={'display': 'flex', 'alignItems': 'stretch'}),
    ])

# renderizar tab ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t2-tab-content', 'children'),
    Input('t2-tabs', 'value'),
)
def t2_render(tab):
    if tab == 't2-box':
        return html.Div([
            _nota('Comparación de dispersión por naturaleza institucional y entorno urbano-rural.'),
            dcc.Graph(figure=_FIG_BOX, style={'height': '520px'}, config={'displayModeBar': False}),
        ])

    if tab == 't2-heat':
        return html.Div([
            _nota('Promedios por combinación de segmento y carácter académico para detectar focos críticos.'),
            dcc.Graph(figure=_FIG_HEAT, style={'height': '570px'}, config={'displayModeBar': False}),
        ])

    if tab == 't2-kde':
        return html.Div([
            _nota('Densidades comparadas de puntaje para población general y población privada de libertad.'),
            dcc.Graph(figure=_FIG_KDE, style={'height': '510px'}, config={'displayModeBar': False}),
        ])

    return html.Div([
        _nota('Distribución completa de puntajes por segmento social y condición de libertad.'),
        dcc.Graph(figure=_FIG_VIOLIN, style={'height': '530px'}, config={'displayModeBar': False}),
    ])
