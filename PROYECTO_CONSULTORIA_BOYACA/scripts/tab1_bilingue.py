import json, re, unicodedata
import warnings
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+",
    category=Warning,
)

import folium
import branca.colormap as cm
from dash import dcc, html, Input, Output
from app_instance import app

#estilos ────────────────────────────────────────────────────────────────────────
C = {
    'primary':    '#003876',
    'secondary':  '#009640',
    'accent':     '#E8B400',
    'bg':         '#F0F4F8',
    'surface':    '#FFFFFF',
    'text':       '#1A2B3C',
    'muted':      '#6B7C93',
    'border':     '#DDE3EA',
    'bili':       "#0B3C6E",
    'nobili':     "#E6CF22",
    'danger':     '#D63031',
}
FONT = '"Plus Jakarta Sans", Arial, sans-serif'

CARD = {
    'backgroundColor': C['surface'], 'borderRadius': '14px',
    'padding': '22px', 'boxShadow': '0 2px 14px rgba(0,0,0,0.07)',
    'border': f'1px solid {C["border"]}', 'marginBottom': '20px',
}
LBL = {
    'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '0.08em',
    'color': C['muted'], 'textTransform': 'uppercase',
    'marginBottom': '5px', 'display': 'block',
}
DD = {'fontSize': '13px', 'borderRadius': '8px',
      'border': f'1px solid {C["border"]}'}

_LAYOUT = dict(
    plot_bgcolor='white', paper_bgcolor='white',
    font=dict(family=FONT, size=18, color=C['text']),
    margin=dict(l=55, r=30, t=36, b=52),
    hoverlabel=dict(bgcolor='white', font_size=15, bordercolor=C['border']),
    legend=dict(font=dict(size=13), title_font=dict(size=13)),
)

_TS = {
    'padding': '8px 12px', 'fontSize': '11.5px', 'fontWeight': '600',
    'color': C['muted'], 'backgroundColor': C['bg'],
    'border': 'none', 'borderBottom': f'2px solid {C["border"]}',
}
_TA = {**_TS, 'color': C['primary'], 'backgroundColor': C['surface'],
       'borderBottom': f'3px solid {C["secondary"]}'}

# constantes ────────────────────────────────────────────────────────────────────────
LABEL_BILI = {'S': 'Bilingüe', 'N': 'No bilingüe'}
ORDER_BILI  = ['No bilingüe', 'Bilingüe']
COLOR_BILI  = {'Bilingüe': C['bili'], 'No bilingüe': C['nobili']}
CARACT_MAP  = {
    'TÉCNICO/ACADÉMICO': 'Técnico/Académico',
    'TÉCNICO': 'Técnico',
    'ACADÉMICO': 'Académico',
    'NO APLICA': 'No aplica',
}
SCORE_OPTS = [
    {'label': 'Puntaje Inglés', 'value': 'punt_ingles'},
    {'label': 'Puntaje Global', 'value': 'punt_global'},
]
MAP_OPTIONS = {
    'mean_all': 'Promedio municipal en inglés',
    'gap_ing': 'Brecha promedio (Bilingüe − No bilingüe)',
    'cnt_bilingue': 'Cantidad de colegios bilingües',
    'pct_gt80': 'Porcentaje de estudiantes con inglés > 80',
    'cnt_lt30': 'Cantidad de estudiantes con inglés < 30',
    'cnt_gt85': 'Cantidad de estudiantes con inglés > 85',
}
GEOJSON = 'PROYECTO_CONSULTORIA_BOYACA/data/boyaca_geojson_123_municipios.geojson'

_BINS   = [0, 30, 50, 70, 85, 101]
_RANGOS = ['0–30', '31–50', '51–70', '71–85', '+85']

df_bili = pd.DataFrame()
agg_muni_t1 = pd.DataFrame()
_df_corr = pd.DataFrame()
_agg_bucket = pd.DataFrame()
_pivot = pd.DataFrame(columns=['Tipo', 'rango', 'n', 'pct'])

_FIG_RANGOS = go.Figure()
_FIG_BOX_ING = go.Figure()
_FIG_VIO_ING = go.Figure()
_FIG_BOX_GLOB = go.Figure()
_FIG_VIO_GLOB = go.Figure()
_FIG_ECDF_ING = go.Figure()
_FIG_ECDF_GLOB = go.Figure()
_FIG_FACET_ING = go.Figure()
_FIG_FACET_GLOB = go.Figure()
_FIG_IC = go.Figure()
_FIG_BUCKET_BAR = go.Figure()
_CI_TABLE_DF = pd.DataFrame(columns=['Puntaje', 'Diferencia', 'CI_low', 'CI_high', 'Significativo'])
_KPI_TABLE_DF = pd.DataFrame(columns=['Puntaje', 'Media Bilingüe', 'Media No Bilingüe', 'Brecha (S − N)', 'Brecha %'])



def norm_text(x):
    if pd.isna(x): return ''
    x = str(x).upper().strip()
    x = ''.join(c for c in unicodedata.normalize('NFD', x)
                if unicodedata.category(c) != 'Mn')
    x = re.sub(r'[^A-Z ]', ' ', x)
    return re.sub(r'\s+', ' ', x).strip()

