import streamlit as st
import os
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO E CONEXÃO ---
# Certifique-se de que o secrets.toml está configurado
db_url = st.secrets["connections"]["url"]
engine = create_engine(db_url)

# --- LOCALIZAÇÃO DE ATIVOS ---
caminho_script = os.path.dirname(os.path.abspath(__file__))
logo_fusve = os.path.join(caminho_script, "assets", "logo_fusve.png")
logo_auditoria = os.path.join(caminho_script, "assets", "logo_auditoria.png")

# --- CONSTANTES ---
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

# --- INICIALIZAÇÃO DE ESTADO ---
if 'riscos' not in st.session_state: st.session_state['riscos'] = []
if 'deve_limpar' not in st.session_state: st.session_state['deve_limpar'] = False

# --- FUNÇÕES ---

def obter_proximo_codigo(area_selecionada):
    prefixo = MAPPING_AREAS.get(area_selecionada)
    query = text("SELECT COUNT(*) FROM processos WHERE area = :area")
    with engine.connect() as conn:
        contagem = conn.execute(query, {"area": area_selecionada}).scalar() or 0
    return f"{prefixo}.{contagem + 1}"

def processar_codigo_inteligente():
    area = st.session_state.get("area")
    nome = st.session_state.get("input_processo")
    if not area or not nome:
        st.session_state['codigo_processo'] = ""
        return
    query = text("SELECT codigo_processo FROM processos WHERE area = :area AND nome_processo = :nome")
    with engine.connect() as conn:
        resultado = conn.execute(query, {"area": area, "nome": nome}).fetchone()
    if resultado:
        st.session_state['codigo_processo'] = resultado[0]
        st.toast(f"Processo já existe! Código carregado: {resultado[0]}", icon="✅")
    else:
        st.session_state['codigo_processo'] = obter_proximo_codigo(area)

def get_estilo_risco(score):
    if score >= 12: return "#FF4B4B", "🔴" 
    elif score >= 8: return "#FF9900", "🟠"    
    elif score >= 4: return "#FFD700", "🟡"   
    elif score >= 0: return "#00CC96", "🟢" 

def validar_formulario():
    # Campos Fixos Obrigatórios
    campos = ["input_processo", "input_objetivo", "input_executor", "input_descricao", "input_etapa_ini", "input_etapa_fim", "input_produto", "codigo_processo"]
    for c in campos:
        if not st.session_state.get(c):
            st.error(f"O campo '{c.replace('input_', '').replace('_', ' ').capitalize()}' é obrigatório.")
            return False
    # Riscos
    if not st.session_state['riscos']:
        st.error("Adicione pelo menos um risco.")
        return False
    for i in range(len(st.session_state['riscos'])):
        for campo in ["nome", "fator", "melhoria", "apetite", "motivo"]:
            if not st.session_state.get(f"{campo}_{i}"):
                st.error(f"Preencha todos os campos do Risco {i+1}.")
                return False
    return True

def salvar_no_banco():
    try: 
        with engine.begin() as conn:
            area_val = st.session_state.get("area")
            nome_val = st.session_state.get("input_processo")
            
            # Buscar ou criar processo
            query_busca = text("SELECT id FROM processos WHERE area = :area AND nome_processo = :nome")
            processo_existente = conn.execute(query_busca, {"area": area_val, "nome": nome_val}).fetchone()
            
            if processo_existente:
                processo_id = processo_existente[0]
            else:
                sql_p = text("""INSERT INTO processos (area, codigo_processo, nome_processo, objetivo, executor, descricao, etapa_ini, etapa_fim, produto) 
                                VALUES (:a, :c, :n, :o, :ex, :d, :ei, :ef, :p) RETURNING id""")
                processo_id = conn.execute(sql_p, {
                    "a": area_val, "c": st.session_state['codigo_processo'], "n": nome_val, "o": st.session_state['input_objetivo'], 
                    "ex": st.session_state['input_executor'], "d": st.session_state['input_descricao'], "ei": st.session_state['input_etapa_ini'], 
                    "ef": st.session_state['input_etapa_fim'], "p": st.session_state['input_produto']
                }).scalar()

            # Salvar Riscos
            sql_risco = text("""INSERT INTO riscos (processo_id, nome_risco, fator_risco, melhoria, impacto, probabilidade, apetite_risco, motivo_risco, score_risco) 
                                VALUES (:pid, :nome, :fator, :melhoria, :imp, :prob, :apetite, :motivo, :score)""")
            for i in range(len(st.session_state['riscos'])):
                imp, prob = st.session_state.get(f"imp_{i}"), st.session_state.get(f"prob_{i}")
                score = MAPA_RISCO.get((imp, prob), 0)
                conn.execute(sql_risco, {
                    "pid": processo_id, "nome": st.session_state.get(f"nome_{i}"), "fator": st.session_state.get(f"fator_{i}"), 
                    "melhoria": st.session_state.get(f"melhoria_{i}"), "imp": imp, "prob": prob, 
                    "apetite": st.session_state.get(f"apetite_{i}"), "motivo": st.session_state.get(f"motivo_{i}"), "score": score
                })
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- UI PRINCIPAL ---
st.set_page_config(page_title="Diagnóstico FUSVE", layout="centered")

