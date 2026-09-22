let financeChart = null;
const realCurrentMonth = new Date().getMonth() + 1;
let selectedMonth = realCurrentMonth;
const mesesNomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
let currentMonthItems = [];
let currentLembretes = [];
let saudeAtual = null;

window.addEventListener('DOMContentLoaded', () => {
    initChart();
    renderMonthButtons();
    loadCategorias();
    loadDashboard();
    setupForm();
    loadNotas();
});

window.switchTab = function(tabName) {
    document.getElementById('tab-inicio').classList.toggle('active', tabName === 'inicio');
    document.getElementById('tab-calendario').classList.toggle('active', tabName === 'calendario');
    document.getElementById('tab-contas').classList.toggle('active', tabName === 'contas');
    document.getElementById('tab-notas').classList.toggle('active', tabName === 'notas');

    document.getElementById('nav-btn-inicio').classList.toggle('active', tabName === 'inicio');
    document.getElementById('nav-btn-calendario').classList.toggle('active', tabName === 'calendario');
    document.getElementById('nav-btn-contas').classList.toggle('active', tabName === 'contas');
    document.getElementById('nav-btn-notas').classList.toggle('active', tabName === 'notas');

    const btnSaude = document.getElementById('btn-saude');
    const btnLembretes = document.getElementById('btn-lembretes');
    const btnChat = document.getElementById('btn-chat');

    if (tabName === 'inicio') {
        document.getElementById('page-title').innerText = 'Início';
        btnSaude.style.display = 'flex';
        btnLembretes.style.display = 'flex';
        btnChat.style.display = 'flex';
        loadDashboard();
    } else if (tabName === 'calendario') {
        document.getElementById('page-title').innerText = 'Faturas e Calendário';
        btnSaude.style.display = 'none';
        btnLembretes.style.display = 'none';
        btnChat.style.display = 'none';
        loadFaturas(selectedMonth);
    } else if (tabName === 'contas') {
        document.getElementById('page-title').innerText = 'Cadastrar Lançamento';
        btnSaude.style.display = 'none';
        btnLembretes.style.display = 'none';
        btnChat.style.display = 'none';
        document.getElementById('mes').value = selectedMonth;
    } else {
        document.getElementById('page-title').innerText = 'Bloco de Notas';
        btnSaude.style.display = 'none';
        btnLembretes.style.display = 'none';
        btnChat.style.display = 'none';
        loadNotas();
    }
};

// =================== CHAT INTELIGENTE ===================
window.openChatModal = function() {
    document.getElementById('modal-chat').classList.add('active');
    document.getElementById('chat-input').focus();
};

window.closeChatModal = function() {
    document.getElementById('modal-chat').classList.remove('active');
};

window.sendChatMessage = function(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;

    const chatBox = document.getElementById('chat-messages');

    // Adiciona a mensagem do usuário
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-msg user';
    userDiv.innerText = msg;
    chatBox.appendChild(userDiv);
    input.value = '';
    chatBox.scrollTop = chatBox.scrollHeight;

    // Loading temporário
    const botLoading = document.createElement('div');
    botLoading.className = 'chat-msg bot';
    botLoading.innerText = 'Pensando e analisando suas finanças...';
    chatBox.appendChild(botLoading);
    chatBox.scrollTop = chatBox.scrollHeight;

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensagem: msg })
    })
    .then(res => res.json())
    .then(data => {
        botLoading.innerText = data.resposta;
        chatBox.scrollTop = chatBox.scrollHeight;
    })
    .catch(() => {
        botLoading.innerText = 'Desculpe, ocorreu uma falha ao consultar os dados.';
    });
};

