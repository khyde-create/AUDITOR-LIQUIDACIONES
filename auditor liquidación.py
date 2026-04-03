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
    st.markdown("### 📄 Sentencia (opcional)")
    uploaded_sentencia = st.file_uploader(
        "Cargar PDF de la sentencia",
        type=["pdf"],
        help="Opcional. Si se sube, la herramienta verifica que la liquidación respete lo ordenado en la sentencia.",
    )
    if uploaded_sentencia:
        st.caption("✓ Sentencia cargada — se activará la verificación legal.")
    else:
        st.caption("Sin sentencia — solo se auditarán los números.")
    st.caption("La base de días (360 o 365) se detecta automáticamente desde el PDF y se verifica su consistencia.")
    base_liquidacion = 360  # valor por defecto, se sobreescribe con detección automática

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


def extraer_meta(texto: str) -> dict:
    """Extrae metadatos del encabezado del PDF."""
    meta = {}
    for linea in texto.split("\n"):
        ll = linea.lower().strip()
        if not linea.strip():
            continue
        if "rol" in ll and ":" in linea and not meta.get("rol"):
            val = linea.split(":", 1)[-1].strip()
            if val:
                meta["rol"] = val
        if ("carátula" in ll or "caratula" in ll) and ":" in linea and not meta.get("caratula"):
            meta["caratula"] = linea.split(":", 1)[-1].strip()
        if "juzgado" in ll and not meta.get("tribunal"):
            meta["tribunal"] = linea.strip()
        if "santiago" in ll and not meta.get("fecha_liq"):
            meta["fecha_liq"] = linea.strip()
    return meta


def extraer_tabla_estrategia1(pdf) -> list[list]:
    """
    Estrategia 1: extract_tables() estándar de pdfplumber.
    Funciona cuando la tabla tiene bordes bien definidos.
    """
    for page in pdf.pages:
        for table in (page.extract_tables() or []):
            if not table or len(table) < 3:
                continue
            for row_i, row in enumerate(table):
                row_text = " ".join(str(c).lower() for c in row if c)
                if any(kw in row_text for kw in ["capital", "días", "mora", "tasa", "interés"]):
                    return table[row_i:]  # encabezado + datos
    return []


def extraer_tabla_estrategia2(pdf) -> list[list]:
    """
    Estrategia 2: extract_table con configuración laxa de bordes.
    Funciona con tablas que tienen líneas tenues o sin bordes.
    """
    settings = {
        "vertical_strategy":   "text",
        "horizontal_strategy": "text",
        "snap_tolerance":      5,
        "join_tolerance":      5,
        "edge_min_length":     10,
        "min_words_vertical":  2,
        "min_words_horizontal":1,
        "keep_blank_chars":    False,
        "text_tolerance":      5,
    }
    for page in pdf.pages:
        try:
            table = page.extract_table(settings)
            if table and len(table) > 3:
                for row_i, row in enumerate(table):
                    row_text = " ".join(str(c).lower() for c in row if c)
                    if any(kw in row_text for kw in ["capital", "días", "mora", "tasa"]):
                        return table[row_i:]
        except Exception:
            continue
    return []