# Limpeza Pós-Salvo
if st.session_state['deve_limpar']:
    for campo in ["input_processo", "input_objetivo", "input_executor", "input_descricao", "input_etapa_ini", "input_etapa_fim", "input_produto", "codigo_processo", "area"]:
        st.session_state[campo] = None if campo == "area" else ""
    st.session_state['riscos'] = []
    st.session_state['deve_limpar'] = False
    st.rerun()

# Layout de Logos
if os.path.exists(logo_fusve): st.sidebar.image(logo_fusve, width=200)
if os.path.exists(logo_auditoria):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2: st.image(logo_auditoria, width=300)

st.title("Diagnóstico de Processos - FUSVE")

# Seção 1: Dados do Processo
st.subheader("1. Dados do Processo")
st.selectbox("Selecione a Área:", list(MAPPING_AREAS.keys()), key="area", on_change=lambda: st.session_state.update({'codigo_processo': ''}))
st.text_input("Nome do Processo:", key="input_processo", on_change=processar_codigo_inteligente)
st.text_input("Código do Processo:", key="codigo_processo", disabled=True)
st.text_area("Objetivo:", key="input_objetivo")
st.text_area("Quem Executa?", key="input_executor")
st.text_area("Descrição:", key="input_descricao")
st.text_area("Etapa Inicial:", key="input_etapa_ini")
st.text_area("Etapa Final:", key="input_etapa_fim")
st.text_area("Produto:", key="input_produto")

st.divider()

# Seção 2: Riscos
st.subheader("2. Riscos Associados")
for i, _ in enumerate(st.session_state['riscos']):
    st.markdown(f"**Risco {i+1}**")
    st.text_input(f"Nome do Risco:", key=f"nome_{i}")
    st.text_area(f"Fator de Risco:", key=f"fator_{i}")
    st.text_area(f"Melhoria:", key=f"melhoria_{i}")
    st.text_area(f"Apetite ao risco:", key=f"apetite_{i}")
    
    col_i, col_p = st.columns(2)
    with col_i: st.selectbox(f"Impacto:", ["Muito Alto", "Alto", "Médio", "Baixo"], key=f"imp_{i}")
    with col_p: st.selectbox(f"Probabilidade:", ["Muito Alto", "Alto", "Médio", "Baixo"], key=f"prob_{i}")
    
    # Exibir Score em tempo real na tela
    imp_v = st.session_state.get(f"imp_{i}", "Baixo")
    prob_v = st.session_state.get(f"prob_{i}", "Baixo")
    score_v = MAPA_RISCO.get((imp_v, prob_v), 0)
    cor, emoji = get_estilo_risco(score_v)
    st.markdown(f'<div style="background-color: {cor}; padding: 10px; border-radius: 5px; text-align: center; color: white;">{emoji} Score Atual: {score_v}</div>', unsafe_allow_html=True)
    
    st.text_area(f"Motivo:", key=f"motivo_{i}")
    st.markdown("---")

# Botões Finais
col_add, col_save = st.columns(2)
with col_add:
    if st.button("➕ Adicionar Novo Risco", use_container_width=True):
        st.session_state['riscos'].append({})
        st.rerun()
with col_save:
    if st.button("💾 Salvar Todos os Dados", type="primary", use_container_width=True):
        if validar_formulario():
            if salvar_no_banco():
                st.success("Dados salvos com sucesso!")
                st.session_state['deve_limpar'] = True
                st.rerun()