function initChart() {
    const ctx = document.getElementById('financeChart').getContext('2d');
    financeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Entradas', data: [], borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', tension: 0.3, fill: true },
                { label: 'Saídas', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.3, fill: true }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function loadDashboard() {
    fetch(`/api/resumo?mes=${selectedMonth}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('total-balance').innerText = 'R$ ' + data.saldo_total.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            document.getElementById('flow-receitas').innerText = 'R$ ' + data.total_receitas.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            document.getElementById('flow-despesas').innerText = 'R$ ' + data.total_despesas.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            document.getElementById('flow-cartao').innerText = 'R$ ' + data.total_cartao.toLocaleString('pt-BR', { minimumFractionDigits: 2 });

            currentLembretes = data.lembretes || [];
            const badgeLembretes = document.getElementById('lembretes-badge');
            if (currentLembretes.length > 0) {
                badgeLembretes.style.display = 'flex';
                badgeLembretes.innerText = currentLembretes.length;
            } else {
                badgeLembretes.style.display = 'none';
            }

            saudeAtual = data.saude;
            const badge = document.getElementById('health-indicator');
            badge.style.background = saudeAtual.status === 'otima' ? '#10b981' : (saudeAtual.status === 'alerta' ? '#f59e0b' : '#ef4444');

            const rankingBox = document.getElementById('ranking-gastos-list');
            if (data.ranking_gastos && data.ranking_gastos.length > 0) {
                rankingBox.innerHTML = '';
                data.ranking_gastos.forEach(item => {
                    const row = document.createElement('div');
                    row.className = 'ranking-row';
                    row.innerHTML = `<span class="ranking-name">${item.categoria}</span><span class="ranking-val">R$ ${item.total.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>`;
                    rankingBox.appendChild(row);
                });
            } else {
                rankingBox.innerHTML = '<p class="empty-state">Sem despesas registradas.</p>';
            }

            const chartCanvas = document.getElementById('financeChart');
            const emptyText = document.getElementById('empty-state-text');
            if (data.labels && data.labels.length > 0) {
                emptyText.style.display = 'none';
                chartCanvas.style.display = 'block';
                financeChart.data.labels = data.labels;
                financeChart.data.datasets[0].data = data.receitas;
                financeChart.data.datasets[1].data = data.despesas;
                financeChart.update();
            } else {
                chartCanvas.style.display = 'none';
                emptyText.style.display = 'block';
            }
        });
}

window.openLembretesModal = function() {
    const list = document.getElementById('modal-lembretes-list');
    if (!currentLembretes || currentLembretes.length === 0) {
        list.innerHTML = '<p class="empty-state">Tudo em dia! Sem contas pendentes ou atrasadas.</p>';
    } else {
        list.innerHTML = '';
        currentLembretes.forEach(l => {
            const row = document.createElement('div');
            row.className = `modal-lembrete-row ${l.tipo}`;
            row.innerHTML = `<span>${l.msg}</span><span>R$ ${l.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>`;
            list.appendChild(row);
        });
    }
    document.getElementById('modal-lembretes').classList.add('active');
};

window.closeLembretesModal = function() {
    document.getElementById('modal-lembretes').classList.remove('active');
};

function loadCategorias() {
    fetch('/api/categorias')
        .then(res => res.json())
        .then(cats => {
            const selects = [document.getElementById('categoria'), document.getElementById('edit-categoria')];
            selects.forEach(sel => {
                if (!sel) return;
                sel.innerHTML = '';
                cats.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c;
                    opt.innerText = c;
                    sel.appendChild(opt);
                });
            });
        });
}

window.promptNovaCategoria = function() {
    const nome = prompt('Digite o nome da nova categoria:');
    if (nome && nome.trim()) {
        fetch('/api/categorias', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nome: nome.trim() })
        }).then(() => {
            loadCategorias();
            alert('Categoria adicionada!');
        });
    }
};

function renderMonthButtons() {
    const bar = document.getElementById('months-bar');
    bar.innerHTML = '';
    mesesNomes.forEach((nome, i) => {
        const m = i + 1;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'month-btn';

        if (m === realCurrentMonth) btn.classList.add('is-current-month');
        if (m === selectedMonth) btn.classList.add('active');

        btn.innerText = m === realCurrentMonth ? `${nome} •` : nome;

        btn.onclick = () => {
            document.querySelectorAll('.month-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedMonth = m;
            document.getElementById('search-faturas').value = '';
            loadFaturas(m);
        };
        bar.appendChild(btn);
    });
}

function loadFaturas(mesNum) {
    document.getElementById('selected-month-title').innerText = `Faturas de ${mesesNomes[mesNum - 1]}`;
    fetch('/api/faturas_ano')
        .then(res => res.json())
        .then(faturas => {
            const f = faturas.find(item => item.mes === mesNum) || { total_despesas: 0, total_receitas: 0, total_cartao: 0, itens: [] };
            document.getElementById('fatura-total-despesa').innerText = 'Fatura: R$ ' + f.total_despesas.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            document.getElementById('fatura-total-receita').innerText = 'Receitas: R$ ' + f.total_receitas.toLocaleString('pt-BR', { minimumFractionDigits: 2 });
            document.getElementById('fatura-total-cartao').innerText = '💳 Cartão: R$ ' + f.total_cartao.toLocaleString('pt-BR', { minimumFractionDigits: 2 });

            currentMonthItems = f.itens || [];
            renderFaturasList(currentMonthItems);
        });
}

function renderFaturasList(itens) {
    const list = document.getElementById('fatura-items-list');
    if (!itens || itens.length === 0) {
        list.innerHTML = '<p class="empty-state">Nenhum lançamento encontrado.</p>';
        return;
    }

    list.innerHTML = '';
    itens.forEach(c => {
        const item = document.createElement('div');
        item.className = 'conta-item';
        const sinal = c.tipo === 'receita' ? '+ ' : '- ';
        const fixo = c.mensal ? ' • 🔁 Fixa' : '';
        const badgeCartao = c.eh_cartao ? '<span class="badge-cartao">💳 Cartão</span>' : '';
        const diaVenc = c.vencimento_dia ? `Venc: Dia ${c.vencimento_dia}` : '';

        item.innerHTML = `
            <div class="conta-item-left">
                <span class="conta-item-desc">${c.descricao} ${badgeCartao}</span>
                <span class="conta-item-meta">${diaVenc}${fixo} • ${c.categoria}</span>
            </div>
            <div class="conta-item-right">
                <button class="status-badge ${c.status}" onclick="toggleStatus(${c.id}, '${c.status}')" title="Clique para alternar">${c.status.toUpperCase()}</button>
                <span class="conta-item-val ${c.tipo}">${sinal}R$ ${c.valor.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span>
                <button class="btn-edit" onclick='openEditModal(${JSON.stringify(c)})' title="Editar valor/conta">✏️</button>
            </div>
        `;
        list.appendChild(item);
    });
}

window.toggleStatus = function(id, statusAtual) {
    const novoStatus = statusAtual === 'pago' ? 'pendente' : 'pago';
    fetch(`/api/contas/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: novoStatus })
    }).then(() => {
        loadFaturas(selectedMonth);
        loadDashboard();
    });
};