#agregar municipios ────────────────────────────────────────────────────────────────────────
def _build_all(datos: pd.DataFrame):
    
    dg = datos[['cole_mcpio_ubicacion', 'cole_bilingue', 'punt_ingles', 'punt_global']].dropna().copy()
    dg['muni_key'] = dg['cole_mcpio_ubicacion'].map(norm_text)
    
    rows = []
    
    for muni, grp in dg.groupby('muni_key'):
        vals_ing = grp['punt_ingles']
        es_bili = grp['cole_bilingue'] == 'S'        
        bv = vals_ing[es_bili]
        nv = vals_ing[~es_bili]        
        cnt_b = len(bv)
        n_total = len(grp)                
        gap = (bv.mean() - nv.mean()) if (cnt_b > 0 and (n_total - cnt_b) > 0) else 0.0
        
        rows.append({
            'muni_key': muni,
            'mean_all': round(vals_ing.mean(), 2),
            'gap_ing': round(gap, 2),
            'cnt_bilingue': cnt_b,
            'cnt_no_bilingue': int((~es_bili).sum()),
            'n_total': n_total,
            'pct_bilingue': round(100 * (cnt_b / n_total), 1),
            'pct_gt80': round(100 * (vals_ing > 80).mean(), 1),
            'cnt_lt30': (vals_ing < 30).sum(),
            'cnt_gt85': (vals_ing > 85).sum(),
            'mean_global': grp['punt_global'].mean()
        })
    
    agg = pd.DataFrame(rows).set_index('muni_key').fillna(0)

    df_sch = (
        datos[['cole_mcpio_ubicacion', 'cole_bilingue']]
        .dropna(subset=['cole_mcpio_ubicacion', 'cole_bilingue'])
        .assign(muni_key=lambda d: d['cole_mcpio_ubicacion'].map(norm_text))
    )
    school_counts = (
        df_sch.groupby('muni_key')['cole_bilingue']
        .agg(cnt_bilingue_school=lambda s: (s == 'S').sum(), cnt_total='count')
        .reset_index()
    )

    df_corr = agg.reset_index().merge(school_counts, on='muni_key', how='left').fillna(0)
    df_corr['cnt_bilingue'] = df_corr['cnt_bilingue_school'].astype(int)
    max_cnt = int(df_corr['cnt_bilingue'].max())
    top_edge = max(21, max_cnt + 1)
    bins = [0, 1, 2, 3, 5, 8, 12, 20, top_edge]
    labels = ['0', '1', '2', '3-4', '5-7', '8-11', '12-19', '20+']
    df_corr['bucket'] = pd.cut(df_corr['cnt_bilingue'], bins=bins, labels=labels, right=False)

    # Actualizar métrica municipal cnt_bilingue para mapa y ranking
    agg = agg.reset_index().merge(
        school_counts[['muni_key', 'cnt_bilingue_school']],
        on='muni_key',
        how='left'
    ).fillna({'cnt_bilingue_school': 0}).set_index('muni_key')
    agg['cnt_bilingue'] = agg['cnt_bilingue_school'].astype(int)
    agg = agg.drop(columns=['cnt_bilingue_school'])

    agg_bucket = (
        df_corr.groupby('bucket', observed=True)
        .agg(
            mean_ing=('mean_all', 'mean'), 
            se=('mean_all', lambda s: (s.std(ddof=1) / len(s)**0.5 if len(s) > 1 else 0)),
            n_munis=('muni_key', 'count'),
            n_exams=('n_total', 'sum'),
        ).reset_index()
    )
    agg_bucket['err'] = 1.96 * agg_bucket['se']
    
    return agg.round(2), None, df_corr, agg_bucket


# kpis ────────────────────────────────────────────────────────────────────────
def _calc_kpis():
    if df_bili.empty or agg_muni_t1.empty:
        return {
            'ing': {'bili': 'N/D', 'nobili': 'N/D', 'brecha': 'N/D', 'brecha_pct': 'N/D'},
            'glob': {'bili': 'N/D', 'nobili': 'N/D', 'brecha': 'N/D', 'brecha_pct': 'N/D'},
            'n_colegios': 0, 'n_munic': 0, 'n_total_m': 0}

    k = {
        'ing': {'bili': 'N/D', 'nobili': 'N/D', 'brecha': 'N/D', 'brecha_pct': 'N/D'},
        'glob': {'bili': 'N/D', 'nobili': 'N/D', 'brecha': 'N/D', 'brecha_pct': 'N/D'},
    }
    for col, nm in [('punt_ingles', 'ing'), ('punt_global', 'glob')]:
        if col not in df_bili.columns:
            continue
        g  = df_bili.groupby('cole_bilingue')[col]
        ms = g.get_group('S').mean() if 'S' in g.groups else np.nan
        mn = g.get_group('N').mean() if 'N' in g.groups else np.nan
        if np.isnan(ms) or np.isnan(mn):
            continue
        k[nm] = dict(
            bili=round(ms, 1),
            nobili=round(mn, 1),
            brecha=round(ms - mn, 1),
            brecha_pct=round(100 * (ms - mn) / mn, 1) if mn != 0 else 'N/D'
        )
    k['n_colegios'] = int(agg_muni_t1['cnt_bilingue'].sum())
    k['n_munic'] = int((agg_muni_t1['cnt_bilingue'] > 0).sum())
    k['n_total_m'] = len(agg_muni_t1)
    return k


def _kpi(label, val, icon, color, sub=None):
    return html.Div([
        html.Div(icon, style={'fontSize': '28px', 'marginBottom': '8px'}),
        html.Div(str(val), style={
            'fontSize': '27px', 'fontWeight': '800',
            'color': color, 'lineHeight': '1',
        }),
        html.Div(label, style={
            'fontSize': '11px', 'color': C['muted'], 'fontWeight': '600',
            'letterSpacing': '0.06em', 'textTransform': 'uppercase',
            'marginTop': '6px',
        }),
        *([html.Div(sub, style={'fontSize': '10px', 'color': C['muted'],
                                'marginTop': '3px'})] if sub else []),
    ], style={**CARD, 'textAlign': 'center', 'padding': '20px 14px',
              'flex': '1', 'marginBottom': '0', 'borderTop': f'4px solid {color}'})


#helpers estilo ────────────────────────────────────────────────────────────────────────
def _sty(fig, **kw):
    fig.update_layout(**{**_LAYOUT, **kw})
    fig.update_xaxes(
        showgrid=False,
        linecolor=C['border'],
        linewidth=1,
        tickfont=dict(size=14),
        title_font=dict(size=16),
    )
    fig.update_yaxes(
        gridcolor='#eef1f5',
        linecolor='rgba(0,0,0,0)',
        tickfont=dict(size=14),
        title_font=dict(size=16),
    )
    return fig


def _nota(txt):
    return html.Div(txt, style={
        'fontSize': '11px', 'color': C['muted'], 'lineHeight': '1.6',
        'backgroundColor': C['bg'], 'borderRadius': '8px',
        'padding': '10px 14px', 'marginBottom': '14px',
        'borderLeft': f'4px solid {C["primary"]}',
    })


def _render_styled_table(df: pd.DataFrame, table_id: str, caption: str, highlight_col=None):
    if df.empty:
        return html.Div('Sin datos disponibles.', style={'fontSize': '12px', 'color': C['muted']})

    cols = list(df.columns)
    highlight_idx = None
    if highlight_col and highlight_col in df.columns:
        try:
            highlight_idx = df[highlight_col].astype(float).idxmax()
        except Exception:
            highlight_idx = None

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
            'position': 'sticky',
            'top': 0,
            'zIndex': 1,
        }) for c in cols
    ]))

    body_rows = []
    for idx, row in df.iterrows():
        row_style = {
            'backgroundColor': '#ECFDF3' if (highlight_idx is not None and idx == highlight_idx) else 'white'
        }
        cells = []
        for c in cols:
            val = row[c]
            if isinstance(val, float):
                if c == 'Brecha %':
                    txt = f"{val:+.1f}%"
                elif c in ('Diferencia', 'Brecha (S − N)'):
                    txt = f"{val:+.2f}"
                elif c in ('CI_low', 'CI_high', 'Media Bilingüe', 'Media No Bilingüe'):
                    txt = f"{val:.2f}"
                else:
                    txt = f"{val:.2f}"
            else:
                txt = str(val)
            cells.append(html.Td(txt, style={
                'padding': '8px 10px',
                'fontSize': '12px',
                'borderBottom': f'1px solid {C["border"]}',
                'color': C['text'],
                'whiteSpace': 'nowrap',
            }))
        body_rows.append(html.Tr(cells, style=row_style))

    table = html.Table([header, html.Tbody(body_rows)], style={
        'width': '100%',
        'borderCollapse': 'separate',
        'borderSpacing': '0',
    })

    return html.Div([
        html.Div(caption, style={
            'fontSize': '12px',
            'fontWeight': '700',
            'color': C['primary'],
            'marginBottom': '8px',
        }),
        html.Div(table, style={
            'maxHeight': '280px',
            'overflowY': 'auto',
            'overflowX': 'auto',
            'border': f'1px solid {C["border"]}',
            'borderRadius': '10px',
        })
    ], id=table_id)


