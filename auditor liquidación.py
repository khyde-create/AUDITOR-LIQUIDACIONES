"""
============================================================
  AUDITOR DE LIQUIDACIONES DE CRÉDITO — Art. 510 CPC
  Ley N° 18.010 — LegalTech Chile
============================================================
INSTALACIÓN:
    pip install streamlit pdfplumber pandas

EJECUCIÓN:
    streamlit run auditor_liquidacion.py
============================================================
"""

import re
import io
from datetime import datetime

import pandas as pd
import pdfplumber
import streamlit as st

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Auditor de Liquidaciones — Art. 510 CPC",
    page_icon="⚖️",
    layout="wide",
)

st.markdown("""
<style>
.app-header{background:#1c1a16;color:#fff;padding:1.2rem 1.5rem;border-radius:10px;margin-bottom:1.5rem;}
.app-header h1{font-size:1.4rem;margin:0;font-weight:600;}
.app-header p{font-size:0.78rem;margin:0;opacity:0.5;letter-spacing:0.06em;text-transform:uppercase;}
.alerta-roja{background:#fce8e8;border-left:4px solid #8b1f1f;color:#8b1f1f;padding:.85rem 1rem;border-radius:6px;margin-bottom:.8rem;font-size:.88rem;line-height:1.6;}
.alerta-amarilla{background:#fef3e2;border-left:4px solid #d4820a;color:#7a4a0a;padding:.85rem 1rem;border-radius:6px;margin-bottom:.8rem;font-size:.88rem;line-height:1.6;}
.alerta-verde{background:#eaf3de;border-left:4px solid #2d5a11;color:#2d5a11;padding:.85rem 1rem;border-radius:6px;margin-bottom:.8rem;font-size:.88rem;line-height:1.6;}
.alerta-azul{background:#e8f1fb;border-left:4px solid #1a4f8a;color:#1a4f8a;padding:.85rem 1rem;border-radius:6px;margin-bottom:.8rem;font-size:.88rem;line-height:1.6;}
.seccion-titulo{font-size:.72rem;font-weight:600;color:#9a9690;text-transform:uppercase;letter-spacing:.07em;margin:1.5rem 0 .6rem;padding-bottom:6px;border-bottom:.5px solid rgba(28,26,22,.1);}
.escrito-box{background:#f7f5f0;border:.5px solid rgba(28,26,22,.2);border-radius:8px;padding:1.5rem;font-family:'Courier New',monospace;font-size:.82rem;line-height:1.9;white-space:pre-wrap;max-height:600px;overflow-y:auto;}
</style>
""", unsafe_allow_html=True)

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
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚖️ Liquidación")
    modo = st.radio(
        "Modo de entrada",
        ["📄 Subir PDF", "📋 Pegar texto"],
        help="Si el PDF no se lee bien, use 'Pegar texto': abra el PDF, Ctrl+A, Ctrl+C, pegue aquí.",
    )
    uploaded_file = None
    texto_pegado_sidebar = ""
    if modo == "📄 Subir PDF":
        uploaded_file = st.file_uploader("PDF de la liquidación", type=["pdf"])
    else:
        texto_pegado_sidebar = st.text_area(
            "Pegue el texto del PDF",
            height=280,
            placeholder="Abra el PDF → Ctrl+A → Ctrl+C → Ctrl+V aquí",
        )
        st.caption("Copie todo el contenido del PDF y péguelo aquí.")

    st.markdown("---")
    st.markdown("### 📄 Sentencia (opcional)")
    uploaded_sentencia = st.file_uploader(
        "PDF de la sentencia",
        type=["pdf"],
        help="Si se sube, se verifica que la liquidación respete lo ordenado en sentencia.",
    )

    st.markdown("---")
    st.markdown("### 📝 Datos para el escrito")
    abogado   = st.text_input("Abogado patrocinante")
    ejecutado = st.text_input("Ejecutado (deudor)")
    ciudad    = st.text_input("Ciudad", value="Santiago")

    st.markdown("---")
    st.caption("Solo uso profesional. Verifique tasas en cmfchile.cl")

# ─────────────────────────────────────────────
#  FUNCIONES AUXILIARES
# ─────────────────────────────────────────────

def fmt_clp(n: float) -> str:
    return f"$ {n:,.0f}".replace(",", ".")

def parse_n(s) -> float:
    try:
        return float(str(s).replace(".", "").replace(",", "."))
    except Exception:
        return 0.0

def calcular_interes(capital: float, dias: int, tasa: float, base: int) -> float:
    if base == 0:
        return 0.0
    return capital * dias * (tasa / 100.0 / base)

def limpiar_monto_pdf(texto: str) -> float:
    """
    Convierte montos del PDF del PJUD a float.
    Maneja espacios internos: '$ 7 76.475' → 776475.0
    """
    if not texto:
        return 0.0
    s = str(texto).strip()
    s = s.replace("$", "").replace("(", "").replace(")", "").strip()
    partes = s.split()
    s = "".join(partes)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

# ─────────────────────────────────────────────
#  PARSER PRINCIPAL — PJUD
# ─────────────────────────────────────────────

