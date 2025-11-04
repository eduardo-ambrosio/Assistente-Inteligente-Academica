import os  # Para operações com arquivos e sistema operacional
import hashlib  # Para criptografar senhas com hash SHA-256
from datetime import datetime  # Para registrar data/hora de cadastro
import google.generativeai as genai  # API do Google Gemini para IA
from flask import Flask, render_template, request, session, redirect, url_for, flash

# ============================================================================
# CONFIGURAÇÕES INICIAIS DO SERVIDOR FLASK
# ============================================================================

app = Flask(__name__, template_folder='templates', static_folder='static')
# template_folder: pasta onde ficam os arquivos HTML
# static_folder: pasta para CSS, imagens, JS

# Gera uma chave secreta aleatória para proteger as sessões dos usuários
# Isso impede que alguém falsifique cookies de sessão
app.secret_key = os.urandom(24)

# ============================================================================
# CONFIGURAÇÕES DA API DO GOOGLE GEMINI (IA)
# ============================================================================

# Chave da API do Google Gemini (IMPORTANTE: Em produção, usar variável de ambiente)
GOOGLE_API_KEY = ""

# Configura a biblioteca do Gemini com a chave
genai.configure(api_key=GOOGLE_API_KEY)

# Cria uma instância do modelo de IA (Flash é o modelo mais rápido)
modelo_gemini = genai.GenerativeModel('gemini-2.5-flash')

# ============================================================================
# DEFINIÇÃO DOS ARQUIVOS DE DADOS (BANCO DE DADOS EM TXT)
# ============================================================================

# Arquivo que contém toda a base de conhecimento (horários, materiais, etc)
NOME_ARQUIVO_CONTEXTO = "banco_dados.txt"

# Arquivo que armazena os usuários cadastrados (RA, nome, senha hash, etc)
NOME_ARQUIVO_USUARIOS = "usuarios.txt"


# ============================================================================
# FUNÇÕES AUXILIARES - GERENCIAMENTO DE DADOS
# ============================================================================