# kpi para resumen tabla
def _kpi_analysis_block():
    if _KPI_TABLE_DF.empty:
        return html.Div('No hay datos suficientes para interpretar brechas.', style={
            'fontSize': '12px',
            'color': C['muted'],
            'marginTop': '10px',
        })

    best_idx = _KPI_TABLE_DF['Brecha (S − N)'].astype(float).idxmax()
    best_row = _KPI_TABLE_DF.loc[best_idx]
    best_score = best_row['Puntaje']
    best_gap = float(best_row['Brecha (S − N)'])
    best_pct = float(best_row['Brecha %'])

    sig_text = 'N/D'
    if not _CI_TABLE_DF.empty and 'Puntaje' in _CI_TABLE_DF.columns:
        row_ci = _CI_TABLE_DF[_CI_TABLE_DF['Puntaje'] == best_score]
        if not row_ci.empty:
            sig_text = row_ci.iloc[0]['Significativo']

    return html.Div([
        html.Div('Análisis y resultado', style={
            'fontSize': '12px',
            'fontWeight': '700',
            'color': C['primary'],
            'marginBottom': '6px',
        }),
        html.Div(
            f'El mayor diferencial se observa en {best_score}: +{best_gap:.2f} puntos '
            f'({best_pct:+.1f}% frente a no bilingüe). '
            f'Con base en los intervalos de confianza, el resultado para esta métrica es: {sig_text}.',
            style={'fontSize': '12px', 'color': C['text'], 'lineHeight': '1.6'}
        ),
    ], style={
        'marginTop': '12px',
        'padding': '10px 12px',
        'backgroundColor': C['bg'],
        'borderRadius': '10px',
        'borderLeft': f'4px solid {C["secondary"]}',
    })


# graficas ────────────────────────────────────────────────────────────────────────
#────────────────────────────────────────────────────────────────────────

# rangos ────────────────────────────────────────────────────────────────────────
def _fig_rangos():
    pal = [C['danger'], '#E8B400', C['muted'], C['secondary'], C['primary']]
    fig = px.bar(_pivot, x='Tipo', y='pct', color='rango',
                 category_orders={'Tipo': ORDER_BILI, 'rango': _RANGOS},
                 barmode='stack', text_auto='.1f',
                 color_discrete_sequence=pal,
                 labels={'Tipo': '', 'pct': '% de estudiantes', 'rango': 'Rango puntaje inglés'})
    fig.update_traces(
        textfont_size=13,
        textposition='auto',
        opacity=0.96,
        marker_line_width=0.25,
        marker_line_color='white',
    )
    return _sty(fig,
                yaxis_title='% de estudiantes', xaxis_title=None,
                hovermode='x unified',
                legend=dict(orientation='h', y=-0.24, x=0.5, xanchor='center', title=None),
                margin=dict(l=55, r=25, t=30, b=80))


# box y violin ────────────────────────────────────────────────────────────────────────
def _fig_box_violin(col, label):
    kw = dict(category_orders={'Tipo': ORDER_BILI},
              color_discrete_map=COLOR_BILI,
              labels={'Tipo': '', col: label})
    fb = px.box(df_bili, x='Tipo', y=col, color='Tipo',
                points='outliers', **kw)
    fb.update_traces(jitter=0.25, marker_opacity=0.12,
                     marker_size=3.5, boxmean='sd',
                     hovertemplate=f'<b>%{{x}}</b><br>{label}: %{{y:.1f}}<extra></extra>')
    for t in ORDER_BILI:
        mv = df_bili.loc[df_bili['Tipo'] == t, col].mean()
        fb.add_hline(y=mv, line_dash='dot', line_width=3.2,
                     line_color=COLOR_BILI[t],
                     annotation_text=f'μ={mv:.1f}',
                     annotation_font=dict(size=14, color=COLOR_BILI[t]),
                     annotation_bgcolor='rgba(255,255,255,0.95)',
                     annotation_position='right')
    _sty(fb, showlegend=False, margin=dict(l=55, r=80, t=30, b=40))

    fv = px.violin(df_bili, x='Tipo', y=col, color='Tipo', box=True, points=False, **kw)
    fv.update_traces(meanline_visible=True, opacity=0.95,
                     hovertemplate=f'<b>%{{x}}</b><br>{label}: %{{y:.1f}}<extra></extra>')
    _sty(fv, showlegend=False, margin=dict(l=55, r=25, t=30, b=40))
    return fb, fv


# ecdf ────────────────────────────────────────────────────────────────────────
def _fig_ecdf(col, label):
    df_d = df_bili[['Tipo', col]].dropna()
    p50n = df_d.loc[df_d['Tipo'] == 'No bilingüe', col].quantile(0.5)
    p50s = df_d.loc[df_d['Tipo'] == 'Bilingüe', col].quantile(0.5)
    ecdf_colors = {'Bilingüe': '#006D77', 'No bilingüe': '#D94841'}
    fig = px.ecdf(df_d, x=col, color='Tipo',
                  color_discrete_map=ecdf_colors,
                  category_orders={'Tipo': ORDER_BILI},
                  labels={col: label, 'Tipo': ''})
    fig.update_traces(line_width=3.8, opacity=0.98)
    fig.add_vline(x=p50n, line_dash='dot', line_color=ecdf_colors['No bilingüe'],
                  annotation_text=f'Med. No Bil.={p50n:.0f}',
                  annotation_font=dict(color=ecdf_colors['No bilingüe'], size=15),
                  annotation_bgcolor='rgba(255,255,255,0.96)')
    fig.add_vline(x=p50s, line_dash='dot', line_color=ecdf_colors['Bilingüe'],
                  annotation_text=f'Med. Bil.={p50s:.0f}',
                  annotation_position='top right',
                  annotation_font=dict(color=ecdf_colors['Bilingüe'], size=15),
                  annotation_bgcolor='rgba(255,255,255,0.96)')
    return _sty(fig, xaxis_title=label, yaxis_title='Probabilidad acumulada',
                legend=dict(orientation='h', y=-0.20, x=0.5, xanchor='center', title=None),
                margin=dict(l=55, r=25, t=30, b=68))


