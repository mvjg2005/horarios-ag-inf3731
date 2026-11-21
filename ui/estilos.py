"""Identidad visual sobria: azul marino institucional, blanco cálido y acentos dorados.

Sin emojis: los estados se comunican con color, texto y marcas tipográficas.
"""
import html as _html

AZUL = "#0E2240"        # marino institucional
AZUL_2 = "#1A3358"
AZUL_3 = "#3C5A85"
DORADO = "#B08D3C"      # dorado envejecido (acento)
DORADO_CLARO = "#E9DDBF"
PAPEL = "#FAF8F4"
LINEA = "#E4DFD5"
TEXTO = "#1B2433"
GRIS = "#6B7280"
ROJO = "#A63D3D"
VERDE = "#2F5D50"
OCRE = "#9C6B1E"

COLOR_TIPO = {"teoria": "#24406B", "laboratorio": "#2F6B6B", "auxiliatura": "#8C6D2A"}
PALETA = [AZUL, DORADO, "#2F6B6B", ROJO, AZUL_3, "#7A6A58"]

FUENTES = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&"
           "family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap")
SANS = "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif"
SERIF = "'Source Serif 4', Georgia, 'Times New Roman', serif"

CSS = f"""
<style>
@import url('{FUENTES}');
.stApp {{ background: {PAPEL}; }}
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {{ font-family: {SANS}; color: {TEXTO}; }}
.block-container {{ padding-top: 3.2rem; max-width: 1360px; }}
h1, h2, h3, h4 {{ font-family: {SERIF} !important; color: {AZUL} !important; font-weight: 600 !important;
                 letter-spacing: -.01em; }}
h4 {{ font-size: 1.12rem !important; margin-top: .8rem !important; }}
h5 {{ font-family: {SANS} !important; color: {GRIS} !important; font-size: .74rem !important; font-weight: 600 !important;
     text-transform: uppercase; letter-spacing: .12em; }}

/* ---------------- barra lateral ---------------- */
section[data-testid="stSidebar"] {{ background: {AZUL}; border-right: 1px solid #0A1A33; }}
section[data-testid="stSidebar"] * {{ color: #DCE3EE; }}
section[data-testid="stSidebar"] hr {{ border-color: #FFFFFF14; margin: .9rem 0; }}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ font-size: .7rem; text-transform: uppercase;
    letter-spacing: .14em; color: #8E9DB4 !important; font-weight: 600; }}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {{ background: #FFFFFF0D; border: 1px solid #FFFFFF26;
    border-radius: 3px; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #8E9DB4 !important; font-size: .76rem; }}
.marca {{ font-family: {SERIF}; font-size: 1.35rem; color: #FFFFFF !important; font-weight: 600; letter-spacing: .01em; }}
.marca-sub {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .16em; color: {DORADO} !important;
             font-weight: 600; margin-top: 2px; }}
.marca-inst {{ font-size: .76rem; color: #8E9DB4 !important; margin-top: 6px; line-height: 1.35; }}
/* menú de navegación: radios convertidos en lista */
[class*="st-key-nav_"], [class*="st-key-nav_"] .stRadio, [class*="st-key-nav_"] [role="radiogroup"] {{ width: 100% !important; }}
[class*="st-key-nav_"] [role="radiogroup"] {{ gap: 1px !important; }}
[class*="st-key-nav_"] [role="radiogroup"] > div {{ width: 100%; }}
[class*="st-key-nav_"] label[data-testid="stRadioOption"] {{ display: block; width: 100%; padding: .48rem .8rem;
    margin: 0; border-left: 2px solid transparent; border-radius: 0 3px 3px 0; transition: background .15s; }}
[class*="st-key-nav_"] label[data-testid="stRadioOption"] > div > div:first-child {{ display: none; }}
[class*="st-key-nav_"] label[data-testid="stRadioOption"] p {{ font-size: .9rem; color: #B9C4D4 !important; }}
[class*="st-key-nav_"] label[data-testid="stRadioOption"]:hover {{ background: #FFFFFF0A; }}
[class*="st-key-nav_"] label[data-testid="stRadioOption"][data-selected="true"] {{ background: #FFFFFF12;
    border-left-color: {DORADO}; }}
[class*="st-key-nav_"] label[data-testid="stRadioOption"][data-selected="true"] p {{ color: #FFFFFF !important;
    font-weight: 500; }}
header[data-testid="stHeader"] {{ background: transparent; }}

/* ---------------- encabezado de página ---------------- */
.enc {{ padding: 0 0 18px 0; margin-bottom: 22px; border-bottom: 1px solid {LINEA}; }}
.enc .sub {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .18em; color: {DORADO}; font-weight: 600; }}
.enc h1 {{ font-family: {SERIF}; font-size: 2rem; margin: 6px 0 6px 0; padding: 0; line-height: 1.15; }}
.enc p {{ color: {GRIS}; margin: 0; font-size: .95rem; max-width: 880px; }}

/* ---------------- indicadores ---------------- */
.kpi {{ background: #FFFFFF; border: 1px solid {LINEA}; border-radius: 4px; padding: 14px 16px 12px; height: 100%; }}
.kpi .v {{ font-family: {SERIF}; font-size: 1.85rem; font-weight: 600; color: {AZUL}; line-height: 1.1;
          font-variant-numeric: tabular-nums; }}
.kpi .l {{ font-size: .66rem; color: {GRIS}; text-transform: uppercase; letter-spacing: .06em; margin-top: 6px;
          font-weight: 500; line-height: 1.35; word-break: normal; overflow-wrap: normal; hyphens: none; }}
.kpi.mal {{ border-top: 2px solid {ROJO}; }} .kpi.mal .v {{ color: {ROJO}; }}
.kpi.bien {{ border-top: 2px solid {VERDE}; }} .kpi.bien .v {{ color: {VERDE}; }}
.kpi.neutro {{ border-top: 2px solid {DORADO}; }}

/* ---------------- etiquetas, avisos y leyendas ---------------- */
.insignia {{ display: inline-block; padding: 2px 9px; border-radius: 2px; font-size: .66rem; font-weight: 600;
            letter-spacing: .14em; text-transform: uppercase; margin-right: 8px; vertical-align: middle; }}
.insignia.real {{ border: 1px solid {DORADO}; color: {OCRE}; background: #FFFFFF; }}
.insignia.sim {{ border: 1px solid #A9B3C2; color: {AZUL_3}; background: #FFFFFF; }}
.aviso {{ background: #FFFFFF; border: 1px solid {LINEA}; border-left: 3px solid {AZUL_3}; border-radius: 3px;
          padding: 11px 15px; margin: 6px 0 14px; font-size: .92rem; line-height: 1.5; }}
.aviso .t {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .14em; font-weight: 600; display: block;
            margin-bottom: 3px; }}
.aviso.ok {{ border-left-color: {VERDE}; }} .aviso.ok .t {{ color: {VERDE}; }}
.aviso.err {{ border-left-color: {ROJO}; }} .aviso.err .t {{ color: {ROJO}; }}
.aviso.warn {{ border-left-color: {DORADO}; }} .aviso.warn .t {{ color: {OCRE}; }}
.aviso.note .t {{ color: {AZUL_3}; }}
.estado {{ display: inline-flex; align-items: center; gap: 6px; font-size: .78rem; font-weight: 500; }}
.estado i {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.leyenda {{ display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 4px 0 12px; }}
.leyenda span {{ display: inline-flex; align-items: center; font-size: .78rem; color: {GRIS}; }}
.leyenda i {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; margin-right: 7px; }}
.lista-supuestos {{ margin: 0; padding-left: 1.1rem; }}
.lista-supuestos li {{ margin: 3px 0; font-size: .9rem; color: {TEXTO}; }}

/* ---------------- controles ---------------- */
.stTabs [data-baseweb="tab-list"] {{ gap: 22px; border-bottom: 1px solid {LINEA}; }}
.stTabs [data-baseweb="tab"] {{ padding: 8px 0; }}
.stTabs [data-baseweb="tab"] p {{ font-size: .88rem; font-weight: 500; color: {GRIS}; }}
.stTabs [aria-selected="true"] p {{ color: {AZUL} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {DORADO} !important; height: 2px; }}
button[data-testid^="stBaseButton"] {{ border-radius: 3px; font-weight: 500; letter-spacing: .01em; }}
button[data-testid^="stBaseButton-secondary"] {{ border: 1px solid #C9CFD9; background: #FFFFFF; color: {AZUL}; }}
button[data-testid^="stBaseButton-secondary"]:hover {{ border-color: {DORADO}; color: {AZUL}; }}
button[data-testid^="stBaseButton-primary"] {{ background: {AZUL}; border: 1px solid {AZUL}; }}
button[data-testid^="stBaseButton-primary"]:hover {{ background: {AZUL_2}; border-color: {DORADO}; }}
button[data-testid^="stBaseButton-primary"] *, button[data-testid^="stBaseButton-primary"] {{ color: #FFFFFF !important; }}
button[data-testid^="stBaseButton-secondary"] p {{ color: {AZUL} !important; }}
button[data-testid^="stBaseButton"]:disabled, button[data-testid^="stBaseButton"]:disabled * {{ opacity: .55; }}
[data-testid="stForm"] {{ background: #FFFFFF; border: 1px solid {LINEA}; border-radius: 4px; padding: 1.2rem 1.4rem; }}
[data-testid="stExpander"] details {{ border: 1px solid {LINEA}; border-radius: 3px; background: #FFFFFF; }}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ border: 1px solid {LINEA}; border-radius: 3px; }}
[data-testid="stProgress"] > div > div > div > div {{ background: {DORADO}; }}
</style>
"""