window.openEditModal = function(conta) {
    document.getElementById('edit-id').value = conta.id;
    document.getElementById('edit-descricao').value = conta.descricao;
    document.getElementById('edit-valor').value = conta.valor;
    document.getElementById('edit-tipo').value = conta.tipo;
    document.getElementById('edit-status').value = conta.status;
    document.getElementById('edit-vencimento').value = conta.vencimento_dia || 1;
    document.getElementById('edit-categoria').value = conta.categoria;
    document.getElementById('edit-cartao').checked = !!conta.eh_cartao;
    document.getElementById('edit-mensal').checked = !!conta.mensal;

    document.getElementById('modal-edicao').classList.add('active');
};

window.closeEditModal = function() {
    document.getElementById('modal-edicao').classList.remove('active');
};

window.saveEdit = function(e) {
    e.preventDefault();
    const id = document.getElementById('edit-id').value;
    const payload = {
        descricao: document.getElementById('edit-descricao').value,
        valor: parseFloat(document.getElementById('edit-valor').value),
        tipo: document.getElementById('edit-tipo').value,
        status: document.getElementById('edit-status').value,
        vencimento_dia: parseInt(document.getElementById('edit-vencimento').value),
        categoria: document.getElementById('edit-categoria').value,
        eh_cartao: document.getElementById('edit-cartao').checked,
        mensal: document.getElementById('edit-mensal').checked
    };

    fetch(`/api/contas/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(() => {
        closeEditModal();
        loadFaturas(selectedMonth);
        loadDashboard();
        alert('Alterações salvas com sucesso!');
    });
};

window.deleteConta = function() {
    const id = document.getElementById('edit-id').value;
    if (confirm('Tem certeza que deseja apagar este lançamento?')) {
        fetch(`/api/contas/${id}`, { method: 'DELETE' }).then(() => {
            closeEditModal();
            loadFaturas(selectedMonth);
            loadDashboard();
        });
    }
};

window.filterFaturas = function() {
    const query = document.getElementById('search-faturas').value.toLowerCase().trim();
    if (!query) {
        renderFaturasList(currentMonthItems);
        return;
    }
    const filtrados = currentMonthItems.filter(item => 
        item.descricao.toLowerCase().includes(query) || 
        item.categoria.toLowerCase().includes(query)
    );
    renderFaturasList(filtrados);
};

// =================== ABA NOTAS ===================
function loadNotas() {
    fetch('/api/notas')
        .then(res => res.json())
        .then(notas => {
            const grid = document.getElementById('keep-grid');
            if (!notas || notas.length === 0) {
                grid.innerHTML = '<p class="empty-state" style="grid-column: span 2;">Nenhuma anotação criada ainda.</p>';
                return;
            }
            grid.innerHTML = '';
            notas.forEach(n => {
                const card = document.createElement('div');
                card.className = 'keep-note-item';
                card.style.backgroundColor = n.cor;
                card.innerHTML = `
                    <div>
                        ${n.titulo ? `<div class="keep-note-title">${n.titulo}</div>` : ''}
                        <div class="keep-note-body">${n.conteudo}</div>
                    </div>
                    <div class="keep-note-footer">
                        <button class="btn-keep-delete" onclick="deleteNota(${n.id})" title="Excluir">🗑️</button>
                    </div>
                `;
                grid.appendChild(card);
            });
        });
}

window.saveNewNota = function(e) {
    e.preventDefault();
    const titulo = document.getElementById('nota-titulo').value;
    const conteudo = document.getElementById('nota-conteudo').value;
    const cor = document.querySelector('input[name="nota-cor"]:checked').value;

    fetch('/api/notas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titulo, conteudo, cor })
    }).then(res => {
        if (res.ok) {
            document.getElementById('keep-form').reset();
            loadNotas();
        }
    });
};

window.deleteNota = function(id) {
    fetch(`/api/notas/${id}`, { method: 'DELETE' }).then(() => loadNotas());
};

// =================== MODAL SAÚDE ===================
window.openHealthModal = function() {
    if (!saudeAtual) return;
    document.getElementById('modal-health-title').innerText = saudeAtual.titulo;
    document.getElementById('modal-health-msg').innerText = saudeAtual.mensagem;
    document.getElementById('modal-health-score').innerText = saudeAtual.score + '%';

    const circle = document.getElementById('modal-score-circle');
    circle.style.background = saudeAtual.status === 'otima' ? '#10b981' : (saudeAtual.status === 'alerta' ? '#f59e0b' : '#ef4444');

    document.getElementById('modal-saude').classList.add('active');
};

window.closeHealthModal = function() {
    document.getElementById('modal-saude').classList.remove('active');
};

function setupForm() {
    const form = document.getElementById('conta-form');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const payload = {
            descricao: document.getElementById('descricao').value,
            valor: parseFloat(document.getElementById('valor').value),
            tipo: document.getElementById('tipo').value,
            categoria: document.getElementById('categoria').value,
            status: document.getElementById('status').value,
            vencimento_dia: parseInt(document.getElementById('vencimento_dia').value),
            eh_cartao: document.getElementById('eh_cartao').checked,
            mes: parseInt(document.getElementById('mes').value),
            ano: new Date().getFullYear(),
            mensal: document.getElementById('mensal').checked
        };

        fetch('/api/contas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(async res => {
            if (res.ok) {
                form.reset();
                alert('Conta lançada com sucesso!');
                window.switchTab('inicio');
            } else {
                const err = await res.json();
                alert('Erro: ' + err.erro);
            }
        })
        .catch(() => alert('Falha ao conectar ao servidor.'));
    });
}
