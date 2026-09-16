from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "financely.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Tabela de contas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                tipo TEXT NOT NULL,
                categoria TEXT NOT NULL,
                mes INTEGER NOT NULL,
                ano INTEGER NOT NULL,
                mensal INTEGER DEFAULT 0,
                vencimento_dia INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pendente',
                eh_cartao INTEGER DEFAULT 0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Tabela de categorias
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            )
        """)
        padrao = ['Alimentação', 'Cartão de Crédito', 'Moradia', 'Transporte', 'Lazer', 'Saúde', 'Salário/Renda', 'Outros']
        for c in padrao:
            conn.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (c,))

        # Tabela de notas estilo Google Keep
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                conteudo TEXT NOT NULL,
                cor TEXT DEFAULT '#ffffff',
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/categorias', methods=['GET', 'POST'])
def handle_categorias():
    with get_db() as conn:
        if request.method == 'POST':
            data = request.get_json(force=True)
            nome = str(data.get('nome', '')).strip()
            if nome:
                conn.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (nome,))
                conn.commit()
            return jsonify({"sucesso": True})
        rows = conn.execute("SELECT nome FROM categorias ORDER BY nome ASC").fetchall()
        return jsonify([r['nome'] for r in rows])

@app.route('/api/notas', methods=['GET', 'POST'])
def handle_notas():
    with get_db() as conn:
        if request.method == 'POST':
            data = request.get_json(force=True)
            titulo = str(data.get('titulo', '')).strip()
            conteudo = str(data.get('conteudo', '')).strip()
            cor = str(data.get('cor', '#ffffff'))
            if not conteudo:
                return jsonify({"erro": "O conteúdo não pode ser vazio."}), 400
            conn.execute("INSERT INTO notas (titulo, conteudo, cor) VALUES (?, ?, ?)", (titulo, conteudo, cor))
            conn.commit()
            return jsonify({"sucesso": True}), 201
        rows = conn.execute("SELECT id, titulo, conteudo, cor, data_criacao FROM notas ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/notas/<int:id>', methods=['DELETE', 'PUT'])
def item_nota(id):
    with get_db() as conn:
        if request.method == 'DELETE':
            conn.execute("DELETE FROM notas WHERE id = ?", (id,))
            conn.commit()
            return jsonify({"sucesso": True})
        data = request.get_json(force=True)
        conn.execute("UPDATE notas SET titulo = ?, conteudo = ?, cor = ? WHERE id = ?",
                     (data.get('titulo', ''), data.get('conteudo', ''), data.get('cor', '#ffffff'), id))
        conn.commit()
        return jsonify({"sucesso": True})

@app.route('/api/resumo', methods=['GET'])
def get_resumo():
    mes = request.args.get('mes', default=datetime.now().month, type=int)
    ano = request.args.get('ano', default=datetime.now().year, type=int)
    hoje_dia = datetime.now().day

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, descricao, valor, tipo, categoria, vencimento_dia, status, eh_cartao 
            FROM contas 
            WHERE (mes = ? AND ano = ?) OR mensal = 1 
            ORDER BY vencimento_dia ASC, id ASC
        """, (mes, ano))
        rows = cursor.fetchall()

    total_receitas = 0.0
    total_despesas = 0.0
    total_cartao = 0.0
    cat_totais = {}
    labels = []
    receitas = []
    despesas = []
    lembretes = []

    for r in rows:
        desc = r['descricao']
        val = float(r['valor'])
        tipo = r['tipo']
        cat = r['categoria']
        venc = r['vencimento_dia']
        st = r['status']
        cartao = bool(r['eh_cartao'])

        labels.append(desc)
        if tipo == 'receita':
            total_receitas += val
            receitas.append(val)
            despesas.append(0)
        else:
            total_despesas += val
            receitas.append(0)
            despesas.append(val)
            cat_totais[cat] = cat_totais.get(cat, 0.0) + val
            if cartao:
                total_cartao += val

            # Lembretes de Vencimento
            if st == 'pendente':
                if venc < hoje_dia:
                    lembretes.append({"msg": f"Atrasada: {desc} (Dia {venc})", "tipo": "atrasada", "valor": val})
                elif venc == hoje_dia:
                    lembretes.append({"msg": f"Vence Hoje: {desc}", "tipo": "hoje", "valor": val})
                elif venc <= hoje_dia + 3:
                    lembretes.append({"msg": f"Vence em breve: {desc} (Dia {venc})", "tipo": "proxima", "valor": val})

    saldo_total = total_receitas - total_despesas
    ranking = sorted([{"categoria": k, "total": v} for k, v in cat_totais.items()], key=lambda x: x["total"], reverse=True)

    if total_receitas == 0 and total_despesas == 0:
        status, titulo, score = "neutro", "Sem Movimentação", 0
        msg = "Cadastre suas contas do mês para receber sua análise financeira."
    elif total_receitas > 0 and total_despesas == 0:
        status, titulo, score = "otima", "Excelente!", 100
        msg = "Sem despesas registradas este mês. Excelente momento para poupar!"
    else:
        pct = (total_despesas / total_receitas * 100) if total_receitas > 0 else 100
        if pct <= 60:
            status, titulo, score = "otima", "Saúde Forte", 90
            msg = f"Você usou {pct:.0f}% dos ganhos. Sobra boa margem."
        elif pct <= 85:
            status, titulo, score = "alerta", "Atenção", 60
            msg = f"Seus gastos somam {pct:.0f}% da renda. Modere compras supérfluas."
        else:
            status, titulo, score = "critica", "Sinal Vermelho", 30
            msg = "Despesas superaram a margem segura. Priorize quitar pendências."

    return jsonify({
        "saldo_total": saldo_total,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "total_cartao": total_cartao,
        "ranking_gastos": ranking,
        "labels": labels,
        "receitas": receitas,
        "despesas": despesas,
        "lembretes": lembretes,
        "saude": {"status": status, "titulo": titulo, "mensagem": msg, "score": score}
    })