def limpiar_monto_pdf(texto: str) -> float:
    """
    Limpia montos con espacios internos y $ al final.
    Ej: '7 76.475 $' → 776475.0
        '1 .244.145 $' → 1244145.0
        '9 8.768 $' → 98768.0
    """
    if not texto:
        return 0.0
    # Quitar $ y espacios, luego unir dígitos separados por espacio
    s = str(texto).replace("$", "").strip()
    # Unir números separados por espacios (ej: "7 76.475" → "776.475")
    partes = s.split()
    s = "".join(partes)
    # Ahora limpiar puntos de miles y comas decimales
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def extraer_tabla_estrategia3(texto: str) -> list:
    """
    Parser para liquidaciones chilenas donde cada campo ocupa su propia línea.
    Formato real extraído por pdfplumber:

        178039
        24/12/2022
        7 76.475 $
        28/07/2023
        216
        21,20%
        saldo 178039
        29/07/2023
        9 8.768 $
        27/05/2025
        668
        21,92%

    Agrupa líneas en bloques de 6 y reconstruye cada factura.
    """
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]

    patron_num    = re.compile(r"^\d{5,7}$")
    patron_saldo  = re.compile(r"^saldo\s+(\d{5,7})$", re.IGNORECASE)
    patron_fecha  = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
    patron_dias   = re.compile(r"^\d{2,4}$")
    patron_tasa   = re.compile(r"^[\d.,]+\s*%$")
    patron_monto  = re.compile(r"^[\d\s.,]+\$?$")

    # Encontrar el inicio de la tabla buscando el primer número de factura
    inicio = 0
    for i, l in enumerate(lineas):
        if patron_num.match(l):
            inicio = i
            break

    registros_principales = {}  # num → dict
    registros_saldo       = {}  # num → dict

    i = inicio
    while i < len(lineas):
        linea = lineas[i]

        # ── Fila principal: empieza con número de 5-7 dígitos ──
        if patron_num.match(linea):
            num = linea
            # Leer los siguientes campos en orden
            campos = []
            j = i + 1
            while j < len(lineas) and len(campos) < 5:
                l = lineas[j]
                # Parar si encontramos otro número de factura o "saldo"
                if patron_num.match(l) or patron_saldo.match(l):
                    break
                campos.append(l)
                j += 1

            if len(campos) >= 5:
                fecha_mora = campos[0] if patron_fecha.match(campos[0]) else ""
                capital    = limpiar_monto_pdf(campos[1])
                fecha_liq  = campos[2] if patron_fecha.match(campos[2]) else ""
                dias_str   = campos[3]
                tasa_str   = campos[4]

                dias = int(dias_str) if patron_dias.match(dias_str) else 0
                tasa_raw = tasa_str.replace("%","").replace(",",".").strip()
                try:
                    tasa = float(tasa_raw)
                except ValueError:
                    tasa = 0.0

                if capital > 0 and dias > 0:
                    registros_principales[num] = {
                        "numero":      num,
                        "fecha_mora":  fecha_mora,
                        "capital":     capital,
                        "fecha_liq":   fecha_liq,
                        "dias":        dias,
                        "tasa":        tasa,
                        "factor_dia":  0.0,
                        "interes_liq": 0.0,
                        "consig":      0.0,
                        "capital_am":  0.0,
                        "dias_p1":     dias,
                        "tasa_p1":     tasa,
                        "interes_p1":  0.0,
                        "tiene_saldo": False,
                        "saldo_capital": 0.0,
                        "dias_p2":     0,
                        "tasa_p2":     0.0,
                        "interes_p2":  0.0,
                    }
                i = j
                continue

        # ── Fila de saldo: empieza con "saldo NNNNN" ──
        ms = patron_saldo.match(linea)
        if ms:
            num = ms.group(1)
            campos = []
            j = i + 1
            while j < len(lineas) and len(campos) < 5:
                l = lineas[j]
                if patron_num.match(l) or patron_saldo.match(l):
                    break
                campos.append(l)
                j += 1

            if len(campos) >= 5:
                saldo_cap  = limpiar_monto_pdf(campos[1])
                dias_str   = campos[3]
                tasa_str   = campos[4]
                dias2 = int(dias_str) if patron_dias.match(dias_str) else 0
                tasa_raw = tasa_str.replace("%","").replace(",",".").strip()
                try:
                    tasa2 = float(tasa_raw)
                except ValueError:
                    tasa2 = 0.0

                registros_saldo[num] = {
                    "saldo_capital": saldo_cap,
                    "dias_p2":       dias2,
                    "tasa_p2":       tasa2,
                    "interes_p2":    0.0,
                }
                i = j
                continue

        i += 1

    if not registros_principales:
        return []

    # Combinar principal + saldo
    resultado = []
    for num, p in registros_principales.items():
        s = registros_saldo.get(num, {})
        if s:
            p["tiene_saldo"]   = True
            p["saldo_capital"] = s.get("saldo_capital", 0.0)
            p["dias_p2"]       = s.get("dias_p2", 0)
            p["tasa_p2"]       = s.get("tasa_p2", 0.0)
            p["interes_p2"]    = s.get("interes_p2", 0.0)
        resultado.append(p)

    return resultado


def extraer_tabla_estrategia4(texto: str) -> list:
    """
    Estrategia 4: fallback flexible.
    Extrae cualquier línea con patrón: N°factura fecha $monto fecha días tasa% factor $interés
    Sin distinguir principal/saldo — para PDFs con formato muy distinto.
    """
    filas = []
    patron = re.compile(
        r"(\d{5,7})\s+"
        r"(\d{1,2}/\d{1,2}/\d{2,4})\s+"
        r"\$?\s*([\d.,]+)\s+"
        r"(\d{1,2}/\d{1,2}/\d{2,4})?\s*"
        r"(\d{2,4})\s+"
        r"([\d.,]+)\s*%?\s*"
        r"(?:[\d.,]+\s*%?\s*)?"
        r"\$?\s*([\d.,]+)"
    )
    for linea in texto.split("\n"):
        m = patron.search(linea.strip())
        if m:
            cap = limpiar_numero(m.group(3))
            dias = int(m.group(5) or 0)
            if cap > 0 and dias > 0:
                filas.append({
                    "numero":      m.group(1),
                    "fecha_mora":  m.group(2),
                    "capital":     cap,
                    "fecha_liq":   m.group(4) or "",
                    "dias":        dias,
                    "tasa":        limpiar_numero(m.group(6)),
                    "factor_dia":  0.0,
                    "interes_liq": limpiar_numero(m.group(7)),
                    "consig":      0.0,
                    "capital_am":  0.0,
                    "tiene_saldo": False,
                    "saldo_capital": 0.0,
                    "dias_p1": dias,
                    "tasa_p1": limpiar_numero(m.group(6)),
                    "interes_p1": limpiar_numero(m.group(7)),
                    "dias_p2": 0,
                    "tasa_p2": 0.0,
                    "interes_p2": 0.0,
                })
    return filas


