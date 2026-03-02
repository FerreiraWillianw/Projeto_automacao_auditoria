import streamlit as st
import os
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO E CONEXÃO ---
# A URL deve estar configurada no seu arquivo .streamlit/secrets.toml
db_url = st.secrets["connections"]["url"]
engine = create_engine(db_url)

# --- LOCALIZAÇÃO DE ATIVOS (LOGOS) ---
caminho_script = os.path.dirname(os.path.abspath(__file__))
logo_fusve = os.path.join(caminho_script, "assets", "logo_fusve.png")
logo_auditoria = os.path.join(caminho_script, "assets", "logo_auditoria.png")

MAPPING_AREAS = {
    "Gerência de Gente e gestão - GGG": 1,
    "Gerência de Finanças": 2,
    "Gerência de TI": 3,
}

MAPA_RISCO = {
    ("Muito Alto", "Muito Alto"): 15, ("Alto", "Muito Alto"): 14, ("Médio", "Muito Alto"): 13, ("Baixo", "Muito Alto"): 12,
    ("Muito Alto", "Alto"): 11, ("Alto", "Alto"): 10, ("Médio", "Alto"): 9, ("Baixo", "Alto"): 8,
    ("Muito Alto", "Médio"): 7, ("Alto", "Médio"): 6, ("Médio", "Médio"): 5, ("Baixo", "Médio"): 4,
    ("Muito Alto", "Baixo"): 3, ("Alto", "Baixo"): 2, ("Médio", "Baixo"): 1, ("Baixo", "Baixo"): 0
}

# --- LÓGICA DE LIMPEZA ---
if 'deve_limpar' in st.session_state and st.session_state['deve_limpar']:
    
    # 1. Reseta os campos de texto
    campos_para_limpar = ["input_processo", "input_objetivo", "input_executor", 
                          "input_descricao", "input_etapa_ini", "input_etapa_fim", 
                          "input_produto", "codigo_processo"]
    
    for campo in campos_para_limpar:
        if campo in st.session_state:
            st.session_state[campo] = ""

    # 2. Reseta a Selectbox da área
    st.session_state["area"] = None

    # 3. Reseta os riscos
    st.session_state['riscos'] = []

    # Finaliza a flag
    st.session_state['deve_limpar'] = False

    st.rerun()

# --- FUNÇÕES ---
def obter_proximo_codigo(area_selecionada):
    prefixo = MAPPING_AREAS.get(area_selecionada, "0")
    query = text("SELECT COUNT(*) FROM processos WHERE area = :area")
    with engine.connect() as conn:
        resultado = conn.execute(query, {"area": area_selecionada})
        contagem = resultado.scalar() or 0
    return f"{prefixo}.{contagem + 1}"

def get_estilo_risco(score):
    if score >= 12: return "#FF4B4B", "🔴" 
    elif score >= 8: return "#FF9900", "🟠"    
    elif score >= 4: return "#FFD700", "🟡"   
    elif score >= 0: return "#00CC96", "🟢" 

def salvar_no_banco():
    try: 
        with engine.begin() as conn:
            # 1. Salva Processo
            sql_processo = text("""
                INSERT INTO processos (area, codigo_processo, nome_processo, objetivo, executor, descricao, etapa_ini, etapa_fim, produto)
                VALUES (:area, :cod, :nome, :obj, :exec, :desc, :e_ini, :e_fim, :prod)
                RETURNING id
            """)
            resultado = conn.execute(sql_processo, {
                "area": st.session_state.get("area"),
                "cod": st.session_state.get("codigo_processo"),
                "nome": st.session_state.get("input_processo"),
                "obj": st.session_state.get("input_objetivo"),
                "exec": st.session_state.get("input_executor"),
                "desc": st.session_state.get("input_descricao"),
                "e_ini": st.session_state.get("input_etapa_ini"),
                "e_fim": st.session_state.get("input_etapa_fim"),
                "prod": st.session_state.get("input_produto")
            })
            processo_id = resultado.scalar()

            # 2. Salva Riscos
            sql_risco = text("""
                INSERT INTO riscos (processo_id, nome_risco, fator_risco, melhoria, impacto, probabilidade, apetite_risco, motivo_risco)
                VALUES (:pid, :nome, :fator, :melhoria, :imp, :prob, :apetite, :motivo)
            """)
            for i in range(len(st.session_state['riscos'])):
                conn.execute(sql_risco, {
                    "pid": processo_id,
                    "nome": st.session_state.get(f"nome_{i}"),
                    "fator": st.session_state.get(f"fator_{i}"),
                    "melhoria": st.session_state.get(f"melhoria_{i}"),
                    "imp": st.session_state.get(f"imp_{i}"),
                    "prob": st.session_state.get(f"prob_{i}"),
                    "apetite": st.session_state.get(f"apetite_{i}"),
                    "motivo": st.session_state.get(f"motivo_{i}")
                })
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False

