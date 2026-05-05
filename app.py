# ============================================
# AGENTE E-COMMERCE — Dashboard Streamlit
# ============================================

import streamlit as st
import pandas as pd
import anthropic
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Carga la API key automáticamente del archivo .env
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── CONFIGURACIÓN ────────────────────────────
st.set_page_config(page_title="Agente E-Commerce IA", page_icon="🛍️", layout="wide")

st.markdown("""
<style>
.stButton > button { border-radius: 8px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ── FUNCIONES ────────────────────────────────

def calcular_kpis(df):
    df = df[df["financial_status"] == "paid"].copy()
    ventas_por_pedido = df.groupby("order_id")["total_price"].sum()
    total_ventas  = round(ventas_por_pedido.sum(), 2)
    ticket_medio  = round(ventas_por_pedido.mean(), 2)
    num_pedidos   = df["order_id"].nunique()
    num_clientes  = df["email"].nunique()

    df["margen_linea"]  = (df["lineitem_price"] - df["lineitem_cost"] - df["lineitem_discount"]) * df["lineitem_quantity"]
    df["ingreso_linea"] = (df["lineitem_price"] - df["lineitem_discount"]) * df["lineitem_quantity"]

    productos = df.groupby("lineitem_name").agg(
        unidades=("lineitem_quantity", "sum"),
        ingresos=("ingreso_linea", "sum"),
        margen=("margen_linea", "sum")
    ).round(2)
    productos["margen_pct"] = (productos["margen"] / productos["ingresos"] * 100).round(1)
    top_productos = productos.sort_values("ingresos", ascending=False).head(6)

    df["dia_semana"] = df["created_at"].dt.day_name()
    mejor_dia = df.groupby("dia_semana")["total_price"].sum().idxmax()

    hoy = df["created_at"].max()
    ultima_compra = df.groupby("email")["created_at"].max()
    en_riesgo = ultima_compra[ultima_compra < hoy - timedelta(days=60)]
    productos_riesgo = productos[productos["margen_pct"] < 20].index.tolist()

    return {
        "df_clean": df,
        "total_ventas": total_ventas,
        "ticket_medio": ticket_medio,
        "num_pedidos": num_pedidos,
        "num_clientes": num_clientes,
        "top_productos": top_productos,
        "mejor_dia": mejor_dia,
        "clientes_en_riesgo": len(en_riesgo),
        "productos_riesgo": productos_riesgo,
    }


def generar_insights(kpis):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Eres un analista senior de e-commerce. Genera exactamente 5 insights accionables,
priorizados por impacto económico. Usa emojis 🔴🟡🟢 según urgencia.

DATOS (últimos 90 días):
- Ventas totales: {kpis['total_ventas']}€
- Ticket medio: {kpis['ticket_medio']}€
- Pedidos: {kpis['num_pedidos']}
- Clientes únicos: {kpis['num_clientes']}
- Mejor día: {kpis['mejor_dia']}
- Clientes en riesgo (60+ días sin comprar): {kpis['clientes_en_riesgo']}
- Productos con margen bajo: {kpis['productos_riesgo']}
- Top productos:\n{kpis['top_productos'][['unidades','ingresos','margen_pct']].to_string()}

Formato por insight:
**[EMOJI] TÍTULO**
- Qué pasa: ...
- Por qué importa: ...
- Acción esta semana: ...
- Impacto estimado: ...
"""
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return r.content[0].text


def chat_con_agente(pregunta, kpis, historial):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    contexto = f"""Eres el agente de análisis de esta tienda online. Responde de forma concisa y accionable.
Datos:
- Ventas: {kpis['total_ventas']}€ | Ticket medio: {kpis['ticket_medio']}€ | Pedidos: {kpis['num_pedidos']}
- Clientes únicos: {kpis['num_clientes']} | Mejor día: {kpis['mejor_dia']}
- Clientes en riesgo: {kpis['clientes_en_riesgo']}
- Top productos: {kpis['top_productos'][['unidades','ingresos','margen_pct']].to_string()}
Historial: {historial}
Pregunta: {pregunta}"""
    r = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": contexto}]
    )
    return r.content[0].text