ESTADO_COLOR = {"Cumplida": VERDE, "Incumplida": ROJO, "Preferencia incumplida": OCRE, "Pendiente de dato": AZUL_3,
                "Pendiente": OCRE, "Aprobada": VERDE, "Rechazada": ROJO, "Aplicada": AZUL_3,
                "Sí": VERDE, "No": ROJO}


def encabezado(titulo: str, subtitulo: str = "", seccion: str = "") -> str:
    return (f'<div class="enc"><div class="sub">{seccion}</div><h1>{titulo}</h1>'
            f'<p>{subtitulo}</p></div>')


def kpi(valor, etiqueta: str, estado: str = "") -> str:
    return f'<div class="kpi {estado}"><div class="v">{valor}</div><div class="l">{etiqueta}</div></div>'


def aviso_html(texto: str, tipo: str = "note", titulo: str | None = None) -> str:
    """Aviso sobrio con barra lateral de color. ``texto`` admite **negrita** simple."""
    t = titulo or {"ok": "Resultado", "err": "Atención", "warn": "Advertencia", "note": "Nota"}[tipo]
    cuerpo = _html.escape(texto)
    partes = cuerpo.split("**")
    cuerpo = "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(partes)).replace("\n", "<br>")
    return f'<div class="aviso {tipo}"><span class="t">{t}</span>{cuerpo}</div>'


def colorear_estados(df, columnas=("Estado", "Válida", "Horario válido")):
    """Styler de pandas: colorea el texto de las columnas de estado (sin íconos)."""
    def color(v):
        c = ESTADO_COLOR.get(str(v))
        return f"color: {c}; font-weight: 600" if c else ""
    cols = [c for c in columnas if c in df.columns]
    return df.style.map(color, subset=cols) if cols else df


def plotly_layout(fig, alto=360):
    fig.update_layout(height=alto, margin=dict(l=8, r=8, t=46, b=8), plot_bgcolor="#FFFFFF",
                      paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", color=TEXTO, size=12),
                      title=dict(font=dict(family="Source Serif 4, Georgia, serif", size=15, color=AZUL), x=0, xanchor="left"),
                      legend=dict(orientation="h", y=-0.18, font=dict(size=11)), colorway=PALETA,
                      hoverlabel=dict(font_family="IBM Plex Sans, sans-serif"))
    fig.update_xaxes(gridcolor="#F0ECE4", linecolor=LINEA, zerolinecolor=LINEA)
    fig.update_yaxes(gridcolor="#F0ECE4", linecolor=LINEA, zerolinecolor=LINEA)
    return fig