# --- UI ---
st.set_page_config(page_title="Diagnóstico FUSVE", layout="centered")

if os.path.exists(logo_fusve): st.sidebar.image(logo_fusve, width=200)
if os.path.exists(logo_auditoria):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2: st.image(logo_auditoria, width=300)

st.title("Diagnóstico de Processos - Auditoria Interna FUSVE")

if 'riscos' not in st.session_state: st.session_state['riscos'] = []
if 'errors' not in st.session_state: st.session_state['errors'] = {}

# 1. Dados do Processo ---------------------------------------

st.subheader("1. Dados do Processo")
area = st.selectbox("Selecione a Área:", list(MAPPING_AREAS.keys()), key="area")
if area:
    sugestao_id = obter_proximo_codigo(area)
    st.text_input("Código do Processo:", value=sugestao_id, key="codigo_processo", disabled=True)

st.text_input("Nome do Processo:", key="input_processo")
st.text_area("Objetivo:", key="input_objetivo")
st.text_area("Quem Executa?", key="input_executor")
st.text_area("Descrição:", key="input_descricao")
st.text_area("Etapa Inicial:", key="input_etapa_ini")
st.text_area("Etapa Final:", key="input_etapa_fim")
st.text_area("Produto:", key="input_produto")

st.divider()

# 2. Riscos Associados ---------------------------------------

st.subheader("2. Riscos Associados")
if st.button("➕ Adicionar Novo Risco"):
    st.session_state['riscos'].append({})
    st.rerun()

for i, _ in enumerate(st.session_state['riscos']):
    st.markdown(f"**Risco {i+1}**")
    st.text_input(f"Nome do Risco:", key=f"nome_{i}")
    st.text_area(f"Fator de Risco:", key=f"fator_{i}")
    st.text_area(f"Melhoria:", key=f"melhoria_{i}")
    st.text_area(f"Apetite ao risco:", key=f"apetite_{i}")
    
    col_i, col_p = st.columns(2)
    with col_i: impacto = st.selectbox(f"Impacto:", ["Muito Alto", "Alto", "Médio", "Baixo"], key=f"imp_{i}")
    with col_p: prob = st.selectbox(f"Probabilidade:", ["Muito Alto", "Alto", "Médio", "Baixo"], key=f"prob_{i}")
    
    risco_calc = MAPA_RISCO.get((impacto, prob), 0)
    cor, emoji = get_estilo_risco(risco_calc)
    
    st.markdown(f"""
        <div style="background-color: {cor}; padding: 10px; border-radius: 5px; text-align: center;">
            <h3 style="color: white; margin: 0;">{emoji} Score: {risco_calc}</h3>
        </div>
    """, unsafe_allow_html=True)
    st.text_area(f"Motivo:", key=f"motivo_{i}")
    st.markdown("---")

# --- BOTÃO SALVAR ---
if st.button("💾 Salvar Todos os Dados", type="primary", use_container_width=True):
    campos_fixos = ["input_processo", "input_objetivo", "input_executor", "input_descricao", "input_etapa_ini", "input_etapa_fim", "input_produto"]
    
    if all(st.session_state.get(c) for c in campos_fixos):
        if salvar_no_banco():
            st.success("Dados salvos com sucesso no SQL!")
            st.session_state['deve_limpar'] = True
            st.rerun()
    else:
        st.error("Por favor, preencha todos os campos obrigatórios.")