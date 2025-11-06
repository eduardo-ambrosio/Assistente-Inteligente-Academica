import os
import hashlib
from datetime import datetime
import google.generativeai as genai
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, Response
import json

# ============================================================================
# CONFIGURAÇÕES INICIAIS DO SERVIDOR FLASK
# ============================================================================

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24)

# ============================================================================
# CONFIGURAÇÕES DA API DO GOOGLE GEMINI (IA)
# ============================================================================

GOOGLE_API_KEY = ""
genai.configure(api_key=GOOGLE_API_KEY)
modelo_gemini = genai.GenerativeModel('gemini-2.5-flash')

# ============================================================================
# DEFINIÇÃO DOS ARQUIVOS DE DADOS
# ============================================================================

NOME_ARQUIVO_CONTEXTO = "banco_dados.txt"
NOME_ARQUIVO_USUARIOS = "usuarios.txt"
NOME_ARQUIVO_DADOS_ALUNOS = "dados_alunos.txt"
NOME_ARQUIVO_HISTORICO = "historico_conversas.txt"


# ============================================================================
# FUNÇÕES AUXILIARES - HISTÓRICO DE CONVERSAS
# ============================================================================

def salvar_conversa(ra, pergunta, resposta):
    """Salva uma conversa no histórico do aluno"""
    try:
        if not os.path.exists(NOME_ARQUIVO_HISTORICO):
            with open(NOME_ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f:
                f.write("# ============================================\n")
                f.write("# HISTÓRICO DE CONVERSAS - UNIHELP\n")
                f.write("# ============================================\n\n")

        with open(NOME_ARQUIVO_HISTORICO, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[RA:{ra}|DATA:{timestamp}]\n")
            f.write(f"PERGUNTA: {pergunta}\n")
            f.write(f"RESPOSTA: {resposta}\n")
            f.write("[FIM_CONVERSA]\n\n")

        print(f"✅ Conversa salva no histórico (RA: {ra})")

    except Exception as e:
        print(f"❌ ERRO ao salvar conversa: {e}")


def carregar_historico_aluno(ra, limite=20):
    """Carrega as últimas conversas do aluno"""
    try:
        if not os.path.exists(NOME_ARQUIVO_HISTORICO):
            return []

        with open(NOME_ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f:
            conteudo = f.read()

        conversas = []
        blocos = conteudo.split('[FIM_CONVERSA]')

        for bloco in blocos:
            if f"[RA:{ra}|" in bloco:
                linhas = bloco.strip().split('\n')
                if len(linhas) >= 3:
                    cabecalho = linhas[0]
                    data = cabecalho.split('DATA:')[1].strip(']') if 'DATA:' in cabecalho else 'N/A'

                    pergunta = linhas[1].replace('PERGUNTA: ', '').strip()
                    resposta = '\n'.join([l.replace('RESPOSTA: ', '', 1) if l.startswith('RESPOSTA:') else l
                                          for l in linhas[2:] if l.strip() and not l.startswith('[')]).strip()

                    conversas.append({
                        'data': data,
                        'pergunta': pergunta,
                        'resposta': resposta
                    })

        return conversas[-limite:][::-1]

    except Exception as e:
        print(f"❌ ERRO ao carregar histórico: {e}")
        return []


# ============================================================================
# FUNÇÕES AUXILIARES - GERENCIAMENTO DE DADOS
# ============================================================================

def carregar_contexto():
    try:
        with open(NOME_ARQUIVO_CONTEXTO, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"AVISO: Arquivo '{NOME_ARQUIVO_CONTEXTO}' não encontrado.")
        return "Nenhum contexto específico fornecido."


def carregar_dados_aluno(ra):
    try:
        if not os.path.exists(NOME_ARQUIVO_DADOS_ALUNOS):
            return ""

        with open(NOME_ARQUIVO_DADOS_ALUNOS, 'r', encoding='utf-8') as f:
            conteudo = f.read()

        inicio = conteudo.find(f"[RA:{ra}]")
        if inicio == -1:
            return ""

        fim = conteudo.find("[FIM]", inicio)
        if fim == -1:
            return ""

        dados_aluno = conteudo[inicio:fim + 5]
        return dados_aluno

    except Exception as e:
        print(f"❌ ERRO ao carregar dados do aluno: {e}")
        return ""


def salvar_dados_aluno_inicial(ra, nome, curso):
    try:
        if not os.path.exists(NOME_ARQUIVO_DADOS_ALUNOS):
            with open(NOME_ARQUIVO_DADOS_ALUNOS, 'w', encoding='utf-8') as f:
                f.write("# ============================================\n")
                f.write("# DADOS PERSONALIZADOS DOS ALUNOS - UNIHELP\n")
                f.write("# ============================================\n\n")

        dados_existentes = carregar_dados_aluno(ra)
        if dados_existentes:
            return

        with open(NOME_ARQUIVO_DADOS_ALUNOS, 'a', encoding='utf-8') as f:
            f.write(f"\n[RA:{ra}]\n")
            f.write(f"NOME: {nome}\n")
            f.write(f"CURSO: {curso}\n")
            f.write(f"GRUPO: Não atribuído\n\n")
            f.write("NOTAS:\n")
            f.write("Ciclo 1|AFE - Avaliação Final de entrega|0.00\n")
            f.write("Ciclo 1|VRAU - Verificação Regular|0.00\n")
            f.write("Ciclo 1|PI - Projeto Integrador|0.00\n")
            f.write("Ciclo 1|Avaliação 360°|0.00\n\n")
            f.write("HISTORICO:\n")
            f.write("Cidadania ética e espiritualidade|1|0.0|Cursando\n")
            f.write("Introdução a engenharia de soluções|1|0.0|Cursando\n")
            f.write("Fundamentos matemáticos para computação|1|0.0|Cursando\n")
            f.write("Fundamentos de computação e infraestrutura|1|0.0|Cursando\n")
            f.write("Fundamentos de engenharia de dados|1|0.0|Cursando\n")
            f.write("[FIM]\n\n")

        print(f"✅ Dados iniciais criados para: {nome} (RA: {ra})")

    except Exception as e:
        print(f"❌ ERRO ao criar dados do aluno: {e}")


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def salvar_usuario(dados):
    try:
        if not os.path.exists(NOME_ARQUIVO_USUARIOS):
            with open(NOME_ARQUIVO_USUARIOS, 'w', encoding='utf-8') as f:
                f.write("# ============================================\n")
                f.write("# BANCO DE DADOS DE USUÁRIOS - UNIHELP\n")
                f.write("# ============================================\n")
                f.write("# Estrutura: RA|NOME|EMAIL|CPF|CURSO|SENHA_HASH|DATA_CADASTRO\n")
                f.write("# " + "=" * 80 + "\n\n")

        with open(NOME_ARQUIVO_USUARIOS, 'a', encoding='utf-8') as f:
            linha = f"{dados['ra']}|{dados['nome_completo']}|{dados['email']}|{dados['cpf']}|{dados['curso']}|{dados['senha_hash']}|{dados['data_cadastro']}\n"
            f.write(linha)

        salvar_dados_aluno_inicial(dados['ra'], dados['nome_completo'], dados['curso'])
        print(f"✅ Usuário salvo: {dados['nome_completo']} (RA: {dados['ra']})")
        return True

    except Exception as e:
        print(f"❌ ERRO ao salvar usuário: {e}")
        return False


def buscar_usuario(ra):
    try:
        if not os.path.exists(NOME_ARQUIVO_USUARIOS):
            return None

        with open(NOME_ARQUIVO_USUARIOS, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if linha.startswith('#') or not linha:
                    continue

                partes = linha.split('|')
                if len(partes) >= 6 and partes[0] == ra:
                    return {
                        'ra': partes[0],
                        'nome': partes[1],
                        'email': partes[2],
                        'cpf': partes[3],
                        'curso': partes[4],
                        'senha_hash': partes[5],
                        'data_cadastro': partes[6] if len(partes) > 6 else 'N/A'
                    }

        return None

    except Exception as e:
        print(f"❌ ERRO ao buscar usuário: {e}")
        return None


def validar_login(ra, senha):
    usuario = buscar_usuario(ra)
    if not usuario:
        return False, None

    senha_hash = hash_senha(senha)
    if usuario['senha_hash'] == senha_hash:
        return True, usuario

    return False, None


# ============================================================================
# FUNÇÕES AUXILIARES - INTELIGÊNCIA ARTIFICIAL
# ============================================================================

def construir_prompt_sistema(ra_usuario):
    contexto_geral = carregar_contexto()
    dados_aluno = carregar_dados_aluno(ra_usuario)
    usuario = buscar_usuario(ra_usuario)
    nome_usuario = usuario['nome'] if usuario else "Aluno"
    curso_usuario = usuario['curso'] if usuario else "Não especificado"

    prompt = f"""Você é UniHelp, assistente acadêmica PERSONALIZADA da UniEVANGÉLICA.

INFORMAÇÕES DO USUÁRIO LOGADO:
Nome: {nome_usuario}
RA: {ra_usuario}
Curso: {curso_usuario}

BASE DE CONHECIMENTO GERAL:
{contexto_geral}

DADOS ESPECÍFICOS DESTE ALUNO:
{dados_aluno if dados_aluno else "Nenhum dado específico cadastrado ainda."}

REGRAS IMPORTANTES:
1. Use APENAS informações da base de conhecimento e dos dados específicos deste aluno
2. Quando o aluno perguntar sobre NOTAS, HISTÓRICO ou GRUPO, use APENAS os dados da seção "DADOS ESPECÍFICOS DESTE ALUNO"
3. NÃO forneça dados de outros alunos
4. NÃO use asteriscos, markdown ou negrito
5. Organize as respostas com estrutura clara
6. Seja pessoal e se refira ao aluno pelo nome quando apropriado

FORMATO PARA LISTAR CONTEÚDOS:

[CICLO_X]
[SEMANA_Y] Título

[MAT_VIDEO] Nome do vídeo
[LINK] url

[MAT_SLIDE] Nome do slide  
[LINK] url

[SEPARADOR]

IMPORTANTE: Seja concisa e objetiva
"""

    return prompt


def formatar_resposta(texto):
    import re

    texto = texto.replace('***', '').replace('**', '').replace('*', '')

    texto = re.sub(r'\[CICLO_(\d+)\]', r'<div class="ciclo-header">📚 CICLO \1</div>', texto)
    texto = re.sub(r'\[SEMANA_(\d+)\]\s*([^\n]+)', r'<div class="semana-header">📌 SEMANA \1: \2</div>', texto)
    texto = re.sub(r'\[MAT_VIDEO\]\s*([^\n]+)',
                   r'<div class="material-item"><span class="material-tipo">🎥 Vídeo:</span> \1</div>', texto)
    texto = re.sub(r'\[MAT_SLIDE\]\s*([^\n]+)',
                   r'<div class="material-item"><span class="material-tipo">📄 Slide:</span> \1</div>', texto)
    texto = re.sub(r'\[LINK\]\s*(https?://[^\s<]+)',
                   r'<div class="material-link">🔗 <a href="\1" target="_blank">\1</a></div>', texto)
    texto = re.sub(r'\[SEPARADOR\]', r'<div class="separador"></div>', texto)

    linhas = texto.split('\n')
    resultado = []

    for linha in linhas:
        linha = linha.strip()
        if linha and not any(tag in linha for tag in ['<div', '</div>']):
            resultado.append(f'<p>{linha}</p>')
        elif linha:
            resultado.append(linha)

    return '\n'.join(resultado)


def obter_resposta_gemini(historico_mensagens):
    """Versão SEM streaming - retorna resposta completa"""
    try:
        historico_gemini = []

        for msg in historico_mensagens:
            if msg['role'] == 'system':
                historico_gemini.append({'role': 'model', 'parts': [msg['content']]})
            elif msg['role'] == 'user':
                historico_gemini.append({'role': 'user', 'parts': [msg['content']]})
            elif msg['role'] == 'assistant':
                historico_gemini.append({'role': 'model', 'parts': [msg['content']]})

        print("\nINFO: Enviando requisição para o Gemini API...")

        chat = modelo_gemini.start_chat(history=historico_gemini[:-1])
        ultima_mensagem = historico_mensagens[-1]['content']

        resposta = chat.send_message(ultima_mensagem)

        print("INFO: Resposta recebida! ⚡")
        return resposta.text

    except Exception as e:
        print(f"ERRO: {e}")
        if "API_KEY" in str(e) or "invalid" in str(e).lower():
            return "ERRO: Chave de API inválida."
        elif "quota" in str(e).lower():
            return "ERRO: Limite de requisições atingido."
        else:
            return f"Erro ao conectar: {str(e)}"


# ============================================================================
# ROTAS DO SERVIDOR WEB
# ============================================================================

@app.route('/')
def index():
    if 'usuario_logado' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ra = request.form.get('ra', '').strip()
        senha = request.form.get('password', '')

        if not ra or not senha:
            return render_template('login.html', erro='Por favor, preencha todos os campos.')

        valido, usuario = validar_login(ra, senha)

        if valido:
            session['usuario_logado'] = ra
            session['nome_usuario'] = usuario['nome']
            session['curso_usuario'] = usuario['curso']
            print(f"✅ Login realizado: {usuario['nome']} (RA: {ra})")
            return redirect(url_for('chat'))
        else:
            return render_template('login.html', erro='RA ou senha incorretos.')

    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        dados = {
            'ra': request.form.get('ra', '').strip(),
            'nome_completo': request.form.get('nome_completo', '').strip(),
            'email': request.form.get('email', '').strip(),
            'cpf': request.form.get('cpf', '').strip(),
            'curso': request.form.get('curso', '').strip(),
            'senha': request.form.get('password', ''),
            'confirm_password': request.form.get('confirm_password', '')
        }

        if not all([dados['ra'], dados['nome_completo'], dados['email'],
                    dados['cpf'], dados['curso'], dados['senha']]):
            return render_template('cadastro.html', erro='Por favor, preencha todos os campos.')

        if dados['senha'] != dados['confirm_password']:
            return render_template('cadastro.html', erro='As senhas não coincidem.')

        if len(dados['senha']) < 6:
            return render_template('cadastro.html', erro='A senha deve ter no mínimo 6 caracteres.')

        if buscar_usuario(dados['ra']):
            return render_template('cadastro.html', erro='RA já cadastrado no sistema!')

        dados['senha_hash'] = hash_senha(dados['senha'])
        dados['data_cadastro'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        del dados['senha']
        del dados['confirm_password']

        if salvar_usuario(dados):
            return render_template('cadastro.html', sucesso='Cadastro realizado com sucesso! Faça login.')
        else:
            return render_template('cadastro.html', erro='Erro ao realizar cadastro. Tente novamente.')

    return render_template('cadastro.html')


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    ra_usuario = session['usuario_logado']

    if 'historico' not in session:
        prompt_sistema = construir_prompt_sistema(ra_usuario)
        session['historico'] = [{"role": "system", "content": prompt_sistema}]

    if request.method == 'POST':
        return redirect(url_for('chat'))

    historico_para_exibir = [msg for msg in session.get('historico', []) if msg['role'] != 'system']

    return render_template('index.html', historico=historico_para_exibir)


@app.route('/enviar_mensagem', methods=['POST'])
def enviar_mensagem():
    """Rota que processa mensagens com efeito de streaming"""
    if 'usuario_logado' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401

    ra_usuario = session['usuario_logado']
    data = request.get_json()
    pergunta = data.get('pergunta', '').strip()

    if not pergunta:
        return jsonify({'erro': 'Pergunta vazia'}), 400

    if 'historico' not in session:
        prompt_sistema = construir_prompt_sistema(ra_usuario)
        session['historico'] = [{"role": "system", "content": prompt_sistema}]

    # Adiciona pergunta ao histórico
    session['historico'].append({"role": "user", "content": pergunta})

    # Obtém resposta COMPLETA (sem streaming no backend por enquanto)
    resposta_texto = obter_resposta_gemini(session['historico'])

    # Formata a resposta
    resposta_formatada = formatar_resposta(resposta_texto)

    # Adiciona ao histórico
    session['historico'].append({"role": "assistant", "content": resposta_formatada})

    # Salva a conversa
    salvar_conversa(ra_usuario, pergunta, resposta_formatada)

    # Limita histórico
    if len(session['historico']) > 9:
        prompt_sistema = construir_prompt_sistema(ra_usuario)
        session['historico'] = [{"role": "system", "content": prompt_sistema}] + session['historico'][-8:]

    session.modified = True

    # Retorna a resposta completa para o JavaScript simular o streaming
    return jsonify({
        'resposta': resposta_formatada,
        'sucesso': True
    })


@app.route('/historico')
def historico():
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    ra_usuario = session['usuario_logado']
    conversas = carregar_historico_aluno(ra_usuario, limite=50)

    return render_template('historico.html', conversas=conversas)


@app.route('/limpar', methods=['POST'])
def limpar_historico():
    ra_usuario = session.get('usuario_logado')
    session.pop('historico', None)

    if ra_usuario:
        prompt_sistema = construir_prompt_sistema(ra_usuario)
        session['historico'] = [{"role": "system", "content": prompt_sistema}]

    print("INFO: Histórico limpo pelo usuário")
    return '', 204


@app.route('/logout')
def logout():
    nome = session.get('nome_usuario', 'Usuário')
    print(f"👋 Logout: {nome}")
    session.clear()
    return redirect(url_for('login'))


# ============================================================================
# INICIALIZAÇÃO DO SERVIDOR
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("🎓 SISTEMA UNIHELP - ASSISTENTE PERSONALIZADA")
    print("=" * 70)
    print(f"✅ Modelo IA: {modelo_gemini.model_name}")
    print(f"✅ Base de conhecimento: {NOME_ARQUIVO_CONTEXTO}")
    print(f"✅ Banco de usuários: {NOME_ARQUIVO_USUARIOS}")
    print(f"✅ Dados personalizados: {NOME_ARQUIVO_DADOS_ALUNOS}")
    print(f"✅ Histórico de conversas: {NOME_ARQUIVO_HISTORICO}")

    contexto = carregar_contexto()
    print(f"✅ Contexto carregado: {len(contexto)} caracteres")

    if os.path.exists(NOME_ARQUIVO_USUARIOS):
        with open(NOME_ARQUIVO_USUARIOS, 'r', encoding='utf-8') as f:
            usuarios = [l for l in f if not l.startswith('#') and l.strip()]
            print(f"✅ Usuários cadastrados: {len(usuarios)}")
    else:
        print("⚠️  Nenhum usuário cadastrado ainda")

    print("\n🌐 Servidor iniciado em: http://localhost:5000")
    print("   • /login     → Tela de login")
    print("   • /cadastro  → Tela de cadastro")
    print("   • /chat      → Chat com efeito de digitação")
    print("   • /historico → Ver histórico de conversas")
    print("=" * 70)

    app.run(debug=True)