# boxplot facetas ────────────────────────────────────────────────────────────────────────
def _fig_facet(col, label):
    if 'caracter_lbl' not in df_bili.columns:
        return go.Figure()
    df_c = df_bili[['Tipo', col, 'caracter_lbl']].dropna()
    fig = px.box(df_c, x='Tipo', y=col, facet_col='caracter_lbl',
                 color='Tipo',
                 category_orders={'Tipo': ORDER_BILI},
                 color_discrete_map=COLOR_BILI,
                 points='outliers',
                 labels={'Tipo': '', col: label, 'caracter_lbl': ''})
    fig.update_traces(jitter=0.3, marker_opacity=0.2,
                      marker_size=3, boxmean=True,
                      hovertemplate=f'<b>%{{x}}</b><br>{label}: %{{y:.1f}}<extra></extra>')
    fig.for_each_annotation(lambda a: a.update(
        text=a.text.replace('caracter_lbl=', ''),
        font=dict(size=11, color=C['primary'])))
    return _sty(fig, showlegend=False, margin=dict(l=55, r=25, t=50, b=40))


# indice confianza ────────────────────────────────────────────────────────────────────────
def _build_ci_df():
    rows = []
    for col, nm in [('punt_ingles', 'Inglés'), ('punt_global', 'Global')]:
        if col not in df_bili.columns:
            continue
        g = df_bili[['cole_bilingue', col]].dropna()
        gs = g.loc[g['cole_bilingue'] == 'S', col]
        gn = g.loc[g['cole_bilingue'] == 'N', col]
        if len(gs) < 5 or len(gn) < 5:
            continue
        d = gs.mean() - gn.mean()
        se = np.sqrt(gs.var() / len(gs) + gn.var() / len(gn))
        rows.append({
            'Puntaje': nm,
            'Diferencia': d,
            'CI_low': d - 1.96 * se,
            'CI_high': d + 1.96 * se,
            'Significativo': '✅ Sí' if (d - 1.96 * se) > 0 else '❌ No'
        })
    return pd.DataFrame(rows)

# constr. KPI ────────────────────────────────────────────────────────────────────────
def _build_kpi_df():
    rows = []
    for col_name, label in [('punt_ingles', 'Inglés'), ('punt_global', 'Global')]:
        if col_name not in df_bili.columns:
            continue
        g = df_bili.groupby('cole_bilingue')[col_name]
        m_s = g.get_group('S').mean() if 'S' in g.groups else np.nan
        m_n = g.get_group('N').mean() if 'N' in g.groups else np.nan
        if np.isnan(m_s) or np.isnan(m_n):
            continue
        rows.append({
            'Puntaje': label,
            'Media Bilingüe': round(m_s, 2),
            'Media No Bilingüe': round(m_n, 2),
            'Brecha (S − N)': round(m_s - m_n, 2),
            'Brecha %': round(100 * (m_s - m_n) / m_n, 1) if m_n else np.nan,
        })
    return pd.DataFrame(rows)

# fig IC ────────────────────────────────────────────────────────────────────────
def _fig_ic():
    ci = _build_ci_df()
    fig = go.Figure()
    interval_colors = {'Inglés': C['secondary'], 'Global': C['accent']}
    for _, r in ci.iterrows():
        col = interval_colors.get(r['Puntaje'], C['primary'])
        fig.add_trace(go.Scatter(
            x=[r['CI_low'], r['CI_high']], y=[r['Puntaje'], r['Puntaje']],
            mode='lines', line=dict(color=col, width=6), showlegend=False,
            hovertemplate=f"IC 95 %: [{r['CI_low']:.2f}, {r['CI_high']:.2f}]<extra></extra>"))        
        for xe in [r['CI_low'], r['CI_high']]:
            fig.add_trace(go.Scatter(
                x=[xe], y=[r['Puntaje']], mode='markers',
                marker=dict(size=12, color=col, symbol='line-ns',
                            line=dict(width=2.5, color=col)),
                showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter(
            x=[r['Diferencia']], y=[r['Puntaje']], mode='markers',
            marker=dict(size=15, color='white', symbol='diamond',
                        line=dict(width=2.5, color=col)),
            showlegend=False,
            hovertemplate=(f"<b>{r['Puntaje']}</b><br>"
                           f"Diferencia: <b>{r['Diferencia']:.2f} pts</b><br>"
                           f"IC 95 %: [{r['CI_low']:.2f}, {r['CI_high']:.2f}]"
                           "<extra></extra>")))
    fig.add_vline(x=0, line_dash='solid', line_color=C['muted'],
                  line_width=1.5, annotation_text='Sin efecto',
                  annotation_font=dict(size=11, color=C['muted']),
                  annotation_position='top right')
    return _sty(fig,
                xaxis_title='Diferencia en puntos (Bilingüe − No bilingüe)',
                yaxis_title='', height=270,
                margin=dict(l=85, r=25, t=36, b=90),
                annotations=[dict(
                    xref='paper', yref='paper', x=0.5, y=-0.42,
                    text=('Rombo = estimador puntual  ·  Barra = IC 95 % (Welch)  ·  '
                          'Si el IC no cruza 0 la diferencia es significativa (α = 0.05)'),
                    showarrow=False,
                    font=dict(size=12, color=C['muted']), xanchor='center')])


# barra IC [pr bucket ────────────────────────────────────────────────────────────────────────
def _fig_bucket_bars():
    if _agg_bucket is None: return go.Figure()
    dfb = _agg_bucket.copy()
    fig = px.bar(dfb, x='bucket', y='mean_ing', error_y='err',
                 text='n_munis',
                 color_discrete_sequence=[C['primary']],
                 labels={'bucket': '# colegios bilingües (bucket)',
                         'mean_ing': 'Promedio inglés'})
    fig.update_traces(
        texttemplate='%{text} munis', textposition='outside',
        textfont_size=14,
        textfont_color=C['text'],
        marker_line_width=0.5,
        marker_line_color='white',
        error_y_color=C['text'],
        error_y_thickness=3,
        error_y_width=9,
        hovertemplate='<b>Bucket %{x}</b><br>Prom.: %{y:.1f}<br>Mun.: %{text}<extra></extra>')
    if not dfb.empty:
        y_top = float((dfb['mean_ing'] + dfb['err']).max())
        y_pad = max(2.0, y_top * 0.08)
        fig.update_yaxes(range=[0, y_top + y_pad * 2.2])

        left_x = dfb.iloc[0]['bucket']
        right_x = dfb.iloc[-1]['bucket']
        left_y = float(dfb.iloc[0]['mean_ing'] + dfb.iloc[0]['err']) + y_pad
        right_y = float(dfb.iloc[-1]['mean_ing'] + dfb.iloc[-1]['err']) + y_pad

        fig.add_annotation(
            x=left_x, y=left_y, text='<b>121</b>',
            showarrow=False,
            font=dict(size=15, color=C['primary']),
            bgcolor='rgba(255,255,255,0.96)',
            bordercolor=C['border'],
            borderwidth=1,
        )
        fig.add_annotation(
            x=right_x, y=right_y, text='<b>5</b>',
            showarrow=False,
            font=dict(size=15, color=C['primary']),
            bgcolor='rgba(255,255,255,0.96)',
            bordercolor=C['border'],
            borderwidth=1,
        )

    return _sty(
        fig,
        yaxis_title='Promedio inglés municipal',
        xaxis_title='Bucket de colegios bilingües',
        margin=dict(l=55, r=25, t=35, b=55),
    )


def _fig_bucket_strip():
    fig = px.strip(_df_corr, 
                   x='bucket', 
                   y='mean_all', 
                   color='gap_ing',
                   hover_data={'muni_key': True, 'cnt_bilingue': True, 'n_total': True, 'gap_ing': ':.2f'},
                   labels={'mean_all': 'Promedio inglés municipal', 'bucket': '# colegios bilingües (bucket)', 'gap_ing': 'Brecha bilingüe'})
    
    fig.update_layout(coloraxis_colorscale='RdYlGn')     
    fig.update_traces(marker=dict(size=8, opacity=0.78, line=dict(width=0.3, color='white')))
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor='rgba(0,0,0,0)',
                      plot_bgcolor='rgba(0,0,0,0)',
                      showlegend=False)
    return fig


