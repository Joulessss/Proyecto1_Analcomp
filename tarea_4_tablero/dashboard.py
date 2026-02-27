
import pandas as pd
import numpy as np
import seaborn as sns
import plotly.express as px
import matplotlib.pyplot as plt
import json
import unicodedata
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output
import scipy.stats as stats


Data = pd.read_csv('../DataAWS.csv')

cols_used = ['cole_area_ubicacion', 'cole_caracter','cole_naturaleza','cole_jornada', #barplots apilados y donas y geograficos
             'cole_mcpio_ubicacion', 'cole_nombre_establecimiento',
             
             'punt_matematicas','punt_c_naturales'] # histograma kde
Data_used = Data[cols_used]
Data_used['punt_prom_mcn'] = (Data_used['punt_matematicas'] + Data_used['punt_c_naturales'])/2

with open('../data_df_graphs/gadm41_COL_2.json', 'r', encoding='utf-8') as f:
    geojson_data = json.load(f)
    
with open('../data_df_graphs/gadm41_COL_1.json', 'r', encoding='utf-8') as f:
    geojson_dpto = json.load(f)