def tabla_a_dataframe(tabla: list[list], es_dict=False) -> pd.DataFrame:
    """Convierte la tabla extraída a DataFrame normalizado."""
    if es_dict:
        return pd.DataFrame(tabla)

    if not tabla or len(tabla) < 2:
        return pd.DataFrame()

    headers = tabla[0]
    col_map = {}
    for campo, opciones in COLS_BUSCAR.items():
        idx = detectar_col(headers, opciones)
        if idx is not None:
            col_map[campo] = idx

    registros = []
    for fila in tabla[1:]:
        if not fila or not any(c for c in fila):
            continue

        def get(campo):
            idx = col_map.get(campo)
            if idx is None or idx >= len(fila):
                return None
            return fila[idx]

        num = str(get("numero") or "").strip()
        if not num or num.lower() in ["n°", "n", ""]:
            continue

        try:
            cap = limpiar_numero(get("capital"))
            dias = int(limpiar_numero(get("dias")) or 0)
            if cap <= 0 and dias <= 0:
                continue

            registros.append({
                "numero":     num,
                "fecha_mora": str(get("fecha_mora") or "").strip(),
                "capital":    cap,
                "fecha_liq":  str(get("fecha_liq") or "").strip(),
                "dias":       dias,
                "tasa":       limpiar_numero(get("tasa")),
                "factor_dia": limpiar_numero(get("factor_dia")),
                "interes_liq":limpiar_numero(get("interes")),
                "consig":     abs(limpiar_numero(get("consig_neg"))),
                "capital_am": limpiar_numero(get("capital_am")),
            })
        except Exception:
            continue

    return pd.DataFrame(registros)


def extraer_tabla_pdf(file_bytes: bytes) -> tuple[pd.DataFrame, dict]:
    """
    Extrae la tabla principal usando 4 estrategias en cascada.
    Retorna (DataFrame, metadatos).
    """
    meta = {}
    texto_completo = ""

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            texto_completo += (page.extract_text() or "") + "\n"

        meta = extraer_meta(texto_completo)

        # Estrategia 1: tablas con bordes
        tabla = extraer_tabla_estrategia1(pdf)
        if tabla and len(tabla) > 2:
            df = tabla_a_dataframe(tabla)
            if not df.empty and len(df) >= 2:
                df.attrs["estrategia"] = "1 — Detección de bordes"
                return df, meta

        # Estrategia 2: tablas sin bordes
        tabla = extraer_tabla_estrategia2(pdf)
        if tabla and len(tabla) > 2:
            df = tabla_a_dataframe(tabla)
            if not df.empty and len(df) >= 2:
                df.attrs["estrategia"] = "2 — Detección por texto"
                return df, meta

    # Estrategia 3: parser calibrado para liquidaciones chilenas
    filas3 = extraer_tabla_estrategia3(texto_completo)
    if filas3 and len(filas3) >= 2:
        df = pd.DataFrame(filas3)
        df.attrs["estrategia"] = "3 — Parser calibrado (principal + saldo)"
        return df, meta

    # Estrategia 4: fallback flexible
    filas4 = extraer_tabla_estrategia4(texto_completo)
    if filas4 and len(filas4) >= 2:
        df = pd.DataFrame(filas4)
        df.attrs["estrategia"] = "4 — Parser flexible"
        return df, meta

    return pd.DataFrame(), meta


# ─────────────────────────────────────────────
#  AUDITORÍA
# ─────────────────────────────────────────────