# scatter ing. vs global ────────────────────────────────────────────────────────────────────────
def _fig_scatter(metric=None):
    df_s = df_bili.copy()

    if metric == 'cnt_lt30':
        df_s = df_s[df_s['punt_ingles'] < 30]
    elif metric == 'pct_gt80':
        df_s = df_s[df_s['punt_ingles'] > 80]
    elif metric == 'cnt_gt85':
        df_s = df_s[df_s['punt_ingles'] > 85]

    if df_s.empty:
        fig = go.Figure()
        fig.add_annotation(
            text='No hay datos para el filtro seleccionado.',
            xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False,
            font=dict(size=13, color=C['muted'])
        )
        return _sty(fig, margin=dict(l=20, r=20, t=30, b=20))

    df_s = df_s.sample(min(6000, len(df_s)), random_state=42)
    fig = px.scatter(df_s, x='punt_ingles', y='punt_global', color='Tipo',
                     category_orders={'Tipo': ORDER_BILI},
                     color_discrete_map=COLOR_BILI,
                     opacity=0.35,
                     labels={'punt_ingles': 'Puntaje Inglés',
                             'punt_global': 'Puntaje Global', 'Tipo': ''})
    
    fig.update_layout(font=dict(size=16), legend=dict(title=dict(font=dict(size=18)), font=dict(size=15), itemsizing='constant'))
    fig.update_traces(
        selector=dict(mode='markers'),
        marker=dict(size=10, opacity=0.4, line=dict(width=0.35, color='white'))
    )
    fig.update_traces(selector=dict(mode='lines'), line=dict(width=2.8))
    return _sty(fig,
                legend=dict(orientation='h', y=-0.18, x=0.5,
                            xanchor='center', title=None),
                margin=dict(l=55, r=25, t=30, b=65))


# hists municpio ────────────────────────────────────────────────────────────────────────
def _fig_hist_muni(metric):
    """Histograma distribución municipal — cell 7."""
    label = MAP_OPTIONS.get(metric, metric)
    df = agg_muni_t1.reset_index()
    if metric not in df.columns:
        metric, label = 'mean_all', MAP_OPTIONS['mean_all']
    mv = df[metric].mean()
    fig = px.histogram(df, x=metric, nbins=22, opacity=0.82,
                       color_discrete_sequence=[C['primary']],
                       labels={metric: label})
    fig.update_traces(marker_line_color='white', marker_line_width=0.7,
                      hovertemplate=f'{label}: %{{x:.1f}}<br>Mun.: %{{y}}<extra></extra>')
    fig.add_vline(x=mv, line_dash='dash', line_width=2, line_color=C['secondary'],
                  annotation_text=f'Media: {mv:.1f}',
                  annotation_font=dict(size=10, color=C['secondary']))
    return _sty(fig, xaxis_title=label, yaxis_title='# municipios',
                margin=dict(l=55, r=25, t=30, b=45))

# top municpios ────────────────────────────────────────────────────────────────────────
def _fig_top_muni(metric):
    """Top municipios barras horizontales — cells 8-9."""
    label = MAP_OPTIONS.get(metric, metric)
    df = agg_muni_t1.reset_index()
    if metric not in df.columns:
        metric, label = 'mean_all', MAP_OPTIONS['mean_all']
    df_p  = df[df['gap_ing'] > 0] if metric == 'gap_ing' else df
    top_n = 12 if metric == 'gap_ing' else 10
    top   = df_p.nlargest(top_n, metric).copy()
    norm = ((top[metric] - top[metric].min())
            / (top[metric].max() - top[metric].min() + 1e-9))
    cols = [f'rgba(0,{int(56+120*n)},{int(118+20*n)},0.85)' for n in norm]
    fig = go.Figure(go.Bar(
        x=top[metric], y=top['muni_key'].str.title(),
        orientation='h', marker_color=cols, marker_line_width=0,
        text=top[metric].apply(lambda v: f'{v:.1f}'),
        textposition='outside', textfont=dict(size=12),
        hovertemplate='<b>%{y}</b><br>' + label + ': %{x:.1f}<extra></extra>'))
    fig.update_layout(yaxis_categoryorder='total ascending')
    return _sty(fig, xaxis_title=label, yaxis_title=None,
                margin=dict(l=10, r=58, t=30, b=40))


