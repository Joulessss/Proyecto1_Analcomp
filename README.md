# Proyecto de Consultoría: Educación en Boyacá 🇨🇴
### Análisis de Componentes - Proyecto 1

Este repositorio contiene una solución integral de consultoría de datos enfocada en el desempeño educativo (competencias de Inglés y Ciencias Sociales) en el departamento de Boyacá, utilizando datos de pruebas estandarizadas.

## 👥 Equipo de Consultoría
* **Santiago Quintana (SQ)**: Análisis de negocio, ingeniería de datos y desarrollo de analítica.
* **Daniel Morantes (DM)**: Análisis de negocio, ingeniería de datos y arquitectura del tablero.
* **Juliana Quintana (JQ)**: Análisis de negocio, análisis de datos y gestión de despliegue.

---

## 📂 Ciclo de Vida y Organización del Proyecto

El proyecto se estructura en cinco fases principales, cada una documentada en carpetas específicas según el consultor responsable:

### 1. ❓ Generación de Preguntas de Negocio (`tarea1`)
Cada miembro del equipo definió una problemática estratégica mediante una pregunta de negocio. Estas se encuentran documentadas en archivos `.md` individuales:
* `tarea_1_analisis_negocio_SQ/pregunta_santiago.md`
* `tarea1_analisis_de_negocio_DM/pregunta.md`
* `tarea1_analisis_negocio_JQ/pregunta.md`

### 2. 🛠️ Ingeniería de Datos (`tarea2`)
La fase crítica de preparación se centraliza en la carpeta `tarea2_limpieza_DM/`. En este módulo se realiza la **Ingeniería de Datos**, que comprende:
* Limpieza profunda de registros inconsistentes.
* Tratamiento de valores nulos (técnicas de imputación y relleno de espacios).
* Estandarización de datasets para garantizar la integridad del análisis.

### 3. 📊 Análisis Exploratorio y Visualización (`tarea3`)
En estas carpetas se encuentran los notebooks `.ipynb` dedicados a la exploración de datos. Cada archivo genera las visualizaciones necesarias para dar respuesta a las preguntas planteadas en la Fase 1:
* **Santiago (`tarea_3_analisis_datos_SQ`)**: Análisis exploratorio de tendencias y métricas educativas.
* **Juliana (`tarea3_analisis_datos_JQ`)**: Foco en bilingüismo, produciendo mapas interactivos de brechas y promedios por municipio.
* **Daniel (`tarea3_analisis_de_datos_Daniel`)**: Foco en Ciencias Sociales, generando mapas de calor y desempeño regional.



### 4. 🖥️ Visualización y Dashboard con Dash (`tarea_4_tablero_SQ`)
Consolidación de los análisis en una aplicación web interactiva desarrollada con **Dash**. Este tablero permite integrar las visualizaciones de forma dinámica:
* `dashboard.py`: Punto de entrada y arquitectura principal de la aplicación.
* `tab1_bilingue.py` / `tab2_csociales.py`: Módulos de visualización específicos por competencia.

### 5. 🚀 Despliegue y Mantenimiento (`tarea5`)
La puesta en producción se coordina desde la carpeta `tarea5_despliegue_JQ/`. Para asegurar la escalabilidad, se utiliza la infraestructura definida en:
* **`PROYECTO_CONSULTORIA_BOYACA/`**: Contiene los scripts finales y la data maestra que alimenta la solución en el entorno de producción.

---

## 🛠️ Requerimientos y Restricciones
* **Restricción Técnica Clave:** Todo análisis y visualización respeta estrictamente la regla de utilizar un **máximo de 2 atributos distintos**, asegurando un enfoque preciso y eficiente en el análisis de componentes.
* **Dependencias Principales:** `pandas`, `plotly`, `dash`, `folium`.

---

## Guía de Ejecución Rápida
1. **Preparación:** Los datos limpios se generan desde el pipeline en `tarea2_limpieza_DM/`.
2. **Visualización Local:** Los mapas interactivos `.html` pueden consultarse directamente en las carpetas de análisis (`tarea3`).
3. **Lanzamiento del Dashboard:** Ejecutar el comando `python dashboard.py` dentro de la carpeta `tarea_4_tablero_SQ/`.