def auditar(df: pd.DataFrame, base_liq: int) -> tuple[pd.DataFrame, list[dict]]:
    """
    Audita la liquidación verificando cada período por separado.
    Maneja tanto facturas de un período como de dos períodos (principal + saldo).
    Solo marca error si el número no cuadra con la base declarada.
    """
    alertas = []
    filas   = []

    tiene_dos_periodos = "dias_p1" in df.columns and "dias_p2" in df.columns

    for _, row in df.iterrows():
        num = row.get("numero", "")
        cap = row.get("capital", 0)

        if tiene_dos_periodos:
            dias1    = row.get("dias_p1", row.get("dias", 0))
            tasa1    = row.get("tasa_p1", row.get("tasa", 0))
            int1_liq = row.get("interes_p1", row.get("interes_liq", 0))
            saldo_cap= row.get("saldo_capital", 0)
            dias2    = row.get("dias_p2", 0)
            tasa2    = row.get("tasa_p2", 0)
            int2_liq = row.get("interes_p2", 0)
            tiene_p2 = row.get("tiene_saldo", False) and dias2 > 0
        else:
            dias1    = row.get("dias", 0)
            tasa1    = row.get("tasa", 0)
            int1_liq = row.get("interes_liq", 0)
            saldo_cap= 0
            dias2 = tasa2 = int2_liq = 0
            tiene_p2 = False

        if cap <= 0 or dias1 <= 0 or tasa1 <= 0:
            continue

        # ── Período 1 ──
        int1_calc = calcular_interes(cap, dias1, tasa1, base_liq)
        diff1     = int1_liq - int1_calc
        tol1      = max(int1_liq * 0.015, 10)

        estado1 = "✓ OK"
        if abs(diff1) > tol1:
            estado1 = "✗ Error P1"
            alertas.append({
                "nivel": "roja",
                "titulo": f"Factura {num} — Error aritmético en período 1",
                "detalle": (
                    f"Capital: {fmt_clp(cap)} | Días: {dias1} | Tasa: {tasa1}% | "
                    f"Liquidado: {fmt_clp(int1_liq)} | "
                    f"Calculado (base {base_liq}d): {fmt_clp(int1_calc)} | "
                    f"Diferencia: {fmt_clp(abs(diff1))}"
                ),
            })

        # ── Período 2 (saldo) ──
        int2_calc = 0.0
        diff2     = 0.0
        estado2   = "—"

        if tiene_p2 and saldo_cap > 0 and tasa2 > 0:
            int2_calc = calcular_interes(saldo_cap, dias2, tasa2, base_liq)
            diff2     = int2_liq - int2_calc
            tol2      = max(int2_liq * 0.015, 10)
            estado2   = "✓ OK"

            if abs(diff2) > tol2:
                estado2 = "✗ Error P2"
                alertas.append({
                    "nivel": "roja",
                    "titulo": f"Factura {num} — Error aritmético en período 2 (saldo)",
                    "detalle": (
                        f"Saldo capital: {fmt_clp(saldo_cap)} | Días: {dias2} | Tasa: {tasa2}% | "
                        f"Liquidado: {fmt_clp(int2_liq)} | "
                        f"Calculado (base {base_liq}d): {fmt_clp(int2_calc)} | "
                        f"Diferencia: {fmt_clp(abs(diff2))}"
                    ),
                })

            # ── Detectar anatocismo ──
            # Si saldo_capital ≈ interés del período 1, es interés sobre interés
            if int1_liq > 0 and abs(saldo_cap - int1_liq) / max(int1_liq, 1) < 0.02:
                alertas.append({
                    "nivel": "roja",
                    "titulo": f"🚨 Factura {num} — Anatocismo (Art. 9, Ley 18.010)",
                    "detalle": (
                        f"El capital del período 2 ({fmt_clp(saldo_cap)}) coincide con "
                        f"el interés del período 1 ({fmt_clp(int1_liq)}), lo que indica "
                        f"que se están calculando intereses sobre intereses. "
                        f"Esto está prohibido por el Art. 9 de la Ley N° 18.010."
                    ),
                })

        int_total_liq  = int1_liq + int2_liq
        int_total_calc = int1_calc + int2_calc

        fila = {
            "N° Factura":           num,
            "Fecha mora":           row.get("fecha_mora", ""),
            "Capital ($)":          cap,
            f"Días P1 | Tasa P1":   f"{dias1} | {tasa1}%",
            f"Interés P1 liq ($)":  int1_liq,
            f"Interés P1 calc ({base_liq}d) ($)": int1_calc,
            "Estado P1":            estado1,
        }
        if tiene_p2:
            fila.update({
                "Días P2 | Tasa P2":  f"{dias2} | {tasa2}%",
                "Interés P2 liq ($)": int2_liq,
                f"Interés P2 calc ({base_liq}d) ($)": int2_calc,
                "Estado P2":          estado2,
                "Total interés liq ($)":  int_total_liq,
                "Total interés calc ($)": int_total_calc,
                "Diferencia total ($)":   int_total_liq - int_total_calc,
            })

        filas.append(fila)

    return pd.DataFrame(filas), alertas


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