# mapa ────────────────────────────────────────────────────────────────────────
def _build_map(metric):
    metric = metric if metric in agg_muni_t1.columns else 'mean_all'
    label  = MAP_OPTIONS.get(metric, metric)
    try:
        with open(GEOJSON, encoding='utf-8') as f:
            geo = json.load(f)
    except FileNotFoundError:
        return (f'<html><body style="font-family:sans-serif;padding:30px;'
                f'color:#6B7C93"><b>GeoJSON no encontrado:</b>{GEOJSON}</body></html>')

    geo_c = json.loads(json.dumps(geo))
    for ft in geo_c['features']:
        key = norm_text(ft['properties'].get('MPIO_CNMBR', ''))
        row = agg_muni_t1.loc[key] if key in agg_muni_t1.index else None
        for col in agg_muni_t1.columns:
            ft['properties'][col] = float(row[col]) if row is not None else 0.0

    vmin, vmax = agg_muni_t1[metric].min(), agg_muni_t1[metric].max()
    if vmin == vmax: vmax = vmin + 1

    cmap_map = {
        'gap_ing': cm.linear.RdBu_11.scale(vmin, vmax),
        'cnt_lt30': cm.linear.OrRd_09.scale(vmin, vmax),
        'cnt_gt85': cm.linear.Greens_09.scale(vmin, vmax),
        'cnt_bilingue': cm.linear.Greens_09.scale(vmin, vmax),
    }
    cmap_obj = cmap_map.get(metric, cm.linear.YlGnBu_09.scale(vmin, vmax))

    tt_fields  = ['MPIO_CNMBR', 'mean_all', 'gap_ing',
                  'cnt_bilingue', 'cnt_no_bilingue', 'pct_bilingue',
                  'cnt_lt30', 'cnt_gt85', 'n_total']
    tt_aliases = ['Municipio:', 'Prom. inglés:', 'Brecha Bil−No:',
                  '# col. bilingüos:', '# col. no bilingüos:',
                  '% bilingüe:', '# est. inglés <30:',
                  '# est. inglés >85:', 'N° exámenes:']

    m = folium.Map(location=[5.6, -73.0], zoom_start=8, tiles='CartoDB positron')
    folium.GeoJson(
        geo_c, name=label,
        style_function=lambda ft: {
            'fillColor': cmap_obj(ft['properties'].get(metric, 0)),
            'color': '#1f2937', 'weight': 0.35, 'fillOpacity': 0.85},
        tooltip=folium.GeoJsonTooltip(
            fields=tt_fields, aliases=tt_aliases, localize=True),
        highlight_function=lambda ft: {'weight': 1.5, 'fillOpacity': 0.95},
    ).add_to(m)
    cmap_obj.add_to(m)
    return m.get_root().render()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# layout ────────────────────────────────────────────────────────────────────────

def tab1_content():
    k = _calc_kpis()

    kpis = html.Div([
        _kpi('Brecha en Inglés',  f"+{k['ing']['brecha']} pts",
             '📈', C['secondary'],
             f"Bil: {k['ing']['bili']}  ·  No Bil: {k['ing']['nobili']}"),
        _kpi('Brecha en Global', f"+{k['glob']['brecha']} pts",
             '🌐', C['primary'],
             f"Bil: {k['glob']['bili']}  ·  No Bil: {k['glob']['nobili']}"),
        _kpi('Brecha relativa inglés', f"+{k['ing']['brecha_pct']}%",
             '📊', C['accent'], '% sobre media no bilingüe'),
        _kpi('Mun. con colegio bilingüe',
             f"{k['n_munic']} / {k['n_total_m']}",
             '📍', C['danger'],
             f"{k['n_colegios']} colegios bilingüos en total"),
    ], style={'display': 'flex', 'gap': '16px', 'marginBottom': '20px'})

    fila = html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.Span('Mapa Territorial del Desempeño en Inglés',
                              style={'fontWeight': '800', 'color': C['primary'],
                                     'fontSize': '24px', 'letterSpacing': '0.01em'}),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'marginBottom': '14px'}),
                html.Div([
                    html.Span('Métrica del mapa', style=LBL),
                    dcc.Dropdown(
                        id='t1-map-metric',
                        options=[{'label': lbl, 'value': k}
                                 for k, lbl in MAP_OPTIONS.items()],
                        value='mean_all', clearable=False, style=DD),
                ], style={'marginBottom': '14px', 'paddingBottom': '14px',
                          'borderBottom': f'1px solid {C["border"]}'}),
                html.Iframe(id='t1-map-frame',
                            style={'width': '100%', 'height': '680px',
                                   'border': 'none', 'borderRadius': '8px'}),
            ], style={**CARD, 'marginBottom': '20px', 'minHeight': '840px'}),

            html.Div([
                html.Div([
                    html.Span('Panel de Análisis Estructural',
                              style={'fontWeight': '800', 'color': C['primary'],
                                     'fontSize': '24px', 'letterSpacing': '0.01em'}),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'marginBottom': '14px'}),
                dcc.Tabs(
                    id='t1-fixed-tabs', value='t1-dist',
                    style={'borderBottom': f'1px solid {C["border"]}',
                           'marginBottom': '16px'},
                    children=[
                        dcc.Tab(label='Distribución', value='t1-dist',
                                style=_TS, selected_style=_TA),
                        dcc.Tab(label='Box / Violín', value='t1-box',
                                style=_TS, selected_style=_TA),
                        dcc.Tab(label='ECDF', value='t1-ecdf',
                                style=_TS, selected_style=_TA),
                        dcc.Tab(label='Por Carácter', value='t1-facet',
                                style=_TS, selected_style=_TA),
                        dcc.Tab(label='Intervalos', value='t1-ic',
                                style=_TS, selected_style=_TA),
                        dcc.Tab(label='Correlación Mun.', value='t1-bucket',
                                style=_TS, selected_style=_TA),
                    ]),
                html.Div(id='t1-fixed-content'),
            ], style={**CARD, 'marginBottom': '0', 'minHeight': '900px'}),
        ], style={'flex': '1.3', 'marginRight': '20px'}),

        html.Div([
            html.Div([
                html.Div([
                    html.Span('Panel de Análisis Dinámico',
                              style={'fontWeight': '800', 'color': C['primary'],
                                     'fontSize': '24px', 'letterSpacing': '0.01em'}),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'marginBottom': '14px'}),
                dcc.Tabs(
                    id='t1-tabs', value='t1-muni',
                    style={'borderBottom': f'1px solid {C["border"]}',
                           'marginBottom': '16px'},
                    children=[
                        dcc.Tab(label='Municipal', value='t1-muni',
                                style=_TS, selected_style=_TA),
                        dcc.Tab(label='Scatter', value='t1-scatter',
                                style=_TS, selected_style=_TA),
                    ]),
                html.Div(id='t1-tab-content'),
            ], style={**CARD, 'marginBottom': '20px', 'minHeight': '840px'}),

            html.Div([
                html.Div([
                    html.Span('Resumen Ejecutivo de Brechas',
                              style={'fontWeight': '800', 'color': C['primary'],
                                     'fontSize': '24px', 'letterSpacing': '0.01em'}),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'marginBottom': '12px'}),
                html.Div(
                    _render_styled_table(
                        _KPI_TABLE_DF,
                        table_id='t1-kpi-table',
                        caption='Comparativo de medias bilingüe vs no bilingüe',
                        highlight_col='Brecha (S − N)'
                    ),
                    id='t1-kpi-table-wrap'
                ),
                _kpi_analysis_block(),
            ], style={**CARD, 'marginBottom': '0', 'minHeight': '300px'}),

            html.Div([
                html.Div([
                    html.Span('Recomendación de Política Pública',
                              style={'fontWeight': '800', 'color': C['primary'],
                                     'fontSize': '24px', 'letterSpacing': '0.01em'}),
                ], style={'display': 'flex', 'alignItems': 'center',
                          'marginBottom': '12px'}),
                html.Div([
                    html.P(
                        'Se debe priorizar la intervención en los municipios que registran '
                        'las mayores brechas de puntaje, como Combita y Nobsa con 27.4 y '
                        '18.5 puntos de diferencia entre instituciones.',
                        style={'margin': '0 0 10px 0', 'fontSize': '18px',
                               'lineHeight': '1.7', 'color': C['text']}
                    ),
                    html.P(
                        'El fortalecimiento debe dirigirse a municipios con alto volumen '
                        'de estudiantes pero baja penetración bilingüe.',
                        style={'margin': '0 0 10px 0', 'fontSize': '18px',
                               'lineHeight': '1.7', 'color': C['text']}
                    ),
                    html.P(
                        'Dado que el análisis demostró que el bilingüismo funciona con igual '
                        'eficacia en colegios de carácter Técnico como en los Académicos, '
                        'la Gobernación puede implementar el programa en ambas modalidades '
                        'sin temor a perder efectividad por el enfoque pedagógico de la institución.',
                        style={'margin': '0', 'fontSize': '18px',
                               'lineHeight': '1.7', 'color': C['text']}
                    ),
                ], style={
                    'backgroundColor': C['bg'],
                    'padding': '14px 16px',
                    'borderRadius': '10px',
                    'borderLeft': f'4px solid {C["secondary"]}',
                }),
            ], style={**CARD, 'marginBottom': '0', 'marginTop': '20px', 'minHeight': '250px'}),
        ], style={'flex': '1'}),
    ], style={'display': 'flex', 'alignItems': 'stretch'})

    return html.Div([
        html.Div([
            html.Span('Pregunta 1', style={
                'backgroundColor': C['secondary'], 'color': 'white',
                'fontSize': '11px', 'fontWeight': '700',
                'letterSpacing': '0.08em', 'padding': '4px 12px',
                'borderRadius': '20px', 'textTransform': 'uppercase'}),
            html.H3('Impacto del Bilingüismo en el Desempeño',
                    style={'color': C['primary'], 'fontWeight': '800',
                           'fontSize': '20px', 'margin': '12px 0 8px'}),
            html.P(
                "Ante el interés de la Gobernación de Boyacá por fortalecer la calidad educativa, ¿existe evidencia, basada en los resultados de las pruebas Saber 11, de que los colegios bilingües presentan un desempeño significativamente superior en inglés y en el puntaje global frente a los colegios no bilingües del departamento, que justifique la viabilidad técnica de implementar programas de educación bilingüe en instituciones públicas bajo su control?",
                style={'color': C['text'], 'fontSize': '15px',
                       'lineHeight': '1.7', 'margin': '0'}),
        ], style={**CARD, 'borderLeft': f'5px solid {C["secondary"]}',
                  'marginBottom': '20px'}),
        kpis,
        fila,
    ])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# callbacks ────────────────────────────────────────────────────────────────────────

