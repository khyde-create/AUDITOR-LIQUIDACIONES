"""
============================================================
  AUDITOR DE LIQUIDACIONES DE CRÉDITO — Art. 510 CPC
  Ley N° 18.010 — LegalTech Chile
============================================================

INSTALACIÓN (una sola vez):
    pip install streamlit pdfplumber pandas

EJECUCIÓN:
    streamlit run auditor_liquidacion.py
============================================================
"""

import re
import io
import math
from datetime import datetime, date

import pandas as pd
import pdfplumber
import streamlit as st

# ─────────────────────────────────────────────
#  CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Auditor de Liquidaciones — Art. 510 CPC",
    page_icon="⚖️",
    layout="wide",
)

# ─────────────────────────────────────────────
#  CSS PERSONALIZADO
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Paleta general */
    :root {
        --err:  #8b1f1f;
        --err-bg: #fce8e8;
        --warn: #7a4a0a;
        --warn-bg: #fef3e2;
        --ok:   #2d5a11;
        --ok-bg: #eaf3de;
        --info: #1a4f8a;
        --info-bg: #e8f1fb;
    }

    /* Cabecera */
    .app-header {
        background: #1c1a16;
        color: #fff;
        padding: 1.2rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .app-header h1 { font-size: 1.4rem; margin: 0; font-weight: 600; }
    .app-header p  { font-size: 0.78rem; margin: 0; opacity: 0.5; letter-spacing: 0.06em; text-transform: uppercase; }

    /* Alertas */
    .alerta-roja {
        background: var(--err-bg);
        border-left: 4px solid var(--err);
        color: var(--err);
        padding: 0.85rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        font-size: 0.88rem;
        line-height: 1.6;
    }
    .alerta-amarilla {
        background: var(--warn-bg);
        border-left: 4px solid #d4820a;
        color: var(--warn);
        padding: 0.85rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        font-size: 0.88rem;
        line-height: 1.6;
    }
    .alerta-verde {
        background: var(--ok-bg);
        border-left: 4px solid var(--ok);
        color: var(--ok);
        padding: 0.85rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        font-size: 0.88rem;
        line-height: 1.6;
    }
    .alerta-azul {
        background: var(--info-bg);
        border-left: 4px solid var(--info);
        color: var(--info);
        padding: 0.85rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
        font-size: 0.88rem;
        line-height: 1.6;
    }

    /* Métricas resumen */
    .metric-card {
        background: #f7f5f0;
        border: 0.5px solid rgba(28,26,22,0.12);
        border-radius: 8px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .metric-label { font-size: 0.72rem; color: #9a9690; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
    .metric-value { font-size: 1.5rem; font-weight: 600; }
    .metric-sub   { font-size: 0.7rem; color: #9a9690; margin-top: 2px; }

    /* Sección */
    .seccion-titulo {
        font-size: 0.72rem;
        font-weight: 600;
        color: #9a9690;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin: 1.5rem 0 0.6rem;
        padding-bottom: 6px;
        border-bottom: 0.5px solid rgba(28,26,22,0.1);
    }

    /* Escrito */
    .escrito-box {
        background: #f7f5f0;
        border: 0.5px solid rgba(28,26,22,0.2);
        border-radius: 8px;
        padding: 1.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.82rem;
        line-height: 1.9;
        white-space: pre-wrap;
        max-height: 600px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CABECERA
# ─────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div>⚖️</div>
    <div>
        <h1>Auditor de Liquidaciones de Crédito</h1>
        <p>Art. 510 CPC · Ley N° 18.010 · LegalTech Chile</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  BARRA LATERAL
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    uploaded_file = st.file_uploader(
        "Cargar PDF de la liquidación",
        type=["pdf"],
        help="Archivo descargado desde el sistema del Poder Judicial (OJV / PJUD)",
    )

    st.markdown("---")
    st.markdown("### 🔧 Parámetros de auditoría")

    base_liquidacion = st.selectbox(
        "Base de días usada en la liquidación",
        options=[360, 365],
        index=0,
        help="Revise la nota al pie del documento. Si dice 'T.I.C. dividida por 360 días', seleccione 360.",
    )

    base_correcta = 365
    st.caption(f"Base correcta (Ley 18.010, Art. 11): **{base_correcta} días**")

    st.markdown("---")
    st.markdown("### 📋 Datos del escrito")
    abogado   = st.text_input("Abogado patrocinante", placeholder="Nombre completo")
    ejecutado = st.text_input("Ejecutado (deudor)",   placeholder="Nombre o razón social")
    ciudad    = st.text_input("Ciudad",               value="Santiago")

    st.markdown("---")
    st.markdown(
        "<small style='color:#9a9690;'>Solo para uso profesional.<br>"
        "Verifique siempre las tasas en <b>cmfchile.cl</b></small>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────
#  FUNCIONES AUXILIARES
# ─────────────────────────────────────────────

def limpiar_numero(texto: str) -> float:
    """Convierte strings como '$1.234.567' o '21,20%' a float."""
    if texto is None:
        return 0.0
    s = str(texto).strip()
    s = re.sub(r"[$ %]", "", s)
    s = s.replace(".", "").replace(",", ".")
    s = s.replace("(", "-").replace(")", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def calcular_interes(capital: float, dias: int, tasa_pct: float, base: int) -> float:
    """Interés = Capital × Días × (Tasa / 100 / base)"""
    if base == 0:
        return 0.0
    return capital * dias * (tasa_pct / 100.0 / base)


def fmt_clp(valor: float) -> str:
    """Formatea un número como pesos chilenos."""
    return f"$ {valor:,.0f}".replace(",", ".")


def fmt_pct(valor: float) -> str:
    return f"{valor:.4f}%"


# ─────────────────────────────────────────────
#  EXTRACCIÓN DE PDF
# ─────────────────────────────────────────────

COLS_BUSCAR = {
    "numero":    ["n°", "n", "numero", "número"],
    "fecha_mora":["fecha de mora", "fecha mora", "fecha vencimiento"],
    "capital":   ["capital adeudado", "capital", "monto"],
    "fecha_liq": ["fecha de consignación", "fecha consignación", "liquidación", "consignacion"],
    "dias":      ["días de mora", "dias de mora", "días mora", "dias"],
    "tasa":      ["t.i.c. % cmf", "t.i.c.", "tasa", "tic", "tasa cmf", "factor anual"],
    "factor_dia":["factor de interés diario", "factor interés diario", "factor diario"],
    "interes":   ["monto de intereses acumulados", "intereses acumulados", "monto de intereses", "intereses"],
    "consig_neg":["(-) consignación $", "consignación $", "consignacion"],
    "interes_neg":["intereses (-) consignación", "intereses (-) consignacion"],
    "capital_am":["capital amortizado", "capital amort"],
}


def detectar_col(headers: list[str], opciones: list[str]) -> int | None:
    """Retorna el índice de la primera columna que coincida."""
    headers_lower = [str(h).lower().strip() for h in headers]
    for op in opciones:
        for i, h in enumerate(headers_lower):
            if op in h:
                return i
    return None


def extraer_tabla_pdf(file_bytes: bytes) -> tuple[pd.DataFrame, dict]:
    """
    Extrae la tabla principal de intereses del PDF.
    Retorna (DataFrame, metadatos del encabezado).
    """
    meta = {}
    filas_datos = []
    headers_encontrados = None

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            texto_completo += (page.extract_text() or "") + "\n"

        # Extraer metadatos del encabezado
        for linea in texto_completo.split("\n"):
            ll = linea.lower().strip()
            if "rol" in ll and ":" in linea:
                meta["rol"] = linea.split(":", 1)[-1].strip()
            if "carátula" in ll or "caratula" in ll:
                meta["caratula"] = linea.split(":", 1)[-1].strip()
            if "tribunal" in ll and "juzgado" in ll.lower():
                meta["tribunal"] = linea.strip()
            if "fecha" in ll and "santiago" in ll.lower():
                meta["fecha_liq"] = linea.strip()

        # Buscar tablas en todas las páginas
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 3:
                    continue
                # Buscar fila de encabezados (primera fila con texto de columna)
                for row_i, row in enumerate(table):
                    row_clean = [str(c).lower().strip() if c else "" for c in row]
                    row_text  = " ".join(row_clean)
                    # Señal de que es la cabecera de la tabla de intereses
                    if any(kw in row_text for kw in ["capital", "días", "tasa", "interés", "mora"]):
                        headers_encontrados = row
                        # Tomar las filas de datos siguientes
                        for data_row in table[row_i + 1:]:
                            if data_row and any(c for c in data_row):
                                filas_datos.append(data_row)
                        break
                if headers_encontrados:
                    break
            if headers_encontrados:
                break

    if not headers_encontrados or not filas_datos:
        return pd.DataFrame(), meta

    # Mapear columnas
    col_map = {}
    for campo, opciones in COLS_BUSCAR.items():
        idx = detectar_col(headers_encontrados, opciones)
        if idx is not None:
            col_map[campo] = idx

    # Construir DataFrame
    registros = []
    for fila in filas_datos:
        # Saltar filas vacías o de totales sin número de factura
        celda_num = fila[col_map.get("numero", 0)] if col_map.get("numero") is not None else ""
        if celda_num is None or str(celda_num).strip() == "":
            continue

        def get(campo):
            idx = col_map.get(campo)
            if idx is None or idx >= len(fila):
                return None
            return fila[idx]

        try:
            registro = {
                "numero":     str(get("numero") or "").strip(),
                "fecha_mora": str(get("fecha_mora") or "").strip(),
                "capital":    limpiar_numero(get("capital")),
                "fecha_liq":  str(get("fecha_liq") or "").strip(),
                "dias":       int(limpiar_numero(get("dias")) or 0),
                "tasa":       limpiar_numero(get("tasa")),
                "factor_dia": limpiar_numero(get("factor_dia")),
                "interes_liq":limpiar_numero(get("interes")),
                "consig":     abs(limpiar_numero(get("consig_neg"))),
                "capital_am": limpiar_numero(get("capital_am")),
            }
            # Solo incluir si tiene capital o días
            if registro["capital"] > 0 or registro["dias"] > 0:
                registros.append(registro)
        except Exception:
            continue

    df = pd.DataFrame(registros)
    return df, meta


# ─────────────────────────────────────────────
#  AUDITORÍA
# ─────────────────────────────────────────────

def auditar(df: pd.DataFrame, base_liq: int) -> tuple[pd.DataFrame, list[dict]]:
    """
    Recalcula intereses con base 365 y detecta discrepancias.
    Retorna (df_auditado, lista_alertas).
    """
    alertas = []
    filas = []

    for _, row in df.iterrows():
        capital   = row["capital"]
        dias      = row["dias"]
        tasa      = row["tasa"]
        int_liq   = row["interes_liq"]

        # Cálculo con base de la liquidación (ej. 360)
        int_base_liq  = calcular_interes(capital, dias, tasa, base_liq)
        # Cálculo correcto (365)
        int_correcto  = calcular_interes(capital, dias, tasa, 365)
        # Diferencia
        diff_base     = int_liq - int_base_liq   # vs lo calculado con la base de la liquidación
        diff_legal    = int_liq - int_correcto    # vs lo correcto por ley

        # Verificar factor diario declarado
        factor_decl   = row.get("factor_dia", 0.0)
        factor_calc   = (tasa / 100.0 / base_liq) * 100  # en %
        diff_factor   = abs(factor_decl - factor_calc)

        estado = "✓ OK"
        if abs(diff_legal) > 50:
            estado = "⚠ Diferencia"
        if diff_legal > 500:
            estado = "✗ Error"

        filas.append({
            "N° Factura":           row["numero"],
            "Fecha mora":           row["fecha_mora"],
            "Capital ($)":          capital,
            "Días":                 dias,
            "Tasa (%)":             tasa,
            "Interés liquidado ($)": int_liq,
            f"Interés correcto 365 ($)": int_correcto,
            "Diferencia ($)":       diff_legal,
            "Estado":               estado,
        })

        # Alertas individuales
        if abs(diff_legal) > 50:
            alertas.append({
                "nivel": "roja" if diff_legal > 500 else "amarilla",
                "titulo": f"Factura {row['numero']} — Diferencia en intereses",
                "detalle": (
                    f"Interés liquidado: {fmt_clp(int_liq)} | "
                    f"Correcto (365 días): {fmt_clp(int_correcto)} | "
                    f"Exceso: {fmt_clp(diff_legal)}"
                ),
            })

    df_out = pd.DataFrame(filas)
    return df_out, alertas


def auditar_comision(df_raw: pd.DataFrame, texto_pdf: str) -> list[dict]:
    """
    Verifica si la Comisión Fija Única usa un saldo insoluto incorrecto.
    """
    alertas = []
    capital_real = df_raw["capital"].sum() if not df_raw.empty else 0

    # Buscar mención de comisión en el texto
    patron = re.compile(
        r"saldo\s+insoluto[\s.:$]*([0-9.,\s]+)",
        re.IGNORECASE
    )
    patron_com = re.compile(
        r"comisi[oó]n\s+fija[\s\w]*[:\s$]*([0-9.,\s]+)",
        re.IGNORECASE
    )
    patron_pct = re.compile(
        r"comisi[oó]n[\s\w]*\(?\s*%?\s*\)?\s*[:\s]*(\d+[,.]?\d*)\s*%",
        re.IGNORECASE
    )

    m_saldo = patron.search(texto_pdf)
    m_com   = patron_com.search(texto_pdf)
    m_pct   = patron_pct.search(texto_pdf)

    if m_saldo:
        saldo_str = m_saldo.group(1).replace(" ", "").replace(".", "").replace(",", ".")
        try:
            saldo_insoluto = float(saldo_str)
        except ValueError:
            saldo_insoluto = 0.0

        if saldo_insoluto > 0 and capital_real > 0:
            ratio = saldo_insoluto / capital_real
            if ratio > 2:
                alertas.append({
                    "nivel": "roja",
                    "titulo": "🚨 ERROR DE PLANTILLA — Comisión Fija Única sobre base incorrecta",
                    "detalle": (
                        f"El 'Saldo Insoluto' usado para calcular la comisión es **{fmt_clp(saldo_insoluto)}**, "
                        f"pero la suma real de capitales adeudados es solo **{fmt_clp(capital_real)}**. "
                        f"La diferencia es {ratio:.1f}x el capital real. "
                        f"La comisión se habría calculado sobre un saldo correspondiente a la deuda original total "
                        f"(antes de consignaciones), no sobre el saldo insoluto vigente."
                    ),
                })
            elif abs(saldo_insoluto - capital_real) > 1000:
                alertas.append({
                    "nivel": "amarilla",
                    "titulo": "Comisión — Saldo insoluto difiere del capital real",
                    "detalle": (
                        f"Saldo insoluto declarado: {fmt_clp(saldo_insoluto)} | "
                        f"Capital real suma: {fmt_clp(capital_real)} | "
                        f"Diferencia: {fmt_clp(abs(saldo_insoluto - capital_real))}"
                    ),
                })

    if m_com and not m_saldo:
        alertas.append({
            "nivel": "amarilla",
            "titulo": "Comisión Fija Única detectada — verificar manualmente",
            "detalle": "Se detectó una comisión en el documento. Verifique si fue ordenada en la sentencia y si la base de cálculo es correcta.",
        })

    return alertas


def auditar_base_dias(df_raw: pd.DataFrame, base_liq: int) -> list[dict]:
    """Alerta global si la base de días de la liquidación no es 365."""
    alertas = []
    if base_liq != 365:
        total_int_liq   = df_raw["interes_liq"].sum() if "interes_liq" in df_raw.columns else 0
        total_int_corr  = sum(
            calcular_interes(r["capital"], r["dias"], r["tasa"], 365)
            for _, r in df_raw.iterrows()
            if r["capital"] > 0 and r["dias"] > 0
        )
        exceso          = total_int_liq - total_int_corr
        pct_exceso      = (exceso / total_int_corr * 100) if total_int_corr > 0 else 0

        alertas.append({
            "nivel": "roja",
            "titulo": f"🚨 BASE DE CÁLCULO INCORRECTA — Se usaron {base_liq} días en vez de 365",
            "detalle": (
                f"El Art. 11 de la Ley N° 18.010 exige base de 365 días. "
                f"El uso de {base_liq} días genera un exceso de **{fmt_clp(exceso)}** "
                f"({pct_exceso:.2f}%) sobre el total de intereses. "
                f"Factor de exceso: {365/base_liq:.4f}x"
            ),
        })
    return alertas


def generar_escrito(
    alertas: list[dict],
    meta: dict,
    df_auditado: pd.DataFrame,
    abogado: str,
    ejecutado: str,
    ciudad: str,
) -> str:
    """Genera el texto del escrito de observaciones."""
    hoy    = datetime.now().strftime("%d de %B de %Y")
    rol    = meta.get("rol", "[ROL]")
    tri    = meta.get("tribunal", "[TRIBUNAL]")
    cara   = meta.get("caratula", "[CARÁTULA]")

    alertas_error = [a for a in alertas if a["nivel"] == "roja"]
    alertas_adv   = [a for a in alertas if a["nivel"] == "amarilla"]

    if not alertas_error and not alertas_adv:
        fundamentos = "\n   Que revisada la liquidación no se advierten errores en los puntos analizados."
    else:
        lines = []
        n = 0
        for a in alertas_error + alertas_adv:
            n += 1
            # Limpiar markdown del detalle
            detalle = re.sub(r"\*\*(.+?)\*\*", r"\1", a["detalle"])
            lines.append(f"\n   {n}°. {a['titulo'].upper()}\n\n   {detalle}\n")
        fundamentos = "".join(lines)

    total_liq  = df_auditado["Interés liquidado ($)"].sum()   if not df_auditado.empty else 0
    total_corr = df_auditado["Interés correcto 365 ($)"].sum() if not df_auditado.empty else 0
    diff_total = total_liq - total_corr

    escrito = f"""OBSERVACIONES A LA LIQUIDACIÓN DE CRÉDITO
(Artículo 510 del Código de Procedimiento Civil)

                                    {ciudad.upper()}, {hoy}

{tri.upper() if tri else "[TRIBUNAL]"}
CAUSA ROL N° {rol}
CARÁTULA: {cara}

{ejecutado or "[EJECUTADO]"}, representado por su abogado patrocinante {abogado or "[ABOGADO]"},
a S.S. respetuosamente expone:

I. ANTECEDENTES

   Que con fecha reciente fue practicada liquidación de crédito en la presente causa.
   Que de conformidad con lo dispuesto en el artículo 510 del Código de Procedimiento Civil,
   vengo en formular las presentes observaciones a dicha liquidación, por cuanto adolece de
   los siguientes errores de cálculo y/o de base legal:

II. FUNDAMENTOS DE LA OBJECIÓN
{fundamentos}
III. CUANTIFICACIÓN DEL PERJUICIO

   Intereses liquidados por el tribunal:      {fmt_clp(total_liq)}
   Intereses correctos (base 365 días):       {fmt_clp(total_corr)}
   Diferencia a favor del ejecutado:          {fmt_clp(abs(diff_total))}

IV. SOLICITUD

   ÚNICO: Acoger las presentes observaciones, declarar que la liquidación no se ajusta a
   derecho en los puntos señalados, y ordenar que se practique una nueva liquidación
   corrigiendo los errores indicados, conforme a la Ley N° 18.010 y demás disposiciones.

POR TANTO, en mérito de lo expuesto y lo dispuesto en el artículo 510 del CPC,

RUEGO A S.S.: Tener por formuladas las presentes observaciones y ordenar la rectificación
de la liquidación en los términos señalados.

_________________________________
{abogado or "[Nombre del Abogado]"}
Abogado Patrocinante
"""
    return escrito


# ─────────────────────────────────────────────
#  RENDER DE ALERTAS
# ─────────────────────────────────────────────

def render_alerta(alerta: dict):
    nivel   = alerta["nivel"]
    titulo  = alerta["titulo"]
    detalle = alerta["detalle"]
    css_cls = {"roja": "alerta-roja", "amarilla": "alerta-amarilla", "verde": "alerta-verde"}.get(nivel, "alerta-azul")
    st.markdown(
        f'<div class="{css_cls}"><strong>{titulo}</strong><br>{detalle}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
#  RENDER PRINCIPAL
# ─────────────────────────────────────────────

if uploaded_file is None:
    # Pantalla de bienvenida
    st.markdown('<div class="alerta-azul">👈 Cargue un PDF de liquidación en la barra lateral para comenzar la auditoría.</div>', unsafe_allow_html=True)

    with st.expander("¿Qué errores detecta esta herramienta?", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**1. Base de cálculo 360 vs 365 días**
El Art. 11 de la Ley 18.010 exige 365 días.
Usar 360 genera ~1.39% de exceso en todos los intereses.

**2. Tasa variable CMF**
La CMF publica tasa nueva el día 15 de cada mes.
Aplicar una tasa fija a períodos largos es incorrecto.

**3. Comisión Fija Única sobre base incorrecta**
Detecta si el saldo insoluto usado para calcular la
comisión corresponde a deuda anterior ya consignada.
""")
        with col2:
            st.markdown("""
**4. Errores aritméticos**
Verifica que Interés = Capital × Días × (Tasa / base).

**5. Anatocismo**
Detecta si se calculan intereses sobre intereses
(Art. 9, Ley 18.010).

**6. Partidas no sentenciadas**
Comisiones u otros ítems sin respaldo en sentencia.
""")
    st.stop()

# ── Procesar PDF ──
file_bytes = uploaded_file.read()

with st.spinner("Extrayendo datos del PDF..."):
    df_raw, meta = extraer_tabla_pdf(file_bytes)

# Extraer texto completo para búsqueda de comisión
with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
    texto_pdf = "\n".join(page.extract_text() or "" for page in pdf.pages)

# ── Metadatos ──
st.markdown('<div class="seccion-titulo">Identificación de la causa</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown(f"**ROL:** {meta.get('rol', 'No detectado')}")
c2.markdown(f"**Fecha:** {meta.get('fecha_liq', 'No detectada')}")
c3.markdown(f"**Tribunal:** {meta.get('tribunal', 'No detectado')}")
if meta.get("caratula"):
    st.markdown(f"**Carátula:** {meta.get('caratula')}")

# ── Verificar extracción ──
if df_raw.empty:
    st.markdown("""
<div class="alerta-amarilla">
<strong>No se pudo extraer la tabla automáticamente.</strong><br>
El PDF puede estar escaneado como imagen o tener un formato no estándar.
Intente con un PDF descargado directamente desde el sistema PJUD (no escaneado).
</div>
""", unsafe_allow_html=True)

    # Permitir entrada manual
    st.markdown('<div class="seccion-titulo">Ingreso manual de datos</div>', unsafe_allow_html=True)
    st.info("Ingrese los datos manualmente en el editor de abajo.")

    df_manual = pd.DataFrame(columns=["numero","fecha_mora","capital","dias","tasa","interes_liq"])
    df_raw = st.data_editor(
        df_manual,
        num_rows="dynamic",
        column_config={
            "numero":     st.column_config.TextColumn("N° Factura"),
            "fecha_mora": st.column_config.TextColumn("Fecha mora"),
            "capital":    st.column_config.NumberColumn("Capital ($)", format="%.0f"),
            "dias":       st.column_config.NumberColumn("Días mora"),
            "tasa":       st.column_config.NumberColumn("Tasa CMF (%)"),
            "interes_liq":st.column_config.NumberColumn("Interés liquidado ($)", format="%.0f"),
        },
        hide_index=True,
        use_container_width=True,
    )
    if df_raw.empty:
        st.stop()

# ── Tabla extraída ──
st.markdown('<div class="seccion-titulo">Tabla extraída del PDF</div>', unsafe_allow_html=True)

df_display = df_raw.copy()
for col in ["capital", "interes_liq", "consig", "capital_am"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(lambda x: fmt_clp(x) if isinstance(x, (int, float)) else x)

st.dataframe(df_display, use_container_width=True, hide_index=True)

# ── Auditoría ──
st.markdown('<div class="seccion-titulo">Re-cálculo del auditor (base 365 días)</div>', unsafe_allow_html=True)

df_auditado, alertas_calc = auditar(df_raw, base_liquidacion)
alertas_base  = auditar_base_dias(df_raw, base_liquidacion)
alertas_com   = auditar_comision(df_raw, texto_pdf)
todas_alertas = alertas_base + alertas_com + alertas_calc

# Colorear tabla auditada
def colorear_fila(row):
    if row["Estado"] == "✗ Error":
        return ["background-color: #fce8e8"] * len(row)
    elif row["Estado"] == "⚠ Diferencia":
        return ["background-color: #fef3e2"] * len(row)
    return [""] * len(row)

cols_fmt = {
    "Capital ($)":              "{:,.0f}",
    "Interés liquidado ($)":    "{:,.0f}",
    "Interés correcto 365 ($)": "{:,.0f}",
    "Diferencia ($)":           "{:,.0f}",
}

if not df_auditado.empty:
    df_styled = (
        df_auditado.style
        .apply(colorear_fila, axis=1)
        .format(cols_fmt)
    )
    st.dataframe(df_styled, use_container_width=True, hide_index=True)

# ── Métricas resumen ──
if not df_auditado.empty:
    total_liq  = df_auditado["Interés liquidado ($)"].sum()
    total_corr = df_auditado["Interés correcto 365 ($)"].sum()
    diff_total = total_liq - total_corr
    n_errores  = len([a for a in todas_alertas if a["nivel"] == "roja"])

    st.markdown('<div class="seccion-titulo">Métricas de la auditoría</div>', unsafe_allow_html=True)
    mc1, mc2, mc3, mc4 = st.columns(4)

    with mc1:
        st.metric("Intereses liquidados", fmt_clp(total_liq))
    with mc2:
        st.metric("Intereses correctos (365d)", fmt_clp(total_corr))
    with mc3:
        color = "normal" if diff_total <= 0 else "inverse"
        st.metric("Exceso cobrado", fmt_clp(abs(diff_total)), delta=f"{diff_total/total_corr*100:.2f}%" if total_corr else "—", delta_color=color)
    with mc4:
        st.metric("Alertas rojas", str(n_errores), delta="errores críticos", delta_color="inverse" if n_errores > 0 else "normal")

# ── Panel de discrepancias ──
st.markdown('<div class="seccion-titulo">Panel de discrepancias detectadas</div>', unsafe_allow_html=True)

if not todas_alertas:
    st.markdown('<div class="alerta-verde">✓ No se detectaron discrepancias en los puntos analizados.</div>', unsafe_allow_html=True)
else:
    # Ordenar: rojas primero
    rojas     = [a for a in todas_alertas if a["nivel"] == "roja"]
    amarillas = [a for a in todas_alertas if a["nivel"] == "amarilla"]
    for a in rojas + amarillas:
        render_alerta(a)

# ── Generador del escrito ──
st.markdown('<div class="seccion-titulo">Escrito de observaciones — Art. 510 CPC</div>', unsafe_allow_html=True)

if not abogado or not ejecutado:
    st.markdown('<div class="alerta-azul">Complete el nombre del abogado y del ejecutado en la barra lateral para generar el escrito.</div>', unsafe_allow_html=True)
else:
    escrito = generar_escrito(
        todas_alertas, meta, df_auditado,
        abogado, ejecutado, ciudad
    )
    st.markdown(f'<div class="escrito-box">{escrito}</div>', unsafe_allow_html=True)

    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    with col_btn1:
        st.download_button(
            label="📥 Descargar .txt",
            data=escrito.encode("utf-8"),
            file_name=f"observaciones_{meta.get('rol','causa').replace('-','_')}.txt",
            mime="text/plain",
        )
    with col_btn2:
        st.download_button(
            label="📋 Copiar como .txt",
            data=escrito.encode("utf-8"),
            file_name="escrito.txt",
            mime="text/plain",
        )

# ── Footer ──
st.markdown("---")
st.markdown(
    "<small style='color:#9a9690;'>Auditor de Liquidaciones · Ley N° 18.010 · Art. 510 CPC · "
    "Solo para uso profesional · Verifique siempre las tasas en "
    "<a href='https://tasas.cmfchile.cl' target='_blank'>cmfchile.cl</a></small>",
    unsafe_allow_html=True,
)