def auditar_base_dias(df_raw: pd.DataFrame, base_liq: int, texto_pdf: str) -> list[dict]:
    """
    Verifica DOS cosas sobre la base de días:
    1. ¿El tribunal declara expresamente qué base usa?
    2. ¿Es consistente en todas las filas?
    No penaliza el uso de 360 si está declarado y es consistente.
    """
    alertas = []

    # ── 1. ¿Lo declara expresamente? ──
    texto_lower = texto_pdf.lower()
    declara_360 = any(p in texto_lower for p in [
        "360 días", "360 dias", "dividida por 360", "dividido por 360",
        "base 360", "año de 360", "factor de 360",
    ])
    declara_365 = any(p in texto_lower for p in [
        "365 días", "365 dias", "dividida por 365", "dividido por 365",
        "base 365", "año de 365",
    ])

    if not declara_360 and not declara_365:
        alertas.append({
            "nivel": "amarilla",
            "titulo": "Base de días no declarada en la liquidación",
            "detalle": (
                f"La liquidación no indica expresamente qué base de días utiliza "
                f"(360 o 365). Toda liquidación debe declarar este criterio para "
                f"permitir su verificación. La base detectada según los cálculos "
                f"es {base_liq} días."
            ),
        })
    else:
        base_declarada = 360 if declara_360 else 365
        if base_declarada != base_liq:
            alertas.append({
                "nivel": "amarilla",
                "titulo": f"Discrepancia entre base declarada y base aplicada",
                "detalle": (
                    f"La liquidación declara base {base_declarada} días, "
                    f"pero los cálculos detectados corresponden a base {base_liq} días."
                ),
            })

    # ── 2. ¿Es consistente en todas las filas? ──
    if df_raw.empty or "capital" not in df_raw.columns:
        return alertas

    inconsistencias = []
    for _, row in df_raw.iterrows():
        cap  = row.get("capital", 0)
        dias = row.get("dias", 0)
        tasa = row.get("tasa", 0)
        int_liq = row.get("interes_liq", 0)
        if cap <= 0 or dias <= 0 or tasa <= 0 or int_liq <= 0:
            continue

        int_360 = calcular_interes(cap, dias, tasa, 360)
        int_365 = calcular_interes(cap, dias, tasa, 365)

        diff_360 = abs(int_liq - int_360)
        diff_365 = abs(int_liq - int_365)

        # Tolerancia del 1% para redondeos
        tolerancia = int_liq * 0.01

        usa_360 = diff_360 <= tolerancia
        usa_365 = diff_365 <= tolerancia

        if not usa_360 and not usa_365:
            inconsistencias.append({
                "factura": row.get("numero", "?"),
                "int_liq": int_liq,
                "int_360": int_360,
                "int_365": int_365,
                "diff_360": diff_360,
                "diff_365": diff_365,
            })

    if inconsistencias:
        detalle_items = " | ".join(
            f"Factura {i['factura']}: liquidado {fmt_clp(i['int_liq'])} "
            f"(360d→{fmt_clp(i['int_360'])}, 365d→{fmt_clp(i['int_365'])})"
            for i in inconsistencias[:3]
        )
        alertas.append({
            "nivel": "roja",
            "titulo": f"🚨 INCONSISTENCIA EN BASE DE DÍAS — {len(inconsistencias)} fila(s) no cuadran con ninguna base",
            "detalle": (
                f"Las siguientes facturas no corresponden ni a base 360 ni a base 365, "
                f"lo que sugiere errores aritméticos o cambios de criterio no declarados. "
                f"{detalle_items}"
            ),
        })
    else:
        # Verificar que todas usen LA MISMA base
        bases_usadas = set()
        for _, row in df_raw.iterrows():
            cap  = row.get("capital", 0)
            dias = row.get("dias", 0)
            tasa = row.get("tasa", 0)
            int_liq = row.get("interes_liq", 0)
            if cap <= 0 or dias <= 0 or tasa <= 0 or int_liq <= 0:
                continue
            int_360 = calcular_interes(cap, dias, tasa, 360)
            int_365 = calcular_interes(cap, dias, tasa, 365)
            tol = int_liq * 0.01
            if abs(int_liq - int_360) <= tol:
                bases_usadas.add(360)
            elif abs(int_liq - int_365) <= tol:
                bases_usadas.add(365)

        if len(bases_usadas) > 1:
            alertas.append({
                "nivel": "roja",
                "titulo": "🚨 BASE DE DÍAS MIXTA — Se mezclan 360 y 365 días en distintas filas",
                "detalle": (
                    "La liquidación aplica base 360 en algunas facturas y base 365 en otras, "
                    "lo que constituye un criterio inconsistente. Cualquier base que se use "
                    "debe aplicarse uniformemente a toda la liquidación."
                ),
            })
        elif bases_usadas == {360} and declara_360:
            alertas.append({
                "nivel": "verde",
                "titulo": "✓ Base de días: 360 días declarada y aplicada consistentemente",
                "detalle": (
                    "La liquidación declara expresamente el uso de base 360 días y lo aplica "
                    "de forma consistente en todas las filas. Criterio aceptable."
                ),
            })
        elif bases_usadas == {365}:
            alertas.append({
                "nivel": "verde",
                "titulo": "✓ Base de días: 365 días aplicada consistentemente (Art. 11 Ley 18.010)",
                "detalle": "La liquidación aplica base 365 días en todas las filas. Correcto.",
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
    # Buscar columna de referencia flexible
    col_ref = next((c for c in df_auditado.columns if "según base" in c or "correcto" in c), None)
    total_corr = df_auditado[col_ref].sum() if (col_ref and not df_auditado.empty) else total_liq
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
#  ANÁLISIS DE SENTENCIA
# ─────────────────────────────────────────────

def extraer_texto_pdf(file_bytes: bytes) -> str:
    """Extrae todo el texto de un PDF."""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def analizar_sentencia(texto_sentencia: str, texto_liquidacion: str, df_raw: pd.DataFrame) -> list[dict]:
    """
    Analiza el texto de la sentencia y lo compara con la liquidación.
    Busca: fecha de inicio de intereses, tipo de interés, capital ordenado,
    mención de costas, comisiones u otras partidas.
    Retorna lista de alertas.
    """
    alertas = []
    txt_s = texto_sentencia.lower()
    txt_l = texto_liquidacion.lower()

    # ── 1. FECHA DE INICIO DE INTERESES ──
    # Patrones comunes en sentencias chilenas
    patrones_fecha_interes = [
        r"intereses?\s+(?:a contar|desde|a partir)\s+(?:del?\s+)?(?:día\s+)?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        r"(?:a contar|desde|a partir)\s+(?:del?\s+)?(?:día\s+)?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})[,\s]+(?:con\s+)?(?:los?\s+)?intereses?",
        r"intereses?\s+(?:legales?|corrientes?|moratorios?).*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        r"(?:notificaci[oó]n|presentaci[oó]n|mora|vencimiento)\s+.*?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}).*?(?:fecha\s+de\s+)?(?:mora|vencimiento|notificaci[oó]n)",
    ]

    fecha_sentencia = None
    contexto_fecha  = ""
    for patron in patrones_fecha_interes:
        m = re.search(patron, txt_s)
        if m:
            fecha_sentencia = m.group(1)
            # Obtener contexto (50 chars antes y después)
            start = max(0, m.start() - 60)
            end   = min(len(txt_s), m.end() + 60)
            contexto_fecha = texto_sentencia[start:end].strip().replace("\n", " ")
            break

    # Buscar también frases sin fecha explícita
    frases_inicio = []
    for frase in [
        "desde la mora", "desde la notificación", "desde la presentación",
        "desde que se hizo exigible", "desde el vencimiento",
        "desde que quedó ejecutoriada", "desde la fecha de la sentencia",
        "desde la fecha del contrato",
    ]:
        if frase in txt_s:
            frases_inicio.append(frase)

    if fecha_sentencia:
        # Buscar esa fecha en la liquidación
        fecha_norm = fecha_sentencia.replace("-", "/")
        if fecha_norm in texto_liquidacion:
            alertas.append({
                "nivel": "verde",
                "titulo": "✓ Fecha de inicio de intereses — coincide con la sentencia",
                "detalle": f"La sentencia ordena intereses desde {fecha_sentencia} y la liquidación usa esa misma fecha.",
            })
        else:
            # Buscar fechas en la liquidación para comparar
            fechas_liq = re.findall(r"\d{2}/\d{2}/\d{4}", texto_liquidacion)
            fechas_str = ", ".join(sorted(set(fechas_liq))[:5]) if fechas_liq else "no detectadas"
            alertas.append({
                "nivel": "roja",
                "titulo": "🚨 Fecha de inicio de intereses — no coincide con la sentencia",
                "detalle": (
                    f"La sentencia ordena intereses desde {fecha_sentencia} "
                    f"(contexto: '…{contexto_fecha}…'). "
                    f"Las fechas encontradas en la liquidación son: {fechas_str}. "
                    f"Verifique cuál usa la liquidación como fecha de inicio."
                ),
            })
    elif frases_inicio:
        alertas.append({
            "nivel": "amarilla",
            "titulo": "Fecha de inicio de intereses — detectada por referencia, no por fecha exacta",
            "detalle": (
                f"La sentencia ordena intereses '{frases_inicio[0]}', sin indicar una fecha exacta. "
                f"Verifique que la liquidación haya calculado correctamente ese momento inicial."
            ),
        })
    else:
        alertas.append({
            "nivel": "amarilla",
            "titulo": "Fecha de inicio de intereses — no detectada en la sentencia",
            "detalle": (
                "No se encontró una referencia clara a la fecha de inicio de los intereses "
                "en el texto de la sentencia. Verifique manualmente el párrafo resolutivo."
            ),
        })

    # ── 2. TIPO DE INTERÉS ORDENADO ──
    tipo_interes_sentencia = None
    if any(p in txt_s for p in ["interés máximo convencional", "interes maximo convencional", "tasa máxima"]):
        tipo_interes_sentencia = "máximo convencional"
    elif any(p in txt_s for p in ["interés corriente", "interes corriente", "tasa corriente"]):
        tipo_interes_sentencia = "corriente"
    elif any(p in txt_s for p in ["interés penal", "interes penal", "interés pactado", "interes pactado"]):
        tipo_interes_sentencia = "penal pactado"
    elif any(p in txt_s for p in ["interés legal", "interes legal"]):
        tipo_interes_sentencia = "legal"

    if tipo_interes_sentencia:
        # Verificar que la liquidación use ese tipo
        tipo_en_liq = any(tipo_interes_sentencia.split()[0] in txt_l for _ in [1])
        if tipo_en_liq:
            alertas.append({
                "nivel": "verde",
                "titulo": f"✓ Tipo de interés — la liquidación aplica '{tipo_interes_sentencia}' conforme a la sentencia",
                "detalle": f"La sentencia ordenó interés {tipo_interes_sentencia} y la liquidación lo refleja.",
            })
        else:
            alertas.append({
                "nivel": "amarilla",
                "titulo": f"Tipo de interés — sentencia ordena '{tipo_interes_sentencia}', verificar en liquidación",
                "detalle": (
                    f"La sentencia ordena aplicar interés {tipo_interes_sentencia}. "
                    f"Verifique que la tasa CMF usada corresponda a ese tipo de operación."
                ),
            })

    # ── 3. CAPITAL ORDENADO ──
    # Buscar montos en la sentencia
    montos_sentencia = re.findall(
        r"\$\s*([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)",
        texto_sentencia
    )
    if montos_sentencia and not df_raw.empty:
        capital_liq = df_raw["capital"].sum() if "capital" in df_raw.columns else 0
        for monto_str in montos_sentencia:
            monto = limpiar_numero(monto_str)
            if monto > 100000:  # filtrar montos relevantes
                diff = abs(monto - capital_liq)
                if diff / max(monto, 1) < 0.05:  # coincide dentro del 5%
                    alertas.append({
                        "nivel": "verde",
                        "titulo": "✓ Capital — coincide con el monto de la sentencia",
                        "detalle": f"El capital de la sentencia (${fmt_clp(monto)}) coincide con el capital de la liquidación (${fmt_clp(capital_liq)}).",
                    })
                    break
                elif diff / max(monto, 1) > 0.10:
                    alertas.append({
                        "nivel": "amarilla",
                        "titulo": "Capital — diferencia entre sentencia y liquidación",
                        "detalle": (
                            f"La sentencia menciona un monto de ${fmt_clp(monto)} "
                            f"y el capital en la liquidación es ${fmt_clp(capital_liq)}. "
                            f"Si hay consignaciones parciales la diferencia puede ser correcta — verifique."
                        ),
                    })
                    break

    # ── 4. COSTAS ──
    ordena_costas = any(p in txt_s for p in [
        "con costas", "en costas", "condena en costas", "pago de costas",
    ])
    sin_costas = any(p in txt_s for p in [
        "sin costas", "cada parte pagará", "no se condena en costas",
    ])
    costas_en_liq = any(p in txt_l for p in ["costa", "honorario"])

    if sin_costas and costas_en_liq:
        alertas.append({
            "nivel": "roja",
            "titulo": "🚨 Costas — la sentencia no las ordenó pero la liquidación las incluye",
            "detalle": (
                "La sentencia resolvió sin costas o sin condena en costas, "
                "sin embargo la liquidación incluye un ítem de costas. "
                "Esta partida es improcedente y debe eliminarse."
            ),
        })
    elif ordena_costas and not costas_en_liq:
        alertas.append({
            "nivel": "amarilla",
            "titulo": "Costas — la sentencia las ordenó pero no aparecen en la liquidación",
            "detalle": (
                "La sentencia condenó en costas pero no se detecta ese ítem en la liquidación. "
                "Puede que estén pendientes de tasación, lo que es correcto si aún no se han tasado."
            ),
        })
    elif ordena_costas and costas_en_liq:
        alertas.append({
            "nivel": "verde",
            "titulo": "✓ Costas — la sentencia las ordenó y están incluidas en la liquidación",
            "detalle": "Verifique que exista resolución de tasación aprobada y ejecutoriada.",
        })

    # ── 5. PARTIDAS ADICIONALES NO ORDENADAS ──
    # Buscar comisiones en sentencia
    ordena_comision = any(p in txt_s for p in [
        "comisión", "comision", "cargo fijo", "cargo adicional",
    ])
    comision_en_liq = any(p in txt_l for p in [
        "comisión fija", "comision fija", "cargo fijo",
    ])

    if comision_en_liq and not ordena_comision:
        alertas.append({
            "nivel": "roja",
            "titulo": "🚨 Comisión — no ordenada en sentencia pero incluida en liquidación",
            "detalle": (
                "La liquidación incluye una comisión que no fue ordenada en la sentencia. "
                "Esta partida es improcedente al no tener respaldo en el título ejecutivo ni en la sentencia."
            ),
        })

    return alertas