# mapa ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t1-map-frame', 'srcDoc'),
    Input('t1-map-metric', 'value'),
)
def t1_map(metric):
    return _build_map(metric)

# analisis comparativo - bars. municipio y scatter ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t1-tab-content', 'children'),
    Input('t1-tabs',       'value'),
    Input('t1-map-metric', 'value'),
)
def t1_tab(tab, metric):

    if tab == 't1-muni':
        only_ranking_metrics = {'gap_ing', 'cnt_bilingue'}
        if metric in only_ranking_metrics:
            return html.Div([
                _nota(f'Ranking municipal de "{MAP_OPTIONS.get(metric, metric)}". '
                      'Se destacan los municipios con mayor magnitud en la métrica seleccionada para priorizar intervención.'),
                dcc.Graph(figure=_fig_top_muni(metric),
                          style={'height': '620px'}, config={'displayModeBar': False}),
            ])
        return html.Div([
            _nota(f'Distribución y ranking municipal de '
                  f'"{MAP_OPTIONS.get(metric, metric)}" '
                  'para comparar dispersión territorial y líderes municipales en una sola vista.'),
            dcc.Graph(figure=_fig_hist_muni(metric),
                      style={'height': '270px'}, config={'displayModeBar': False}),
            dcc.Graph(figure=_fig_top_muni(metric),
                      style={'height': '350px'}, config={'displayModeBar': False}),
        ])

    if tab == 't1-scatter':
        etiqueta = MAP_OPTIONS.get(metric, metric)
        filtro_txt = ''
        if metric == 'cnt_lt30':
            filtro_txt = ' · filtrado a estudiantes con inglés < 30'
        elif metric == 'pct_gt80':
            filtro_txt = ' · filtrado a estudiantes con inglés > 80'
        elif metric == 'cnt_gt85':
            filtro_txt = ' · filtrado a estudiantes con inglés > 85'
        return html.Div([
            _nota(f'Métrica activa: "{etiqueta}"{filtro_txt}. '
                  'Cada punto representa un estudiante; las líneas permiten comparar la pendiente de desempeño entre tipos de colegio.'),
            dcc.Graph(figure=_fig_scatter(metric),
                      style={'height': '560px'}, config={'displayModeBar': False}),
        ])

    return html.Div()