def parsear_texto_liquidacion(texto: str) -> list:
    """
    Parser calibrado para liquidaciones del PJUD chileno.

    El texto del PDF llega en una sola línea continua con:
    - Montos con espacios internos: '$ 7 76.475'
    - Sin separador entre el interés de una factura y la siguiente: '$ 40.173178538'
    - Filas de saldo: 'saldo 178039 29/07/2023 ...'

    Estrategia:
    1. Extraer los números de factura que existen en el texto
    2. Usarlos como anclas para insertar saltos de línea precisos
    3. Parsear línea por línea con regex
    """
    # ── 1. Encontrar todos los números de factura ──
    nums_factura = list(dict.fromkeys(
        re.findall(r'(?<!\d)(\d{5,7})(?=\s+\d{1,2}/\d{1,2}/\d{4})', texto)
    ))
    if not nums_factura:
        return []

    # ── 2. Insertar \n antes de cada factura y saldo ──
    t = texto
    for num in nums_factura:
        n = re.escape(num)
        fecha = r'\s+\d{1,2}/\d{1,2}/\d{4}'
        # Factura pegada a dígitos previos (fin del interés anterior)
        t = re.sub(r'(\d)(' + n + r')(' + fecha + r')', r'\1\n\2\3', t)
        # "saldo NUM" pegado a dígitos previos
        t = re.sub(r'(\d)(saldo\s+' + n + r')(' + fecha + r')',
                   r'\1\n\2\3', t, flags=re.IGNORECASE)
        # Factura pegada a texto de cabecera (letras o paréntesis)
        t = re.sub(r'([a-zA-ZáéíóúÁÉÍÓÚ\u00f1\u00d1\)])(' + n + r')(' + fecha + r')',
                   r'\1\n\2\3', t)

    # ── 3. Parsear cada línea ──
    patron_p = re.compile(
        r'^(\d{5,7})\s+'
        r'(\d{1,2}/\d{1,2}/\d{4})\s+'
        r'\$\s*([\d\s.,]+?)\s+'
        r'(\d{1,2}/\d{1,2}/\d{4})\s+'
        r'(\d{2,4})\s+'
        r'([\d,]+)\s*%\s+'
        r'[\d,]+\s*%\s+'
        r'\$\s*([\d.,]+)'
    )
    patron_s = re.compile(
        r'^saldo\s+(\d{5,7})\s+'
        r'(\d{1,2}/\d{1,2}/\d{4})\s+'
        r'\$\s*([\d\s.,]+?)\s+'
        r'(\d{1,2}/\d{1,2}/\d{4})\s+'
        r'(\d{2,4})\s+'
        r'([\d,]+)\s*%\s+'
        r'[\d,]+\s*%\s+'
        r'\$\s*([\d.,]+)',
        re.IGNORECASE
    )

    principales = {}
    saldos      = {}

    for linea in t.split("\n"):
        linea = linea.strip()
        if not linea:
            continue

        ms = patron_s.match(linea)
        if ms:
            num = ms.group(1)
            saldos[num] = {
                "saldo_capital": limpiar_monto_pdf(ms.group(3)),
                "dias_p2":       int(ms.group(5)),
                "tasa_p2":       float(ms.group(6).replace(",", ".")),
                "interes_p2":    limpiar_monto_pdf(ms.group(7)),
            }
            continue

        m = patron_p.match(linea)
        if m:
            num = m.group(1)
            cap     = limpiar_monto_pdf(m.group(3))
            interes = limpiar_monto_pdf(m.group(7))
            tasa    = float(m.group(6).replace(",", "."))
            # Guardar solo el de mayor capital (el original, no el saldo)
            if num not in principales or cap > principales[num]["capital"]:
                principales[num] = {
                    "numero":        num,
                    "fecha_mora":    m.group(2),
                    "capital":       cap,
                    "fecha_liq":     m.group(4),
                    "dias":          int(m.group(5)),
                    "tasa":          tasa,
                    "interes_liq":   interes,
                    "dias_p1":       int(m.group(5)),
                    "tasa_p1":       tasa,
                    "interes_p1":    interes,
                    "tiene_saldo":   False,
                    "saldo_capital": 0.0,
                    "dias_p2":       0,
                    "tasa_p2":       0.0,
                    "interes_p2":    0.0,
                    "consig":        0.0,
                    "capital_am":    0.0,
                    "factor_dia":    0.0,
                }

    if not principales:
        return []

    # ── 4. Combinar principal + saldo ──
    resultado = []
    for num in sorted(principales.keys()):
        p = principales[num]
        s = saldos.get(num, {})
        if s:
            p["tiene_saldo"]   = True
            p["saldo_capital"] = s["saldo_capital"]
            p["dias_p2"]       = s["dias_p2"]
            p["tasa_p2"]       = s["tasa_p2"]
            p["interes_p2"]    = s["interes_p2"]
        resultado.append(p)

    return resultado

# ─────────────────────────────────────────────
#  EXTRACCIÓN PDF
# ─────────────────────────────────────────────