# ─────────────────────────────────────────────
#  RENDER DE ALERTAS
# ─────────────────────────────────────────────

def render_alerta(alerta: dict):
    nivel   = alerta["nivel"]
    titulo  = alerta["titulo"]
    detalle = alerta["detalle"]
    css_cls = {
        "roja":     "alerta-roja",
        "amarilla": "alerta-amarilla",
        "verde":    "alerta-verde",
        "azul":     "alerta-azul",
    }.get(nivel, "alerta-azul")
    st.markdown(
        f'<div class="{css_cls}"><strong>{titulo}</strong><br>{detalle}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
#  RENDER PRINCIPAL
# ─────────────────────────────────────────────

if uploaded_file is None:
    st.markdown('<div class="alerta-azul">👈 Cargue un PDF de liquidación en la barra lateral para comenzar. La sentencia es opcional — si la sube, se activa la verificación legal.</div>', unsafe_allow_html=True)

    with st.expander("¿Qué audita esta herramienta?", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**Solo con la liquidación:**
1. Base de días (360 vs 365) — consistencia y declaración expresa
2. Errores aritméticos por factura
3. Comisión Fija Única sobre base incorrecta
4. Tasa variable CMF en períodos largos
5. Anatocismo (interés sobre interés)
""")
        with col2:
            st.markdown("""
**Agregando la sentencia (opcional):**
6. Fecha de inicio de intereses — ¿coincide con lo ordenado?
7. Tipo de interés — ¿corriente, máximo o penal?
8. Capital base — ¿coincide con el fijado en sentencia?
9. Costas — ¿fueron ordenadas? ¿están tasadas?
10. Partidas no sentenciadas (comisiones, cargos)
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

# ── Detectar base automáticamente desde el texto ──
texto_lower = texto_pdf.lower()
if any(p in texto_lower for p in ["dividida por 360","dividido por 360","360 días","360 dias","base 360"]):
    base_liquidacion = 360
elif any(p in texto_lower for p in ["dividida por 365","dividido por 365","365 días","365 dias","base 365"]):
    base_liquidacion = 365
else:
    # Intentar detectar por los cálculos reales si hay datos
    if not df_raw.empty and "capital" in df_raw.columns:
        votos_360 = votos_365 = 0
        for _, row in df_raw.iterrows():
            cap = row.get("capital",0); dias = row.get("dias",0)
            tasa = row.get("tasa",0);   int_liq = row.get("interes_liq",0)
            if cap<=0 or dias<=0 or tasa<=0 or int_liq<=0: continue
            tol = int_liq * 0.01
            if abs(calcular_interes(cap,dias,tasa,360) - int_liq) <= tol: votos_360 += 1
            if abs(calcular_interes(cap,dias,tasa,365) - int_liq) <= tol: votos_365 += 1
        base_liquidacion = 360 if votos_360 >= votos_365 else 365
    # si no hay datos, queda el default 360
if df_raw.empty:
    st.markdown("""
<div class="alerta-amarilla">
<strong>No se pudo extraer la tabla automáticamente.</strong><br>
Se intentaron 4 métodos de extracción sin éxito. Esto puede ocurrir cuando el PDF
tiene un formato de tabla muy particular. Use el editor manual a continuación para
ingresar los datos — solo necesita las columnas principales.
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

# Mostrar qué estrategia funcionó
estrategia = df_raw.attrs.get("estrategia", "")
if estrategia:
    st.markdown(
        f'<div class="alerta-verde">✓ Extracción exitosa — Método: {estrategia}</div>',
        unsafe_allow_html=True,
    )

df_display = df_raw.copy()
for col in ["capital", "interes_liq", "consig", "capital_am"]:
    if col in df_display.columns:
        df_display[col] = df_display[col].apply(lambda x: fmt_clp(x) if isinstance(x, (int, float)) else x)

st.dataframe(df_display, use_container_width=True, hide_index=True)

# ── Auditoría ──
df_auditado, alertas_calc = auditar(df_raw, base_liquidacion)
alertas_base  = auditar_base_dias(df_raw, base_liquidacion, texto_pdf)
alertas_com   = auditar_comision(df_raw, texto_pdf)

st.markdown(
    f'<div class="seccion-titulo">Re-cálculo del auditor — verificando consistencia con base {base_liquidacion} días</div>',
    unsafe_allow_html=True,
)

# ── Analizar sentencia si fue subida ──
alertas_sentencia = []
texto_sentencia   = ""
if uploaded_sentencia:
    with st.spinner("Analizando sentencia..."):
        sentencia_bytes = uploaded_sentencia.read()
        texto_sentencia = extraer_texto_pdf(sentencia_bytes)
        if texto_sentencia.strip():
            alertas_sentencia = analizar_sentencia(texto_sentencia, texto_pdf, df_raw)
        else:
            st.markdown(
                '<div class="alerta-amarilla">No se pudo extraer texto de la sentencia. '
                'Verifique que el PDF no sea una imagen escaneada.</div>',
                unsafe_allow_html=True,
            )

todas_alertas = alertas_base + alertas_com + alertas_calc + alertas_sentencia

# Colorear tabla auditada
def colorear_fila(row):
    estados = [str(v) for k, v in row.items() if "Estado" in str(k)]
    if any("Error" in e for e in estados):
        return ["background-color: #fce8e8"] * len(row)
    if any("Diferencia" in e for e in estados):
        return ["background-color: #fef3e2"] * len(row)
    return [""] * len(row)

# Formato dinámico: aplicar formato numérico a todas las columnas con ($)
cols_fmt = {c: "{:,.0f}" for c in df_auditado.columns if "($)" in str(c)}

if not df_auditado.empty:
    df_styled = (
        df_auditado.style
        .apply(colorear_fila, axis=1)
        .format({k: v for k, v in cols_fmt.items() if k in df_auditado.columns})
    )
    st.dataframe(df_styled, use_container_width=True, hide_index=True)

# ── Métricas resumen ──
if not df_auditado.empty:
    # Sumar todas las columnas de interés liquidado
    cols_liq  = [c for c in df_auditado.columns if "liq" in c.lower() and "($)" in c]
    cols_calc = [c for c in df_auditado.columns if "calc" in c.lower() and "($)" in c]
    total_liq  = df_auditado[cols_liq].sum(numeric_only=True).sum()  if cols_liq  else 0
    total_corr = df_auditado[cols_calc].sum(numeric_only=True).sum() if cols_calc else total_liq
    diff_total = total_liq - total_corr
    n_errores  = len([a for a in todas_alertas if a["nivel"] == "roja"])

    st.markdown('<div class="seccion-titulo">Métricas de la auditoría</div>', unsafe_allow_html=True)
    mc1, mc2, mc3, mc4 = st.columns(4)

    with mc1:
        st.metric("Intereses liquidados", fmt_clp(total_liq))
    with mc2:
        st.metric(f"Interés calculado (base {base_liquidacion}d)", fmt_clp(total_corr))
    with mc3:
        color = "normal" if diff_total <= 0 else "inverse"
        st.metric("Exceso cobrado", fmt_clp(abs(diff_total)), delta=f"{diff_total/total_corr*100:.2f}%" if total_corr else "—", delta_color=color)
    with mc4:
        st.metric("Alertas rojas", str(n_errores), delta="errores críticos", delta_color="inverse" if n_errores > 0 else "normal")

# ── Panel de análisis de sentencia ──
if uploaded_sentencia and alertas_sentencia:
    st.markdown('<div class="seccion-titulo">Verificación legal — contraste con la sentencia</div>', unsafe_allow_html=True)
    for a in alertas_sentencia:
        render_alerta(a)
elif uploaded_sentencia:
    st.markdown('<div class="seccion-titulo">Verificación legal — contraste con la sentencia</div>', unsafe_allow_html=True)
    st.markdown('<div class="alerta-azul">No se detectaron discrepancias entre la sentencia y la liquidación en los puntos analizados.</div>', unsafe_allow_html=True)

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