def carregar_contexto():
    """
    Carrega todo o conteúdo da base de conhecimento do arquivo TXT.

    Este arquivo contém:
    - Horários das aulas
    - Lista de disciplinas e professores
    - Materiais de estudo (vídeos, slides)
    - Calendário acadêmico
    - Notas e histórico

    Returns:
        str: Conteúdo completo do arquivo ou mensagem de aviso
    """
    try:
        # Abre o arquivo com codificação UTF-8 (suporta acentos)
        with open(NOME_ARQUIVO_CONTEXTO, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # Se o arquivo não existir, exibe aviso e retorna texto padrão
        print(f"AVISO: Arquivo de contexto '{NOME_ARQUIVO_CONTEXTO}' não encontrado.")
        return "Nenhum contexto específico fornecido."


def hash_senha(senha):
    """
    Criptografa a senha usando o algoritmo SHA-256.

    IMPORTANTE: Nunca armazenamos senhas em texto puro por segurança!
    O hash é uma via única: não é possível "descriptografar" de volta.

    Exemplo:
        "senha123" → "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"

    Args:
        senha (str): Senha em texto puro

    Returns:
        str: Hash hexadecimal da senha
    """
    # Converte a string para bytes e aplica SHA-256
    return hashlib.sha256(senha.encode()).hexdigest()


def salvar_usuario(dados):
    """
    Salva um novo usuário no arquivo TXT de usuários.

    Estrutura do arquivo:
    RA|NOME|EMAIL|CPF|CURSO|SENHA_HASH|DATA_CADASTRO

    Exemplo de linha:
    202301234|João Silva|joao@email.com|123.456.789-00|IA|hash...|2025-11-03 14:30:45

    Args:
        dados (dict): Dicionário com os dados do usuário

    Returns:
        bool: True se salvou com sucesso, False se houve erro
    """
    try:
        # Se o arquivo não existe, cria ele com o cabeçalho
        if not os.path.exists(NOME_ARQUIVO_USUARIOS):
            with open(NOME_ARQUIVO_USUARIOS, 'w', encoding='utf-8') as f:
                # Escreve cabeçalho explicativo
                f.write("# ============================================\n")
                f.write("# BANCO DE DADOS DE USUÁRIOS - UNIHELP\n")
                f.write("# ============================================\n")
                f.write("# Estrutura: RA|NOME|EMAIL|CPF|CURSO|SENHA_HASH|DATA_CADASTRO\n")
                f.write("# " + "=" * 80 + "\n\n")

        # Adiciona novo usuário ao final do arquivo (modo 'a' = append)
        with open(NOME_ARQUIVO_USUARIOS, 'a', encoding='utf-8') as f:
            # Monta a linha com os dados separados por pipe (|)
            linha = f"{dados['ra']}|{dados['nome_completo']}|{dados['email']}|{dados['cpf']}|{dados['curso']}|{dados['senha_hash']}|{dados['data_cadastro']}\n"
            f.write(linha)

        # Log de sucesso no console
        print(f"✅ Usuário salvo: {dados['nome_completo']} (RA: {dados['ra']})")
        return True

    except Exception as e:
        # Se algo deu errado, exibe o erro
        print(f"❌ ERRO ao salvar usuário: {e}")
        return False


def buscar_usuario(ra):
    """
    Busca um usuário no arquivo TXT pelo RA (Registro Acadêmico).

    Lê o arquivo linha por linha e compara o RA até encontrar ou
    chegar ao fim do arquivo.

    Args:
        ra (str): Número do RA do aluno

    Returns:
        dict ou None: Dicionário com os dados do usuário ou None se não encontrou
    """
    try:
        # Verifica se o arquivo existe antes de tentar ler
        if not os.path.exists(NOME_ARQUIVO_USUARIOS):
            return None

        # Abre o arquivo para leitura
        with open(NOME_ARQUIVO_USUARIOS, 'r', encoding='utf-8') as f:
            # Percorre cada linha do arquivo
            for linha in f:
                linha = linha.strip()  # Remove espaços em branco e quebras de linha

                # Ignora linhas de comentário (#) e linhas vazias
                if linha.startswith('#') or not linha:
                    continue

                # Separa os dados da linha pelo pipe (|)
                partes = linha.split('|')

                # Verifica se tem pelo menos 6 campos e se o RA bate
                if len(partes) >= 6 and partes[0] == ra:
                    # Retorna um dicionário com os dados estruturados
                    return {
                        'ra': partes[0],
                        'nome': partes[1],
                        'email': partes[2],
                        'cpf': partes[3],
                        'curso': partes[4],
                        'senha_hash': partes[5],
                        'data_cadastro': partes[6] if len(partes) > 6 else 'N/A'
                    }

        # Se chegou aqui, não encontrou o usuário
        return None

    except Exception as e:
        print(f"❌ ERRO ao buscar usuário: {e}")
        return None


def validar_login(ra, senha):
    """
    Valida as credenciais de login do usuário.

    Processo:
    1. Busca o usuário pelo RA
    2. Criptografa a senha informada
    3. Compara com o hash armazenado

    Args:
        ra (str): RA do usuário
        senha (str): Senha em texto puro

    Returns:
        tuple: (bool_valido, dict_usuario ou None)
        Exemplos: (True, {...dados...}) ou (False, None)
    """
    # Busca o usuário no arquivo
    usuario = buscar_usuario(ra)

    # Se não encontrou, login inválido
    if not usuario:
        return False, None

    # Criptografa a senha fornecida para comparar
    senha_hash = hash_senha(senha)

    # Compara o hash gerado com o hash armazenado
    if usuario['senha_hash'] == senha_hash:
        return True, usuario  # Login válido

    return False, None  # Senha incorreta


# ============================================================================
# FUNÇÕES AUXILIARES - INTELIGÊNCIA ARTIFICIAL
# ============================================================================

def construir_prompt_sistema():
    """
    Cria as instruções iniciais (prompt) para a IA.

    O prompt define:
    - Quem é a IA (UniHelp, assistente da UniEVANGÉLICA)
    - Como ela deve formatar as respostas
    - Quais informações ela pode usar (base de conhecimento)
    - Regras de formatação com tags especiais

    As tags [CICLO_X], [SEMANA_Y], etc. são marcadores que depois
    serão convertidos em HTML formatado.

    Returns:
        str: Prompt completo para inicializar a IA
    """
    # Carrega todo o conteúdo da base de conhecimento
    contexto_texto = carregar_contexto()

    # Monta o prompt com instruções detalhadas
    prompt = f"""Você é UniHelp, assistente acadêmica da UniEVANGÉLICA.

BASE DE CONHECIMENTO:
{contexto_texto}

REGRAS DE FORMATAÇÃO (SIGA EXATAMENTE):

1. Use APENAS informações da base de conhecimento
2. NÃO use asteriscos, markdown ou negrito
3. Organize as respostas com estrutura clara e hierárquica

FORMATO PADRÃO PARA LISTAR CONTEÚDOS:

[CICLO_X]
[SEMANA_Y] Título do Conteúdo

[MAT_VIDEO] Nome do vídeo
[LINK] url_completa

[MAT_SLIDE] Nome do slide  
[LINK] url_completa

[SEPARADOR]

EXEMPLO DE RESPOSTA CORRETA:

[CICLO_01]
[SEMANA_01] Inteligência Artificial no Trabalho

[MAT_VIDEO] Mapeamento de processos
[LINK] https://youtu.be/nC7_jjPZ3ys

[MAT_SLIDE] Ciclo de Vida de Soluções em IA
[LINK] https://drive.google.com/file/d/1peR1Xrwn2ggUVQ2lzvc1GY8J_qTDZDU9

[SEPARADOR]

[SEMANA_02] Design Thinking

[MAT_VIDEO] O que é Design Thinking?
[LINK] https://youtu.be/7hZMGSamsYA

[SEPARADOR]

IMPORTANTE:
- Use [CICLO_X] para iniciar cada ciclo
- Use [SEMANA_Y] para cada semana
- Use [MAT_VIDEO] ou [MAT_SLIDE] antes do nome do material
- Use [LINK] antes de cada URL
- Use [SEPARADOR] entre semanas
- Seja concisa e objetiva"""

    return prompt


def formatar_resposta(texto):
    """
    Converte as tags especiais da IA em HTML formatado.

    Transforma:
    [CICLO_1] → <div class="ciclo-header">📚 CICLO 1</div>
    [SEMANA_2] → <div class="semana-header">📌 SEMANA 2: Título</div>
    [MAT_VIDEO] → <div class="material-item">🎥 Vídeo: Nome</div>
    [LINK] → <div class="material-link">🔗 <a>link</a></div>

    O CSS irá estilizar essas classes para criar a interface visual.

    Args:
        texto (str): Resposta da IA com tags especiais

    Returns:
        str: HTML formatado pronto para exibir no navegador
    """
    import re  # Biblioteca para expressões regulares (regex)

    # Remove asteriscos que a IA possa ter usado por engano
    texto = texto.replace('***', '').replace('**', '').replace('*', '')

    # Substitui [CICLO_X] por HTML com classe CSS
    texto = re.sub(
        r'\[CICLO_(\d+)\]',  # Padrão: [CICLO_ seguido de números]
        r'<div class="ciclo-header">📚 CICLO \1</div>',  # \1 = primeiro grupo capturado (número)
        texto
    )

    # Substitui [SEMANA_Y] Título por HTML
    texto = re.sub(
        r'\[SEMANA_(\d+)\]\s*([^\n]+)',  # Captura número e título
        r'<div class="semana-header">📌 SEMANA \1: \2</div>',
        texto
    )

    # Substitui [MAT_VIDEO] Nome por HTML
    texto = re.sub(
        r'\[MAT_VIDEO\]\s*([^\n]+)',
        r'<div class="material-item"><span class="material-tipo">🎥 Vídeo:</span> \1</div>',
        texto
    )

    # Substitui [MAT_SLIDE] Nome por HTML
    texto = re.sub(
        r'\[MAT_SLIDE\]\s*([^\n]+)',
        r'<div class="material-item"><span class="material-tipo">📄 Slide:</span> \1</div>',
        texto
    )

    # Substitui [LINK] url por HTML com link clicável
    texto = re.sub(
        r'\[LINK\]\s*(https?://[^\s<]+)',  # Captura URLs http/https
        r'<div class="material-link">🔗 <a href="\1" target="_blank">\1</a></div>',
        texto
    )

    # Substitui [SEPARADOR] por linha divisória
    texto = re.sub(
        r'\[SEPARADOR\]',
        r'<div class="separador"></div>',
        texto
    )

    # Processa linhas que não têm tags HTML
    linhas = texto.split('\n')
    resultado = []

    for linha in linhas:
        linha = linha.strip()
        # Se não é HTML e não está vazia, envolve em parágrafo
        if linha and not any(tag in linha for tag in ['<div', '</div>']):
            resultado.append(f'<p>{linha}</p>')
        elif linha:
            resultado.append(linha)

    return '\n'.join(resultado)


def obter_resposta_gemini(historico_mensagens):
    """
    Envia o histórico de conversa para a API do Gemini e obtém resposta.

    Processo:
    1. Converte o histórico para o formato que a API do Gemini entende
    2. Cria uma sessão de chat com o histórico
    3. Envia a última mensagem do usuário
    4. Recebe e formata a resposta da IA

    Args:
        historico_mensagens (list): Lista de dicionários com role e content

    Returns:
        str: Resposta da IA formatada em HTML
    """
    try:
        historico_gemini = []

        # Converte cada mensagem do histórico para o formato da API
        for msg in historico_mensagens:
            if msg['role'] == 'system':
                # Mensagens de sistema viram mensagens do modelo
                historico_gemini.append({
                    'role': 'model',
                    'parts': [msg['content']]
                })
            elif msg['role'] == 'user':
                # Mensagens do usuário mantém o role 'user'
                historico_gemini.append({
                    'role': 'user',
                    'parts': [msg['content']]
                })
            elif msg['role'] == 'assistant':
                # Mensagens do assistente viram mensagens do modelo
                historico_gemini.append({
                    'role': 'model',
                    'parts': [msg['content']]
                })

        print("\nINFO: Enviando requisição para o Gemini API...")

        # Inicia uma conversa com todo o histórico (exceto a última mensagem)
        chat = modelo_gemini.start_chat(history=historico_gemini[:-1])

        # Pega a última mensagem (a pergunta atual do usuário)
        ultima_mensagem = historico_mensagens[-1]['content']

        # Envia para a IA e aguarda resposta
        resposta = chat.send_message(ultima_mensagem)

        print("INFO: Resposta recebida do Gemini! ⚡")

        # Formata a resposta convertendo tags em HTML
        resposta_formatada = formatar_resposta(resposta.text)
        return resposta_formatada

    except Exception as e:
        # Tratamento de erros com mensagens específicas
        print(f"ERRO: {e}")

        if "API_KEY" in str(e) or "invalid" in str(e).lower():
            return "<p class='erro'>❌ ERRO: Chave de API inválida.</p>"
        elif "quota" in str(e).lower():
            return "<p class='erro'>⚠️ ERRO: Limite de requisições atingido. Tente amanhã.</p>"
        else:
            return f"<p class='erro'>❌ Erro ao conectar: {str(e)}</p>"


# ============================================================================
# ROTAS DO SERVIDOR WEB (FLASK)
# ============================================================================
# Cada @app.route define uma URL que o usuário pode acessar

@app.route('/')
def index():
    """
    Rota raiz: http://localhost:5000/

    Redireciona o usuário:
    - Se está logado → vai para o chat
    - Se não está logado → vai para o login
    """
    if 'usuario_logado' in session:  # session = cookies da sessão
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Rota de login: http://localhost:5000/login

    GET: Exibe o formulário de login
    POST: Processa o login e valida credenciais
    """
    if request.method == 'POST':
        # Pega os dados enviados pelo formulário
        ra = request.form.get('ra', '').strip()
        senha = request.form.get('password', '')

        # Validação básica: campos não podem estar vazios
        if not ra or not senha:
            return render_template('login.html', erro='Por favor, preencha todos os campos.')

        # Valida as credenciais comparando com o arquivo TXT
        valido, usuario = validar_login(ra, senha)

        if valido:
            # Login bem-sucedido: salva dados na sessão
            session['usuario_logado'] = ra
            session['nome_usuario'] = usuario['nome']
            print(f"✅ Login realizado: {usuario['nome']} (RA: {ra})")
            return redirect(url_for('chat'))  # Redireciona para o chat
        else:
            # Credenciais inválidas: mostra erro
            return render_template('login.html', erro='RA ou senha incorretos.')

    # Se for GET, apenas mostra o formulário
    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """
    Rota de cadastro: http://localhost:5000/cadastro

    GET: Exibe o formulário de cadastro
    POST: Processa e salva novo usuário
    """
    if request.method == 'POST':
        # Coleta todos os dados do formulário
        dados = {
            'ra': request.form.get('ra', '').strip(),
            'nome_completo': request.form.get('nome_completo', '').strip(),
            'email': request.form.get('email', '').strip(),
            'cpf': request.form.get('cpf', '').strip(),
            'curso': request.form.get('curso', '').strip(),
            'senha': request.form.get('password', ''),
            'confirm_password': request.form.get('confirm_password', '')
        }

        # VALIDAÇÃO 1: Todos os campos devem estar preenchidos
        if not all([dados['ra'], dados['nome_completo'], dados['email'],
                    dados['cpf'], dados['curso'], dados['senha']]):
            return render_template('cadastro.html', erro='Por favor, preencha todos os campos.')

        # VALIDAÇÃO 2: As senhas devem ser iguais
        if dados['senha'] != dados['confirm_password']:
            return render_template('cadastro.html', erro='As senhas não coincidem.')

        # VALIDAÇÃO 3: Senha deve ter pelo menos 6 caracteres
        if len(dados['senha']) < 6:
            return render_template('cadastro.html', erro='A senha deve ter no mínimo 6 caracteres.')

        # VALIDAÇÃO 4: RA não pode estar cadastrado
        if buscar_usuario(dados['ra']):
            return render_template('cadastro.html', erro='RA já cadastrado no sistema!')

        # Prepara os dados para salvar
        dados['senha_hash'] = hash_senha(dados['senha'])  # Criptografa a senha
        dados['data_cadastro'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Registra data/hora

        # Remove campos temporários que não serão salvos
        del dados['senha']  # Nunca salvar senha em texto puro!
        del dados['confirm_password']

        # Salva no arquivo TXT
        if salvar_usuario(dados):
            # Sucesso: mostra mensagem e sugere fazer login
            return render_template('cadastro.html', sucesso='Cadastro realizado com sucesso! Faça login.')
        else:
            # Erro ao salvar: mostra mensagem de erro
            return render_template('cadastro.html', erro='Erro ao realizar cadastro. Tente novamente.')

    # Se for GET, apenas mostra o formulário
    return render_template('cadastro.html')


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    """
    Rota do chat: http://localhost:5000/chat

    Esta é a página principal do sistema, onde o usuário conversa
    com a IA. Requer login obrigatório.

    GET: Exibe o chat com histórico
    POST: Processa nova mensagem do usuário
    """
    # Verifica se o usuário está logado
    if 'usuario_logado' not in session:
        return redirect(url_for('login'))

    # Se é o primeiro acesso, inicializa o histórico com o prompt do sistema
    if 'historico' not in session:
        prompt_sistema = construir_prompt_sistema()
        session['historico'] = [{"role": "system", "content": prompt_sistema}]

    # Se o usuário enviou uma mensagem (POST)
    if request.method == 'POST':
        pergunta_usuario = request.form.get('pergunta', '').strip()

        if pergunta_usuario:
            # Adiciona a pergunta do usuário ao histórico
            session['historico'].append({"role": "user", "content": pergunta_usuario})

            # Envia para a IA e obtém resposta
            resposta_ia = obter_resposta_gemini(session['historico'])

            # Adiciona a resposta da IA ao histórico
            session['historico'].append({"role": "assistant", "content": resposta_ia})

            # Limita o histórico para não ficar muito grande
            # Mantém apenas o prompt do sistema + últimas 8 mensagens
            if len(session['historico']) > 9:
                session['historico'] = [session['historico'][0]] + session['historico'][-8:]

            # Marca que a sessão foi modificada (para salvar nos cookies)
            session.modified = True

    # Filtra apenas mensagens visíveis (remove o prompt do sistema)
    historico_para_exibir = [msg for msg in session.get('historico', []) if msg['role'] != 'system']

    # Renderiza a página do chat com o histórico
    return render_template('index.html', historico=historico_para_exibir)


@app.route('/limpar', methods=['POST'])
def limpar_historico():
    """
    Rota para limpar o histórico de conversa.

    Remove todas as mensagens do chat, permitindo começar uma nova conversa.
    """
    session.pop('historico', None)  # Remove o histórico da sessão
    print("INFO: Histórico limpo pelo usuário")
    return '', 204  # Retorna resposta vazia com código 204 (No Content)


@app.route('/logout')
def logout():
    """
    Rota de logout: http://localhost:5000/logout

    Encerra a sessão do usuário e redireciona para o login.
    """
    nome = session.get('nome_usuario', 'Usuário')
    print(f"👋 Logout: {nome}")
    session.clear()  # Limpa todos os dados da sessão
    return redirect(url_for('login'))


# ============================================================================
# INICIALIZAÇÃO DO SERVIDOR
# ============================================================================

if __name__ == '__main__':
    # Este bloco só executa quando o arquivo é rodado diretamente
    # (não quando é importado como módulo)

    # Exibe informações do sistema no console
    print("=" * 70)
    print("🎓 SISTEMA UNIHELP - ASSISTENTE ACADÊMICA INTELIGENTE")
    print("=" * 70)
    print(f"✅ Modelo IA: {modelo_gemini.model_name}")
    print(f"✅ Base de conhecimento: {NOME_ARQUIVO_CONTEXTO}")
    print(f"✅ Banco de usuários: {NOME_ARQUIVO_USUARIOS}")

    # Carrega e exibe informações da base de conhecimento
    contexto = carregar_contexto()
    print(f"✅ Contexto carregado: {len(contexto)} caracteres")

    # Verifica quantos usuários estão cadastrados
    if os.path.exists(NOME_ARQUIVO_USUARIOS):
        with open(NOME_ARQUIVO_USUARIOS, 'r', encoding='utf-8') as f:
            # Conta linhas que não são comentários
            usuarios = [l for l in f if not l.startswith('#') and l.strip()]
            print(f"✅ Usuários cadastrados: {len(usuarios)}")
    else:
        print("⚠️  Nenhum usuário cadastrado ainda")

    # Mostra as URLs disponíveis
    print("\n🌐 Servidor iniciado em: http://localhost:5000")
    print("   • /login    → Tela de login")
    print("   • /cadastro → Tela de cadastro")
    print("   • /chat     → Chat (requer login)")
    print("=" * 70)

    # Inicia o servidor Flask
    # debug=True: Reinicia automaticamente quando o código é modificado
    # e mostra erros detalhados no navegador
    app.run(debug=True)