def extraer_meta(texto: str) -> dict:
    meta = {}
    for linea in texto.split("\n"):
        ll = linea.lower().strip()
        if "rol" in ll and ":" in linea and not meta.get("rol"):
            val = linea.split(":", 1)[-1].strip()
            if val:
                meta["rol"] = val
        if ("carátula" in ll or "caratula" in ll) and not meta.get("caratula"):
            meta["caratula"] = linea.split(":", 1)[-1].strip()
        if "juzgado" in ll and not meta.get("tribunal"):
            meta["tribunal"] = linea.strip()
        if "santiago" in ll and not meta.get("fecha_liq"):
            meta["fecha_liq"] = linea.strip()
    return meta

def extraer_texto_pdf(file_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def extraer_tabla_pdf(file_bytes: bytes) -> tuple:
    texto = extraer_texto_pdf(file_bytes)
    meta  = extraer_meta(texto)

    # Intentar con pdfplumber primero
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                if not table or len(table) < 3:
                    continue
                for row_i, row in enumerate(table):
                    row_text = " ".join(str(c or "").lower() for c in row)
                    if any(k in row_text for k in ["capital", "días", "mora", "tasa"]):
                        headers = table[row_i]
                        filas = []
                        for fila in table[row_i+1:]:
                            if not fila or not any(c for c in fila):
                                continue
                            # Mapear columnas básicas por posición
                            try:
                                registro = {
                                    "numero":      str(fila[0] or "").strip(),
                                    "fecha_mora":  str(fila[1] or "").strip(),
                                    "capital":     limpiar_monto_pdf(str(fila[2] or "")),
                                    "fecha_liq":   str(fila[3] or "").strip() if len(fila)>3 else "",
                                    "dias":        int(limpiar_monto_pdf(str(fila[4] or "")) or 0) if len(fila)>4 else 0,
                                    "tasa":        limpiar_monto_pdf(str(fila[5] or "")) if len(fila)>5 else 0,
                                    "interes_liq": limpiar_monto_pdf(str(fila[7] or "")) if len(fila)>7 else 0,
                                    "dias_p1": int(limpiar_monto_pdf(str(fila[4] or "")) or 0) if len(fila)>4 else 0,
                                    "tasa_p1": limpiar_monto_pdf(str(fila[5] or "")) if len(fila)>5 else 0,
                                    "interes_p1": limpiar_monto_pdf(str(fila[7] or "")) if len(fila)>7 else 0,
                                    "tiene_saldo": False, "saldo_capital": 0.0,
                                    "dias_p2": 0, "tasa_p2": 0.0, "interes_p2": 0.0,
                                    "consig": 0.0, "capital_am": 0.0, "factor_dia": 0.0,
                                }
                                if registro["capital"] > 0 and registro["dias"] > 0:
                                    filas.append(registro)
                            except Exception:
                                continue
                        if len(filas) >= 3:
                            df = pd.DataFrame(filas)
                            df.attrs["estrategia"] = "pdfplumber (bordes)"
                            return df, meta

    # Fallback: parsear texto directamente
    filas = parsear_texto_liquidacion(texto)
    if filas and len(filas) >= 2:
        df = pd.DataFrame(filas)
        df.attrs["estrategia"] = "parser de texto"
        return df, meta

    return pd.DataFrame(), meta

# ─────────────────────────────────────────────
#  AUDITORÍA
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  UMBRAL MÍNIMO DE RELEVANCIA
# ─────────────────────────────────────────────
# Diferencias menores a este monto no se reportan —
# no tienen relevancia práctica para objetar.
UMBRAL_MINIMO = 1000  # $1.000 pesos


def es_relevante(diff: float) -> bool:
    """Retorna True solo si la diferencia justifica una objeción."""
    return abs(diff) >= UMBRAL_MINIMO


def detectar_base(df: pd.DataFrame, texto: str) -> int:
    tl = texto.lower()
    if any(p in tl for p in ["dividida por 360","dividido por 360","360 días","360 dias","/ 360"]):
        return 360
    if any(p in tl for p in ["dividida por 365","dividido por 365","365 días","365 dias","/ 365"]):
        return 365
    v360 = v365 = 0
    for _, r in df.iterrows():
        cap  = r.get("capital", 0)
        dias = r.get("dias_p1", r.get("dias", 0))
        tasa = r.get("tasa_p1", r.get("tasa", 0))
        il   = r.get("interes_p1", r.get("interes_liq", 0))
        if cap > 0 and dias > 0 and tasa > 0 and il > 0:
            tol = il * 0.015
            if abs(calcular_interes(cap, int(dias), tasa, 360) - il) <= tol:
                v360 += 1
            if abs(calcular_interes(cap, int(dias), tasa, 365) - il) <= tol:
                v365 += 1
    return 360 if v360 >= v365 else 365
    tl = texto.lower()
    if any(p in tl for p in ["dividida por 360", "dividido por 360", "360 días", "360 dias", "/ 360"]):
        return 360
    if any(p in tl for p in ["dividida por 365", "dividido por 365", "365 días", "365 dias", "/ 365"]):
        return 365
    # Detectar por votación en los datos
    v360 = v365 = 0
    for _, r in df.iterrows():
        cap = r.get("capital", 0); dias = r.get("dias_p1", r.get("dias", 0))
        tasa = r.get("tasa_p1", r.get("tasa", 0)); il = r.get("interes_p1", r.get("interes_liq", 0))
        if cap > 0 and dias > 0 and tasa > 0 and il > 0:
            tol = il * 0.015
            if abs(calcular_interes(cap, dias, tasa, 360) - il) <= tol:
                v360 += 1
            if abs(calcular_interes(cap, dias, tasa, 365) - il) <= tol:
                v365 += 1
    return 360 if v360 >= v365 else 365


def auditar(df: pd.DataFrame, base: int) -> tuple:
    alertas = []
    filas   = []
    tiene_p2 = "dias_p2" in df.columns

    for _, row in df.iterrows():
        num  = row.get("numero", "")
        cap  = row.get("capital", 0)
        d1   = row.get("dias_p1", row.get("dias", 0))
        t1   = row.get("tasa_p1", row.get("tasa", 0))
        i1l  = row.get("interes_p1", row.get("interes_liq", 0))

        if cap <= 0 or d1 <= 0 or t1 <= 0:
            continue

        i1c  = calcular_interes(cap, d1, t1, base)
        d1   = int(d1)
        tol1 = max(i1l * 0.015, 10)
        e1   = "✓ OK" if abs(i1l - i1c) <= tol1 else "✗ Error"

        if e1 == "✗ Error" and es_relevante(i1l - i1c):
            alertas.append({
                "nivel": "roja",
                "titulo": f"Factura {num} — Error aritmético período 1",
                "detalle": (
                    f"Capital: {fmt_clp(cap)} | Días: {d1} | Tasa: {t1}% | "
                    f"Liquidado: {fmt_clp(i1l)} | Calculado ({base}d): {fmt_clp(i1c)} | "
                    f"Diferencia: {fmt_clp(abs(i1l-i1c))}"
                ),
            })

        # Período 2
        scap = row.get("saldo_capital", 0) if tiene_p2 else 0
        d2   = row.get("dias_p2", 0) if tiene_p2 else 0
        t2   = row.get("tasa_p2", 0) if tiene_p2 else 0
        i2l  = row.get("interes_p2", 0) if tiene_p2 else 0
        i2c  = 0.0
        e2   = "—"

        if tiene_p2 and scap > 0 and d2 > 0 and t2 > 0:
            i2c  = calcular_interes(scap, int(d2), t2, base)
            tol2 = max(i2l * 0.015, 10)
            e2   = "✓ OK" if abs(i2l - i2c) <= tol2 else "✗ Error"
            if e2 == "✗ Error" and es_relevante(i2l - i2c):
                alertas.append({
                    "nivel": "roja",
                    "titulo": f"Factura {num} — Error aritmético período 2 (saldo)",
                    "detalle": (
                        f"Saldo cap: {fmt_clp(scap)} | Días: {d2} | Tasa: {t2}% | "
                        f"Liquidado: {fmt_clp(i2l)} | Calculado ({base}d): {fmt_clp(i2c)} | "
                        f"Diferencia: {fmt_clp(abs(i2l-i2c))}"
                    ),
                })
            # Anatocismo — saldo_capital ≈ interés_p1 Y diferencia relevante
            diff_ana = abs(scap - i1l)
            if i1l > 0 and diff_ana / max(i1l, 1) < 0.01 and es_relevante(i1l):
                alertas.append({
                    "nivel": "roja",
                    "titulo": f"🚨 Factura {num} — Anatocismo (Art. 9, Ley 18.010)",
                    "detalle": (
                        f"El capital del período 2 ({fmt_clp(scap)}) coincide con el interés "
                        f"del período 1 ({fmt_clp(i1l)}). Se calculan intereses sobre intereses."
                    ),
                })

        fila = {
            "N° Factura":                   num,
            "Fecha mora":                   row.get("fecha_mora", ""),
            "Capital ($)":                  cap,
            f"Días P1 | Tasa":              f"{d1} | {t1}%",
            "Interés P1 liq ($)":           i1l,
            f"Interés P1 calc {base}d ($)": i1c,
            "Estado P1":                    e1,
        }
        if tiene_p2 and d2 > 0:
            fila.update({
                f"Días P2 | Tasa":              f"{int(d2)} | {t2}%",
                "Interés P2 liq ($)":           i2l,
                f"Interés P2 calc {base}d ($)": i2c,
                "Estado P2":                    e2,
                "Total liq ($)":                i1l + i2l,
                "Total calc ($)":               i1c + i2c,
                "Diferencia ($)":               (i1l + i2l) - (i1c + i2c),
            })
        filas.append(fila)

    return pd.DataFrame(filas), alertas


def auditar_base(df: pd.DataFrame, base: int, texto: str) -> list:
    alertas = []
    tl = texto.lower()
    declara_360 = any(p in tl for p in ["dividida por 360","dividido por 360","360 días","360 dias"])
    declara_365 = any(p in tl for p in ["dividida por 365","dividido por 365","365 días","365 dias"])

    if not declara_360 and not declara_365:
        alertas.append({
            "nivel": "amarilla",
            "titulo": "Base de días no declarada en la liquidación",
            "detalle": f"No se encontró declaración expresa de base 360 o 365. Base detectada: {base} días.",
        })
    elif declara_360 and base == 360:
        alertas.append({
            "nivel": "verde",
            "titulo": "✓ Base de días: 360 días declarada y aplicada consistentemente",
            "detalle": "La liquidación declara base 360 días y lo aplica de forma consistente.",
        })
    elif declara_365 and base == 365:
        alertas.append({
            "nivel": "verde",
            "titulo": "✓ Base de días: 365 días (Art. 11 Ley 18.010)",
            "detalle": "La liquidación aplica base 365 días correctamente.",
        })

    # Verificar consistencia
    bases_usadas = set()
    for _, r in df.iterrows():
        cap = r.get("capital", 0); d = r.get("dias_p1", r.get("dias", 0))
        t = r.get("tasa_p1", r.get("tasa", 0)); il = r.get("interes_p1", r.get("interes_liq", 0))
        if cap <= 0 or d <= 0 or t <= 0 or il <= 0:
            continue
        tol = il * 0.015
        if abs(calcular_interes(cap, int(d), t, 360) - il) <= tol:
            bases_usadas.add(360)
        elif abs(calcular_interes(cap, int(d), t, 365) - il) <= tol:
            bases_usadas.add(365)

    if len(bases_usadas) > 1:
        alertas.append({
            "nivel": "roja",
            "titulo": "🚨 BASE MIXTA — Se mezclan 360 y 365 días en distintas facturas",
            "detalle": "La liquidación aplica base 360 en algunas facturas y 365 en otras. Debe ser consistente.",
        })
    return alertas


def auditar_comision(df: pd.DataFrame, texto: str) -> list:
    alertas = []
    capital_real = df["capital"].sum() if not df.empty else 0
    m = re.search(r"saldo\s+insoluto[\s.:$]*([\d.,\s]+)", texto, re.IGNORECASE)
    if m:
        try:
            saldo = limpiar_monto_pdf(m.group(1))
            if saldo > 0 and capital_real > 0:
                ratio = saldo / capital_real
                if ratio > 2:
                    alertas.append({
                        "nivel": "roja",
                        "titulo": "🚨 ERROR DE PLANTILLA — Comisión sobre saldo incorrecto",
                        "detalle": (
                            f"El saldo insoluto usado para la comisión es {fmt_clp(saldo)}, "
                            f"pero la suma real de capitales es {fmt_clp(capital_real)} "
                            f"({ratio:.1f}x el capital real). La comisión está calculada sobre "
                            f"deuda anterior ya consignada."
                        ),
                    })
        except Exception:
            pass
    return alertas


def analizar_sentencia(texto_s: str, texto_l: str, df: pd.DataFrame) -> list:
    alertas = []
    ts = texto_s.lower()
    tl = texto_l.lower()

    capital_liq = df["capital"].sum() if not df.empty else 0

    # ── 1. CAPITAL ORIGINAL EN SENTENCIA vs SALDO REAL ──
    # Buscar montos grandes mencionados en la sentencia (capital demandado)
    montos_sentencia = re.findall(
        r'\$\s*([\d]{1,3}(?:[.,]\d{3})+)',
        texto_s
    )
    capital_original = 0
    for m in montos_sentencia:
        v = limpiar_monto_pdf(m)
        if v > capital_original and v > 1_000_000:
            capital_original = v

    if capital_original > 0 and capital_liq > 0:
        if capital_original > capital_liq * 2:
            # ── 2. COMISIÓN CALCULADA SOBRE CAPITAL INCORRECTO ──
            # Buscar comisión en la liquidación
            m_com = re.search(
                r'comisi[oó]n\s+fija[\s\w]*[:\s]*\$?\s*([\d.,\s]+)',
                tl, re.IGNORECASE
            )
            m_saldo = re.search(
                r'saldo\s+insoluto[\s.:$]*([\d.,\s]+)',
                tl, re.IGNORECASE
            )
            if m_saldo:
                saldo_usado = limpiar_monto_pdf(m_saldo.group(1))
                if saldo_usado > capital_liq * 2:
                    com_incorrecta = saldo_usado * 0.01
                    com_correcta   = capital_liq  * 0.01
                    exceso         = com_incorrecta - com_correcta
                    alertas.append({
                        "nivel": "roja",
                        "titulo": "🚨 Comisión Ley 19.983 calculada sobre saldo incorrecto",
                        "detalle": (
                            f"La liquidación calcula la comisión (1%) sobre el saldo insoluto "
                            f"original de {fmt_clp(saldo_usado)} (deuda antes de pagos), "
                            f"cuando debería calcularse sobre el capital insoluto real después "
                            f"de las consignaciones: {fmt_clp(capital_liq)}. "
                            f"Comisión cobrada: {fmt_clp(com_incorrecta)} | "
                            f"Comisión correcta: {fmt_clp(com_correcta)} | "
                            f"Exceso: {fmt_clp(exceso)}."
                        ),
                    })

    # ── 3. COSTAS EN SENTENCIA ──
    con_costas  = any(p in ts for p in ["condena en costas", "condena a la parte ejecutada en costas",
                                         "se condena en costas"])
    sin_costas  = any(p in ts for p in ["sin costas", "no se condena en costas", "cada parte"])
    costas_liq  = any(p in tl for p in ["costas", "honorario"])

    if con_costas:
        # Verificar si están en la liquidación sin tasación
        tasacion = any(p in tl for p in ["tasación", "tasacion", "regulación", "regulacion"])
        if costas_liq and not tasacion:
            alertas.append({
                "nivel": "amarilla",
                "titulo": "Costas incluidas — verificar si existe tasación aprobada",
                "detalle": (
                    "La sentencia condena en costas a la ejecutada (punto II resolutivo). "
                    "Para incluirlas en la liquidación deben existir resoluciones firmes de "
                    "tasación de costas procesales y regulación de costas personales. "
                    "Verifique si esas resoluciones existen en el expediente."
                ),
            })
        elif not costas_liq:
            alertas.append({
                "nivel": "amarilla",
                "titulo": "Costas ordenadas en sentencia — no aparecen en la liquidación",
                "detalle": "La sentencia condena en costas pero no se detectan en la liquidación. Pueden estar pendientes de tasación.",
            })
    elif sin_costas and costas_liq:
        alertas.append({
            "nivel": "roja",
            "titulo": "🚨 Costas incluidas sin ser ordenadas en sentencia",
            "detalle": "La sentencia resolvió sin costas pero la liquidación las incluye. Partida improcedente.",
        })

    # ── 4. FECHA DE INICIO DE INTERESES ──
    # En juicios de facturas (Ley 19.983) los intereses corren desde la mora
    # que es la fecha de vencimiento de cada factura
    if any(p in ts for p in ["19.983", "ley 19983", "factura"]):
        alertas.append({
            "nivel": "verde",
            "titulo": "✓ Intereses desde fecha de mora de cada factura (Ley 19.983)",
            "detalle": (
                "La sentencia se basa en la Ley 19.983 (facturas). "
                "Los intereses deben computarse desde la fecha de vencimiento de cada factura, "
                "que es la fecha de mora indicada en la columna correspondiente. "
                "Verifique que las fechas de mora en la liquidación coincidan con los vencimientos "
                "de las facturas individualizadas en la sentencia."
            ),
        })

    # ── 5. DEDUCCIÓN DE PAGOS PARCIALES ──
    # La sentencia ordena expresamente deducir los pagos del considerando séptimo
    if any(p in ts for p in ["previa deducción", "previa deducci", "considerando séptimo",
                              "considerando septimo", "sumas señaladas"]):
        # Verificar que la liquidación tenga consignaciones
        tiene_consig = "capital_am" in df.columns and df["capital_am"].sum() > 0
        tiene_p2     = "saldo_capital" in df.columns and df["saldo_capital"].sum() > 0

        if tiene_consig or tiene_p2:
            alertas.append({
                "nivel": "verde",
                "titulo": "✓ Pagos parciales deducidos conforme a sentencia",
                "detalle": (
                    "La sentencia ordena proseguir la ejecución 'previa deducción de las sumas "
                    "señaladas en el considerando séptimo' (pagos por transferencia bancaria). "
                    "La liquidación refleja consignaciones para cada factura. "
                    "Verifique que los montos descontados coincidan exactamente con los "
                    "comprobantes de pago individualizados en dicho considerando."
                ),
            })
        else:
            alertas.append({
                "nivel": "roja",
                "titulo": "🚨 La sentencia ordena deducir pagos pero la liquidación no los refleja",
                "detalle": (
                    "La sentencia ordena expresamente deducir los pagos parciales realizados "
                    "antes de calcular los intereses, pero no se detectan consignaciones "
                    "en la liquidación."
                ),
            })

    return alertas


def render_alerta(a: dict):
    cls = {"roja": "alerta-roja", "amarilla": "alerta-amarilla",
           "verde": "alerta-verde"}.get(a["nivel"], "alerta-azul")
    st.markdown(f'<div class="{cls}"><strong>{a["titulo"]}</strong><br>{a["detalle"]}</div>',
                unsafe_allow_html=True)


def generar_escrito(alertas, meta, df, abogado, ejecutado, ciudad) -> str:
    hoy  = datetime.now().strftime("%d de %B de %Y")
    rol  = meta.get("rol", "[ROL]")
    tri  = meta.get("tribunal", "[TRIBUNAL]")
    cara = meta.get("caratula", "[CARÁTULA]")

    errores = [a for a in alertas if a["nivel"] in ("roja", "amarilla")]
    if not errores:
        args = "\n   Sin errores detectados en los puntos analizados.\n"
    else:
        lines = []
        for i, a in enumerate(errores, 1):
            det = re.sub(r'\*\*(.+?)\*\*', r'\1', a["detalle"])
            lines.append(f"\n   {i}°. {a['titulo'].upper()}\n\n   {det}\n")
        args = "".join(lines)

    cols_liq  = [c for c in df.columns if "liq" in c.lower() and "($)" in c]
    cols_calc = [c for c in df.columns if "calc" in c.lower() and "($)" in c]
    tl = df[cols_liq].sum(numeric_only=True).sum()  if cols_liq  else 0
    tc = df[cols_calc].sum(numeric_only=True).sum() if cols_calc else tl

    return f"""OBSERVACIONES A LA LIQUIDACIÓN DE CRÉDITO
(Artículo 510 del Código de Procedimiento Civil)

                                    {ciudad.upper()}, {hoy}

{tri.upper() if tri else "[TRIBUNAL]"}
CAUSA ROL N° {rol}
CARÁTULA: {cara}

{ejecutado or "[EJECUTADO]"}, representado por {abogado or "[ABOGADO]"}, a S.S. expone:

I. ANTECEDENTES

   De conformidad con el artículo 510 del CPC, formulo observaciones a la liquidación
   practicada, por cuanto adolece de los siguientes errores:

II. FUNDAMENTOS
{args}
III. CUANTIFICACIÓN

   Intereses liquidados:              {fmt_clp(tl)}
   Intereses correctos:               {fmt_clp(tc)}
   Diferencia a favor del ejecutado:  {fmt_clp(abs(tl - tc))}

IV. SOLICITUD

   ÚNICO: Rectificar la liquidación corrigiendo los errores señalados, conforme a la
   Ley N° 18.010 y demás disposiciones legales aplicables.

POR TANTO, RUEGO A S.S.: Acoger las presentes observaciones y ordenar nueva liquidación.

_________________________________
{abogado or "[Abogado]"}
Abogado Patrocinante
"""

# ─────────────────────────────────────────────
#  PANTALLA DE BIENVENIDA
# ─────────────────────────────────────────────
if uploaded_file is None and not texto_pegado_sidebar.strip():
    st.markdown('<div class="alerta-azul">👈 Suba un PDF o pegue el texto de la liquidación en la barra lateral.</div>',
                unsafe_allow_html=True)
    with st.expander("¿Qué audita esta herramienta?", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
**Con la liquidación:**
1. Base de días (360/365) — declaración y consistencia
2. Errores aritméticos por factura y período
3. Comisión sobre saldo incorrecto
4. Anatocismo (interés sobre interés)
""")
        with c2:
            st.markdown("""
**Agregando la sentencia (opcional):**
5. Fecha de inicio de intereses
6. Partidas no ordenadas (comisiones, costas)
7. Tipo de interés aplicado
""")
    st.stop()

# ─────────────────────────────────────────────
#  PROCESAR ENTRADA
# ─────────────────────────────────────────────
meta = {}
texto_pdf = ""
df_raw = pd.DataFrame()

if texto_pegado_sidebar.strip():
    texto_pdf = texto_pegado_sidebar
    meta = extraer_meta(texto_pdf)
    with st.spinner("Procesando texto..."):
        filas = parsear_texto_liquidacion(texto_pdf)
    if filas:
        df_raw = pd.DataFrame(filas)
        df_raw.attrs["estrategia"] = "Texto pegado"
    else:
        st.markdown('<div class="alerta-amarilla"><strong>No se pudo parsear el texto.</strong> Verifique que copió la tabla completa.</div>',
                    unsafe_allow_html=True)
        st.stop()

elif uploaded_file is not None:
    file_bytes = uploaded_file.read()
    with st.spinner("Extrayendo datos del PDF..."):
        df_raw, meta = extraer_tabla_pdf(file_bytes)
    texto_pdf = extraer_texto_pdf(file_bytes)

    if df_raw.empty or len(df_raw) < 2:
        # Intentar con el texto del PDF también
        filas = parsear_texto_liquidacion(texto_pdf)
        if filas:
            df_raw = pd.DataFrame(filas)
            df_raw.attrs["estrategia"] = "Parser de texto (PDF)"
        else:
            st.markdown("""
<div class="alerta-amarilla"><strong>No se pudo extraer la tabla.</strong>
Pruebe el modo "Pegar texto": abra el PDF, <strong>Ctrl+A → Ctrl+C</strong>,
y pegue en la barra lateral.</div>""", unsafe_allow_html=True)
            if df_raw.empty:
                st.stop()

# ─────────────────────────────────────────────
#  MOSTRAR METADATOS
# ─────────────────────────────────────────────
st.markdown('<div class="seccion-titulo">Identificación de la causa</div>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown(f"**ROL:** {meta.get('rol','No detectado')}")
c2.markdown(f"**Fecha:** {meta.get('fecha_liq','No detectada')}")
c3.markdown(f"**Tribunal:** {meta.get('tribunal','No detectado')}")
if meta.get("caratula"):
    st.markdown(f"**Carátula:** {meta['caratula']}")

estrategia = df_raw.attrs.get("estrategia", "")
if estrategia:
    st.markdown(f'<div class="alerta-verde">✓ Extracción exitosa — {estrategia} — {len(df_raw)} facturas</div>',
                unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  TABLA EXTRAÍDA
# ─────────────────────────────────────────────
st.markdown('<div class="seccion-titulo">Tabla extraída</div>', unsafe_allow_html=True)

cols_mostrar = ["numero", "fecha_mora", "capital", "dias_p1", "tasa_p1", "interes_p1",
                "saldo_capital", "dias_p2", "tasa_p2", "interes_p2"]
cols_mostrar = [c for c in cols_mostrar if c in df_raw.columns]
df_disp = df_raw[cols_mostrar].copy()
for col in ["capital", "interes_p1", "saldo_capital", "interes_p2"]:
    if col in df_disp.columns:
        df_disp[col] = df_disp[col].apply(lambda x: fmt_clp(x) if isinstance(x, (int,float)) else x)
st.dataframe(df_disp, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
#  AUDITORÍA
# ─────────────────────────────────────────────
base = detectar_base(df_raw, texto_pdf)
st.markdown(f'<div class="seccion-titulo">Re-cálculo — base {base} días detectada</div>',
            unsafe_allow_html=True)

df_aud, al_calc = auditar(df_raw, base)
al_base = auditar_base(df_raw, base, texto_pdf)
al_com  = auditar_comision(df_raw, texto_pdf)

# Sentencia
al_sent = []
if uploaded_sentencia:
    with st.spinner("Analizando sentencia..."):
        sent_bytes = uploaded_sentencia.read()
        texto_s    = extraer_texto_pdf(sent_bytes)
        if texto_s.strip():
            al_sent = analizar_sentencia(texto_s, texto_pdf, df_raw)

todas = al_base + al_com + al_calc + al_sent

# Colorear tabla
def colorear(row):
    estados = [str(v) for k, v in row.items() if "Estado" in str(k)]
    if any("Error" in e for e in estados):
        return ["background-color:#fce8e8"] * len(row)
    return [""] * len(row)

fmt_cols = {c: "{:,.0f}" for c in df_aud.columns if "($)" in str(c)}
if not df_aud.empty:
    styled = df_aud.style.apply(colorear, axis=1).format(
        {k: v for k, v in fmt_cols.items() if k in df_aud.columns}
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

# Métricas
if not df_aud.empty:
    cols_l = [c for c in df_aud.columns if "liq" in c.lower() and "($)" in c]
    cols_c = [c for c in df_aud.columns if "calc" in c.lower() and "($)" in c]
    tl = df_aud[cols_l].sum(numeric_only=True).sum() if cols_l else 0
    tc = df_aud[cols_c].sum(numeric_only=True).sum() if cols_c else tl
    diff = tl - tc
    nerr = len([a for a in todas if a["nivel"] == "roja"])

    st.markdown('<div class="seccion-titulo">Métricas</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Intereses liquidados", fmt_clp(tl))
    m2.metric(f"Intereses correctos ({base}d)", fmt_clp(tc))
    m3.metric("Diferencia", fmt_clp(abs(diff)),
              delta=f"{diff/tc*100:.2f}%" if tc else "—",
              delta_color="inverse" if diff > 0 else "normal")
    m4.metric("Alertas rojas", str(nerr), delta_color="inverse" if nerr > 0 else "normal")

# Sentencia
if uploaded_sentencia and al_sent:
    st.markdown('<div class="seccion-titulo">Verificación vs sentencia</div>', unsafe_allow_html=True)
    for a in al_sent:
        render_alerta(a)

# Discrepancias
st.markdown('<div class="seccion-titulo">Discrepancias detectadas</div>', unsafe_allow_html=True)
if not todas:
    st.markdown('<div class="alerta-verde">✓ No se detectaron discrepancias.</div>', unsafe_allow_html=True)
else:
    rojas = [a for a in todas if a["nivel"] == "roja"]
    resto = [a for a in todas if a["nivel"] != "roja"]
    for a in rojas + resto:
        render_alerta(a)

# Escrito
st.markdown('<div class="seccion-titulo">Escrito de observaciones — Art. 510 CPC</div>',
            unsafe_allow_html=True)
if abogado and ejecutado:
    escrito = generar_escrito(todas, meta, df_aud, abogado, ejecutado, ciudad)
    st.markdown(f'<div class="escrito-box">{escrito}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 5])
    with c1:
        st.download_button("📥 Descargar",
                          data=escrito.encode("utf-8"),
                          file_name=f"observaciones_{meta.get('rol','causa')}.txt",
                          mime="text/plain")
else:
    st.markdown('<div class="alerta-azul">Complete el nombre del abogado y ejecutado en la barra lateral para generar el escrito.</div>',
                unsafe_allow_html=True)

st.markdown("---")
st.markdown("<small style='color:#9a9690;'>Auditor · Ley N° 18.010 · Art. 510 CPC · Solo uso profesional</small>",
            unsafe_allow_html=True)