@app.route('/api/contas', methods=['POST'])
def add_conta():
    data = request.get_json(force=True)
    descricao = str(data.get('descricao', '')).strip()
    valor = float(data.get('valor', 0))
    tipo = data.get('tipo', 'despesa')
    categoria = data.get('categoria', 'Outros')
    mes = int(data.get('mes', datetime.now().month))
    ano = int(data.get('ano', datetime.now().year))
    mensal = 1 if data.get('mensal') else 0
    vencimento_dia = int(data.get('vencimento_dia', 1))
    eh_cartao = 1 if data.get('eh_cartao') else 0
    status = data.get('status', 'pendente')

    if not descricao or valor <= 0:
        return jsonify({"erro": "Informe descrição e valor válido."}), 400

    with get_db() as conn:
        conn.execute("""
            INSERT INTO contas (descricao, valor, tipo, categoria, mes, ano, mensal, vencimento_dia, status, eh_cartao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (descricao, valor, tipo, categoria, mes, ano, mensal, vencimento_dia, status, eh_cartao))
        conn.commit()

    return jsonify({"sucesso": True}), 201

@app.route('/api/contas/<int:id>', methods=['PUT', 'DELETE'])
def update_or_delete_conta(id):
    with get_db() as conn:
        if request.method == 'DELETE':
            conn.execute("DELETE FROM contas WHERE id = ?", (id,))
            conn.commit()
            return jsonify({"sucesso": True})
        
        data = request.get_json(force=True)
        if 'status' in data and len(data) == 1:
            conn.execute("UPDATE contas SET status = ? WHERE id = ?", (data['status'], id))
        else:
            conn.execute("""
                UPDATE contas SET 
                    descricao = ?, valor = ?, tipo = ?, categoria = ?, 
                    vencimento_dia = ?, status = ?, eh_cartao = ?, mensal = ?
                WHERE id = ?
            """, (
                data['descricao'], float(data['valor']), data['tipo'], data['categoria'],
                int(data['vencimento_dia']), data['status'], 1 if data['eh_cartao'] else 0,
                1 if data['mensal'] else 0, id
            ))
        conn.commit()
        return jsonify({"sucesso": True})

@app.route('/api/faturas_ano', methods=['GET'])
def get_faturas_ano():
    ano = request.args.get('ano', default=datetime.now().year, type=int)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas ORDER BY vencimento_dia ASC")
        rows = cursor.fetchall()

    faturas = {m: {"mes": m, "total_despesas": 0.0, "total_receitas": 0.0, "total_cartao": 0.0, "itens": []} for m in range(1, 13)}
    for r in rows:
        item = dict(r)
        item['mensal'] = bool(item['mensal'])
        item['eh_cartao'] = bool(item['eh_cartao'])

        alvos = range(1, 13) if item['mensal'] else ([item['mes']] if item['ano'] == ano and 1 <= item['mes'] <= 12 else [])
        for m in alvos:
            faturas[m]["itens"].append(item)
            if item['tipo'] == 'receita':
                faturas[m]["total_receitas"] += item['valor']
            else:
                faturas[m]["total_despesas"] += item['valor']
                if item['eh_cartao']:
                    faturas[m]["total_cartao"] += item['valor']

    return jsonify(list(faturas.values()))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