# analisis fijo ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t1-fixed-content', 'children'),
    Input('t1-fixed-tabs', 'value'),
)
def t1_fixed_tab(tab):
    if tab == 't1-dist':
        return html.Div([
            _nota('% de estudiantes por rango de puntaje de inglés. '
                  'Permite identificar rápidamente si la distribución se concentra en niveles críticos (0-30) o de alto desempeño (+85).'),
            dcc.Graph(figure=_FIG_RANGOS,
                      style={'height': '560px'}, config={'displayModeBar': False}),
        ])

    if tab == 't1-box':
        return html.Div([
            html.Div([
                html.Span('Puntaje:', style={**LBL, 'display': 'inline','marginRight': '10px'}),
                dcc.RadioItems(
                    id='t1-fixed-score-radio', options=SCORE_OPTS,
                    value='punt_ingles', inline=True,
                    labelStyle={'marginRight': '16px', 'fontSize': '12px'}),
            ], style={'marginBottom': '10px'}),
            _nota('Línea punteada = media del grupo. '
                  'La caja resume el 50 % central y el violín muestra densidad para comparar forma y dispersión entre grupos.'),
            dcc.Graph(id='t1-fixed-box-fig', style={'height': '340px'},
                      config={'displayModeBar': False}),
            dcc.Graph(id='t1-fixed-vio-fig', style={'height': '360px'},
                      config={'displayModeBar': False}),
        ])

    if tab == 't1-ecdf':
        return html.Div([
            html.Div([
                html.Span('Puntaje:', style={**LBL, 'display': 'inline', 'marginRight': '10px'}),
                dcc.RadioItems(
                    id='t1-fixed-ecdf-radio', options=SCORE_OPTS,
                    value='punt_ingles', inline=True,
                    labelStyle={'marginRight': '16px', 'fontSize': '12px'}),
            ], style={'marginBottom': '10px'}),
            _nota('Curva bilingüe por debajo → dominancia estocástica: '
                  'si una curva permanece más a la derecha/abajo, ese grupo tiene mayor probabilidad de lograr puntajes altos.'),
            dcc.Graph(id='t1-fixed-ecdf-fig', style={'height': '560px'}, config={'displayModeBar': False}),
        ])

    if tab == 't1-facet':
        return html.Div([
            html.Div([
                html.Span('Puntaje:', style={**LBL, 'display': 'inline', 'marginRight': '10px'}),
                dcc.RadioItems(
                    id='t1-fixed-facet-radio', options=SCORE_OPTS,
                    value='punt_ingles', inline=True,
                    labelStyle={'marginRight': '16px', 'fontSize': '12px'}),
            ], style={'marginBottom': '10px'}),
            _nota('Brecha bilingüe por carácter de colegio '
                  '(Académico, Técnico, etc.) para evaluar si el efecto es homogéneo o depende del tipo de institución.'),
            dcc.Graph(id='t1-fixed-facet-fig', style={'height': '560px'}, config={'displayModeBar': False}),
        ])

    if tab == 't1-ic':
        return html.Div([
            _nota('Diferencia de medias (Bilingüe − No bilingüe) con IC 95 % Welch. '
                  'Cada intervalo resume incertidumbre: si no cruza el cero, hay evidencia estadística de brecha positiva.'),
            dcc.Graph(figure=_FIG_IC,
                      style={'height': '460px'}, config={'displayModeBar': False}),
            html.Div(
                _render_styled_table(
                    _CI_TABLE_DF,
                    table_id='t1-ci-table',
                    caption='Diferencia de medias bilingüe vs no bilingüe'
                ),
                style={'marginTop': '12px'}
            ),
        ])

    if tab == 't1-bucket':
        return html.Div([
            _nota('Relación entre número de colegios bilingües y desempeño municipal en inglés. '
                  'La barra resume media e IC 95% por bucket municipal.'),
            dcc.Graph(figure=_FIG_BUCKET_BAR, style={'height': '400px'},
                      config={'displayModeBar': False}),
            html.Div(
                'Nota: las etiquetas 121 (barra izquierda) y 5 (barra derecha) se incluyen como '
                'marcadores de referencia para explicar los extremos usados en la lectura de '
                'promedios bilingües más altos del departamento.',
                style={
                    'fontSize': '12px',
                    'color': C['text'],
                    'lineHeight': '1.6',
                    'backgroundColor': C['bg'],
                    'borderRadius': '8px',
                    'padding': '10px 14px',
                    'marginTop': '10px',
                    'borderLeft': f'4px solid {C["secondary"]}',
                },
            ),
        ])

    return html.Div()

# box violin en analisis fijo ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t1-fixed-box-fig', 'figure'),
    Output('t1-fixed-vio-fig', 'figure'),
    Input('t1-fixed-score-radio', 'value'),
)
def t1_fixed_box(score):
    return ((_FIG_BOX_GLOB, _FIG_VIO_GLOB)
            if score == 'punt_global'
            else (_FIG_BOX_ING, _FIG_VIO_ING))

# ecdf en analisis fijo ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t1-fixed-ecdf-fig', 'figure'),
    Input('t1-fixed-ecdf-radio', 'value'),
)
def t1_fixed_ecdf(score):
    return _FIG_ECDF_GLOB if score == 'punt_global' else _FIG_ECDF_ING

# caracter en analisis fijo ────────────────────────────────────────────────────────────────────────
@app.callback(
    Output('t1-fixed-facet-fig', 'figure'),
    Input('t1-fixed-facet-radio', 'value'),
)
def t1_fixed_facet(score):
    return _FIG_FACET_GLOB if score == 'punt_global' else _FIG_FACET_ING

# Carga de datos y creacion pivots y figuras ────────────────────────────────────────────────────────────────────────
try:
    _datos = pd.read_csv('PROYECTO_CONSULTORIA_BOYACA/data/cleaned_data.csv')
except FileNotFoundError:
    print('NO FILE')
    _datos = pd.DataFrame()

if not _datos.empty:
    _COLS = [
        'cole_bilingue', 'punt_ingles', 'punt_global', 'cole_caracter',
        'cole_mcpio_ubicacion', 'cole_cod_dane_establecimiento'
    ]
    _raw = _datos[[c for c in _COLS if c in _datos.columns]].copy()
    _raw['Tipo'] = _raw['cole_bilingue'].map(LABEL_BILI)

    if 'cole_caracter' in _raw.columns:
        _raw['caracter_lbl'] = _raw['cole_caracter'].map(CARACT_MAP).fillna('Otro')

    df_bili = _raw.dropna(subset=['punt_ingles', 'punt_global', 'cole_bilingue']).copy()
    agg_muni_t1, _sch_counts, _df_corr, _agg_bucket = _build_all(_datos)

    _df_desemp = _datos[['cole_bilingue', 'punt_ingles']].dropna().copy()
    _df_desemp['Tipo'] = _df_desemp['cole_bilingue'].map(LABEL_BILI)
    _df_desemp['rango'] = pd.cut(
        _df_desemp['punt_ingles'],
        bins=_BINS,
        labels=_RANGOS,
        right=True,
        include_lowest=True
    )
    _pivot = _df_desemp.groupby(['Tipo', 'rango'], observed=True).size().reset_index(name='n')
    _pivot['pct'] = 100 * _pivot['n'] / _pivot.groupby('Tipo')['n'].transform('sum')

    _FIG_RANGOS = _fig_rangos()
    _FIG_BOX_ING, _FIG_VIO_ING = _fig_box_violin('punt_ingles', 'Puntaje Inglés')
    _FIG_BOX_GLOB, _FIG_VIO_GLOB = _fig_box_violin('punt_global', 'Puntaje Global')
    _FIG_ECDF_ING = _fig_ecdf('punt_ingles', 'Puntaje Inglés')
    _FIG_ECDF_GLOB = _fig_ecdf('punt_global', 'Puntaje Global')
    _FIG_FACET_ING = _fig_facet('punt_ingles', 'Puntaje Inglés')
    _FIG_FACET_GLOB = _fig_facet('punt_global', 'Puntaje Global')
    _CI_TABLE_DF = _build_ci_df()
    _KPI_TABLE_DF = _build_kpi_df()
    _FIG_IC = _fig_ic()
    _FIG_BUCKET_BAR = _fig_bucket_bars()
else:
    print('DF vacio')