# ── SIDEBAR ──────────────────────────────────
with st.sidebar:
    st.title("🛍️ Agente E-Commerce")
    if ANTHROPIC_API_KEY:
        st.success("✓ API Key cargada automáticamente")
    else:
        st.error("No se encontró la API Key en el archivo .env")
    st.divider()
    st.subheader("📂 Sube tus datos")
    uploaded = st.file_uploader("CSV de ventas", type=["csv"])
    st.caption("Exporta desde Shopify → Pedidos → Exportar")


# ── PANTALLA PRINCIPAL ───────────────────────

if not uploaded:
    st.title("🛍️ Tu analista de e-commerce con IA")
    st.markdown("#### Sube el CSV de tu tienda y obtén insights en segundos")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.info("📊 **KPIs automáticos**\nVentas, ticket medio, márgenes")
    with c2:
        st.info("🤖 **5 insights con IA**\nAcciones concretas priorizadas")
    with c3:
        st.info("💬 **Chat con tus datos**\nPregunta lo que quieras")

else:
    try:
        df = pd.read_csv(uploaded, parse_dates=["created_at"])
        kpis = calcular_kpis(df)

        st.title("📊 Dashboard de tu tienda")
        st.caption(f"Analizando {kpis['num_pedidos']} pedidos · {kpis['num_clientes']} clientes únicos")

        # KPIs
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("💶 Ventas totales", f"{kpis['total_ventas']:,}€")
        with c2: st.metric("🛒 Ticket medio", f"{kpis['ticket_medio']}€")
        with c3: st.metric("📦 Pedidos", kpis['num_pedidos'])
        with c4: st.metric("⚠️ Clientes en riesgo", kpis['clientes_en_riesgo'])

        st.divider()

        tab1, tab2, tab3 = st.tabs(["📦 Productos", "🤖 Insights IA", "💬 Chat"])

        with tab1:
            st.subheader("Top productos")
            top = kpis["top_productos"].reset_index()
            top.columns = ["Producto", "Unidades", "Ingresos (€)", "Margen (€)", "Margen (%)"]
            st.dataframe(top, use_container_width=True, hide_index=True)
            st.caption(f"📅 Mejor día de ventas: **{kpis['mejor_dia']}**")

        with tab2:
            st.subheader("Insights generados por IA")
            if st.button("🔍 Generar insights", type="primary"):
                with st.spinner("Claude está analizando tu tienda..."):
                    st.session_state.insights = generar_insights(kpis)
            if "insights" in st.session_state:
                st.markdown(st.session_state.insights)

        with tab3:
            st.subheader("Habla con tu agente")
            if "mensajes" not in st.session_state:
                st.session_state.mensajes = [
                    {"rol": "agente", "texto": f"Hola 👋 He analizado tu tienda. Tienes {kpis['num_pedidos']} pedidos y {kpis['clientes_en_riesgo']} clientes en riesgo. ¿Qué quieres saber?"}
                ]
            for m in st.session_state.mensajes:
                if m["rol"] == "agente":
                    st.chat_message("assistant").write(m["texto"])
                else:
                    st.chat_message("user").write(m["texto"])

            pregunta = st.chat_input("Pregunta algo sobre tu tienda...")
            if pregunta:
                st.session_state.mensajes.append({"rol": "usuario", "texto": pregunta})
                historial = "\n".join([f"{m['rol']}: {m['texto']}" for m in st.session_state.mensajes[-6:]])
                with st.spinner("Analizando..."):
                    respuesta = chat_con_agente(pregunta, kpis, historial)
                st.session_state.mensajes.append({"rol": "agente", "texto": respuesta})
                st.rerun()

    except Exception as e:
        st.error(f"Error: {e}")
        st.info("Asegúrate de que el CSV tiene las columnas correctas.")

