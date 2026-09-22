from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime
import re

app = Flask(__name__)
DB_NAME = "financely.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL
            )
        """)
        padrao = ['Alimentação', 'Cartão de Crédito', 'Moradia', 'Transporte', 'Lazer', 'Saúde', 'Salário/Renda', 'Outros']
        for c in padrao:
            conn.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (c,))

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

@app.route('/api/chat', methods=['POST'])
def finance_chat():
    data = request.get_json(force=True) or {}
    pergunta = str(data.get('mensagem', '')).strip().lower()
    
    if not pergunta:
        return jsonify({"resposta": "Por favor, digite sua pergunta sobre suas finanças!"})

    mes_atual = datetime.now().month
    ano_atual = datetime.now().year
    hoje_dia = datetime.now().day

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contas WHERE (mes = ? AND ano = ?) OR mensal = 1", (mes_atual, ano_atual))
        contas_mes = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM notas ORDER BY id DESC")
        notas_app = [dict(r) for r in cursor.fetchall()]

    # Métricas calculadas em tempo real
    receitas = [c for c in contas_mes if c['tipo'] == 'receita']
    despesas = [c for c in contas_mes if c['tipo'] == 'despesa']
    
    total_receitas = sum(c['valor'] for c in receitas)
    total_despesas = sum(c['valor'] for c in despesas)
    saldo = total_receitas - total_despesas
    
    despesas_cartao = [c for c in despesas if c['eh_cartao']]
    total_cartao = sum(c['valor'] for c in despesas_cartao)
    
    contas_atrasadas = [c for c in despesas if c['status'] == 'pendente' and c['vencimento_dia'] < hoje_dia]
    contas_hoje = [c for c in despesas if c['status'] == 'pendente' and c['vencimento_dia'] == hoje_dia]
    contas_pendentes = [c for c in despesas if c['status'] == 'pendente']

    # Raciocínio por categorias
    cat_totais = {}
    for c in despesas:
        cat = c['categoria']
        cat_totais[cat] = cat_totais.get(cat, 0.0) + c['valor']
    maior_categoria = max(cat_totais.items(), key=lambda x: x[1]) if cat_totais else None

    # Motor de raciocínio da IA interna do Financely
    if any(p in pergunta for p in ['saldo', 'quanto tenho', 'balanço', 'lucro']):
        estado = "positivo (no azul) 🟢" if saldo >= 0 else "negativo (no vermelho) 🔴"
        resposta = (f"Seu saldo atual no mês é de **R$ {saldo:,.2f}** ({estado}).\n\n"
                    f"• Entradas totais: R$ {total_receitas:,.2f}\n"
                    f"• Saídas totais: R$ {total_despesas:,.2f}")

    elif any(p in pergunta for p in ['cartao', 'cartão', 'fatura do cartao', 'crédito']):
        if total_cartao > 0:
            itens = "\n".join([f"  - {c['descricao']}: R$ {c['valor']:,.2f} (Venc. dia {c['vencimento_dia']})" for c in despesas_cartao])
            resposta = (f"💳 O total lançado no cartão de crédito este mês é de **R$ {total_cartao:,.2f}**.\n\n"
                        f"Detalhamento:\n{itens}")
        else:
            resposta = "Você não possui nenhuma despesa marcada no cartão de crédito este mês."

    elif any(p in pergunta for p in ['atrasad', 'venceu', 'devendo', 'vencida']):
        if contas_atrasadas:
            lista = "\n".join([f"  ⚠️ {c['descricao']}: R$ {c['valor']:,.2f} (Venceu dia {c['vencimento_dia']})" for c in contas_atrasadas])
            resposta = f"Você tem {len(contas_atrasadas)} conta(s) em atraso este mês:\n\n{lista}\n\nRecomendo quitar logo para evitar juros!"
        else:
            resposta = "🎉 Ótima notícia! Você não tem nenhuma conta atrasada no momento."

    elif any(p in pergunta for p in ['hoje', 'vence hoje']):
        if contas_hoje:
            lista = "\n".join([f"  🔔 {c['descricao']}: R$ {c['valor']:,.2f}" for c in contas_hoje])
            resposta = f"Atenção: Estas contas vencem hoje (Dia {hoje_dia}):\n\n{lista}"
        else:
            resposta = f"Nenhuma conta sua vence hoje (Dia {hoje_dia})."

    elif any(p in pergunta for p in ['onde gasto mais', 'maior gasto', 'categoria', 'mais gastando']):
        if maior_categoria:
            pct = (maior_categoria[1] / total_despesas * 100) if total_despesas > 0 else 0
            resposta = (f"🔍 A categoria onde você mais está gastando é **{maior_categoria[0]}**,\n"
                        f"somando **R$ {maior_categoria[1]:,.2f}** ({pct:.1f}% de todas as suas despesas do mês).")
        else:
            resposta = "Você ainda não possui despesas cadastradas para avaliar onde está gastando mais."

    elif any(p in pergunta for p in ['nota', 'anota', 'keep', 'bloco', 'lembrete']):
        if notas_app:
            titulos = "\n".join([f"  📝 {n['titulo'] or 'Sem título'}: {n['conteudo']}" for n in notas_app[:4]])
            resposta = f"Aqui estão suas anotações recentes no Keep:\n\n{titulos}"
        else:
            resposta = "Você ainda não tem anotações cadastradas na aba de Notas."

    elif any(p in pergunta for p in ['saúde', 'saude', 'diagnostico', 'situação']):
        if total_receitas == 0:
            resposta = "Cadastre suas receitas para eu avaliar sua saúde financeira com precisão."
        else:
            pct = (total_despesas / total_receitas) * 100
            if pct <= 60:
                resposta = f"Sua saúde financeira está **Excelente**! Você só comprometeu {pct:.0f}% da renda."
            elif pct <= 85:
                resposta = f"Sua saúde financeira está em **Atenção**: {pct:.0f}% da sua renda já está consumida."
            else:
                resposta = f"Alerta de saúde **Crítica**: Seus gastos atingiram {pct:.0f}% da renda. Corte despesas supérfluas."

    elif any(p in pergunta for p in ['resumo', 'relatorio', 'relatório', 'tudo', 'geral']):
        resposta = (f"📊 **Relatório Completo do Mês Atual:**\n\n"
                    f"• Entradas: R$ {total_receitas:,.2f}\n"
                    f"• Saídas: R$ {total_despesas:,.2f}\n"
                    f"• Saldo Livre: R$ {saldo:,.2f}\n"
                    f"• Fatura Cartão: R$ {total_cartao:,.2f}\n"
                    f"• Contas Pendentes: {len(contas_pendentes)}\n"
                    f"• Contas em Atraso: {len(contas_atrasadas)}\n"
                    f"• Total de Anotações salvas: {len(notas_app)}")
    else:
        resposta = (f"Entendi sua dúvida! Com base nos dados do seu app:\n"
                    f"Seu saldo atual é de R$ {saldo:,.2f}, com R$ {total_despesas:,.2f} em despesas cadastradas.\n\n"
                    f"Você pode me perguntar especificamente sobre:\n"
                    f"- 'Qual o meu saldo?'\n"
                    f"- 'Quanto gastei no cartão?'\n"
                    f"- 'Tenho contas atrasadas?'\n"
                    f"- 'Onde estou gastando mais?'\n"
                    f"- 'Resumo geral'")

    return jsonify({"resposta": resposta})

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
