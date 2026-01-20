"""
🛫 Dashboard de Promoções - Versão com Atualização Automática
=============================================================
- Atualiza automaticamente via cron externo (cron-job.org)
- Envia alertas no Telegram quando encontra novas promoções
- 100% gratuito

Deploy: Render.com
Cron: cron-job.org (gratuito)
"""

from flask import Flask, render_template_string, jsonify, request
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
import re
import sqlite3
import hashlib
import os
import threading
import time

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÃO - EDITE AQUI!
# ============================================================

# Telegram (opcional - deixe vazio se não quiser)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Chave secreta para o cron (evita que qualquer um chame a atualização)
CRON_SECRET = os.environ.get('CRON_SECRET', 'minha-chave-secreta-123')

# Banco de dados
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'promocoes.db')

# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': mensagem,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro Telegram: {e}")
        return False

def notificar_promocao(promo):
    """Formata e envia notificação de uma promoção"""
    emojis = {
        'passagem': '✈️',
        'milhas': '🎯',
        'transferencia_bonificada': '🔥'
    }
    
    emoji = emojis.get(promo.get('tipo'), '📢')
    tipo_label = {
        'passagem': 'PASSAGEM',
        'milhas': 'MILHAS',
        'transferencia_bonificada': 'BÔNUS'
    }.get(promo.get('tipo'), 'PROMO')
    
    msg = f"{emoji} <b>{tipo_label}</b>\n\n"
    msg += f"📌 {promo.get('titulo')}\n\n"
    
    if promo.get('preco'):
        msg += f"💰 <b>R$ {promo['preco']:,.0f}</b>\n"
    
    if promo.get('bonus_percentual'):
        msg += f"🎁 <b>{promo['bonus_percentual']}% de bônus</b>\n"
    
    if promo.get('programa'):
        msg += f"🏷️ {promo['programa']}\n"
    
    if promo.get('destino'):
        msg += f"📍 {promo['destino']}\n"
    
    msg += f"\n🔗 {promo.get('url')}"
    
    return enviar_telegram(msg)

def notificar_resumo(novas):
    """Envia resumo das novas promoções"""
    if not novas:
        return
    
    msg = f"📊 <b>{len(novas)} novas promoções encontradas!</b>\n\n"
    
    passagens = [p for p in novas if p.get('tipo') == 'passagem']
    milhas = [p for p in novas if p.get('tipo') == 'milhas']
    bonus = [p for p in novas if p.get('tipo') == 'transferencia_bonificada']
    
    if passagens:
        msg += f"✈️ {len(passagens)} passagens\n"
    if milhas:
        msg += f"🎯 {len(milhas)} milhas\n"
    if bonus:
        msg += f"🔥 {len(bonus)} bonificadas\n"
    
    # Destaque: melhor preço e maior bônus
    precos = [p['preco'] for p in passagens if p.get('preco')]
    if precos:
        menor = min(precos)
        msg += f"\n💰 Menor preço: <b>R$ {menor:,.0f}</b>"
    
    bonus_vals = [p['bonus_percentual'] for p in bonus if p.get('bonus_percentual')]
    if bonus_vals:
        maior = max(bonus_vals)
        msg += f"\n🎁 Maior bônus: <b>{maior}%</b>"
    
    enviar_telegram(msg)

# ============================================================
# MODELOS E BANCO
# ============================================================

@dataclass
class Promocao:
    tipo: str
    titulo: str
    url: str
    fonte: str
    data_encontrada: str = ""
    preco: Optional[float] = None
    bonus_percentual: Optional[int] = None
    programa: Optional[str] = None
    destino: Optional[str] = None
    
    def __post_init__(self):
        if not self.data_encontrada:
            self.data_encontrada = datetime.now().strftime("%d/%m %H:%M")
    
    @property
    def hash_id(self) -> str:
        return hashlib.md5(f"{self.titulo}{self.url}".encode()).hexdigest()[:12]

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS promocoes (
            hash_id TEXT PRIMARY KEY,
            tipo TEXT,
            titulo TEXT,
            url TEXT,
            fonte TEXT,
            data_encontrada TEXT,
            preco REAL,
            bonus_percentual INTEGER,
            programa TEXT,
            destino TEXT,
            notificado INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def salvar_promocao(promo: Promocao) -> bool:
    """Salva promoção. Retorna True se for nova."""
    conn = get_db()
    
    # Verifica se já existe
    existe = conn.execute(
        'SELECT 1 FROM promocoes WHERE hash_id = ?', 
        (promo.hash_id,)
    ).fetchone()
    
    if existe:
        conn.close()
        return False
    
    # Nova promoção
    conn.execute('''
        INSERT INTO promocoes VALUES (?,?,?,?,?,?,?,?,?,?,0)
    ''', (promo.hash_id, promo.tipo, promo.titulo, promo.url, promo.fonte,
          promo.data_encontrada, promo.preco, promo.bonus_percentual, 
          promo.programa, promo.destino))
    conn.commit()
    conn.close()
    return True

def get_promocoes(tipo=None, limite=100):
    conn = get_db()
    if tipo and tipo != 'todas':
        rows = conn.execute(
            'SELECT * FROM promocoes WHERE tipo=? ORDER BY rowid DESC LIMIT ?',
            (tipo, limite)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM promocoes ORDER BY rowid DESC LIMIT ?',
            (limite,)
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_stats():
    conn = get_db()
    stats = {
        'passagens': conn.execute("SELECT COUNT(*) FROM promocoes WHERE tipo='passagem'").fetchone()[0],
        'milhas': conn.execute("SELECT COUNT(*) FROM promocoes WHERE tipo='milhas'").fetchone()[0],
        'bonificadas': conn.execute("SELECT COUNT(*) FROM promocoes WHERE tipo='transferencia_bonificada'").fetchone()[0],
        'menor_preco': conn.execute("SELECT MIN(preco) FROM promocoes WHERE preco > 0").fetchone()[0],
        'maior_bonus': conn.execute("SELECT MAX(bonus_percentual) FROM promocoes").fetchone()[0],
    }
    stats['total'] = stats['passagens'] + stats['milhas'] + stats['bonificadas']
    conn.close()
    return stats

def get_ultima_atualizacao():
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key='ultima_atualizacao'").fetchone()
    conn.close()
    return row[0] if row else None

def set_ultima_atualizacao():
    conn = get_db()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn.execute("INSERT OR REPLACE INTO config VALUES ('ultima_atualizacao', ?)", (now,))
    conn.commit()
    conn.close()
    return now

# ============================================================
# SCRAPERS
# ============================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'pt-BR,pt;q=0.9',
}

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        return BeautifulSoup(r.text, 'html.parser') if r.ok else None
    except:
        return None

def extrair_preco(texto):
    m = re.search(r'R\$\s*([\d.,]+)', texto)
    if m:
        try:
            return float(m.group(1).replace('.','').replace(',','.'))
        except:
            pass
    return None

def extrair_bonus(texto):
    m = re.search(r'(\d+)\s*%', texto)
    return int(m.group(1)) if m else None

def extrair_destino(texto):
    destinos = ['miami', 'orlando', 'nova york', 'new york', 'paris', 'londres', 
                'roma', 'lisboa', 'porto', 'madrid', 'barcelona', 'cancun',
                'buenos aires', 'santiago', 'dubai', 'tokyo', 'los angeles',
                'nova iorque', 'milao', 'amsterdam', 'berlim']
    texto_lower = texto.lower()
    for d in destinos:
        if d in texto_lower:
            return d.title()
    return None

def identificar_programa(texto):
    programas = {'smiles': 'Smiles', 'latam': 'LATAM Pass', 'azul': 'TudoAzul',
                 'livelo': 'Livelo', 'esfera': 'Esfera'}
    for k, v in programas.items():
        if k in texto.lower():
            return v
    return None

def buscar_melhores_destinos():
    promocoes = []
    urls = [
        ("https://www.melhoresdestinos.com.br/promocoes-de-passagens-aereas", "passagem"),
        ("https://www.melhoresdestinos.com.br/categoria/milhas-aereas", "milhas"),
    ]
    
    for url, tipo_default in urls:
        soup = fetch(url)
        if not soup:
            continue
        
        for article in soup.select('article, .post-item')[:25]:
            try:
                link_elem = article.select_one('h2 a, h3 a, a.post-title')
                if not link_elem:
                    continue
                
                titulo = link_elem.get_text(strip=True)
                href = link_elem.get('href', '')
                if not href.startswith('http'):
                    href = "https://www.melhoresdestinos.com.br" + href
                
                is_bonus = any(x in titulo.lower() for x in ['bônus', 'bonus', 'bonificad'])
                tipo = 'transferencia_bonificada' if is_bonus else tipo_default
                
                promo = Promocao(
                    tipo=tipo,
                    titulo=titulo[:150],
                    url=href,
                    fonte='Melhores Destinos',
                    preco=extrair_preco(titulo),
                    bonus_percentual=extrair_bonus(titulo) if is_bonus else None,
                    programa=identificar_programa(titulo),
                    destino=extrair_destino(titulo)
                )
                promocoes.append(promo)
            except:
                continue
    
    return promocoes

def buscar_passagens_imperdiveis():
    promocoes = []
    soup = fetch("https://www.passagensimperdiveis.com.br")
    if not soup:
        return promocoes
    
    for article in soup.select('article, .post')[:20]:
        try:
            link_elem = article.select_one('h2 a, h3 a, a.title')
            if not link_elem:
                continue
            
            titulo = link_elem.get_text(strip=True)
            href = link_elem.get('href', '')
            if not href.startswith('http'):
                href = "https://www.passagensimperdiveis.com.br" + href
            
            promo = Promocao(
                tipo='passagem',
                titulo=titulo[:150],
                url=href,
                fonte='Passagens Imperdíveis',
                preco=extrair_preco(titulo),
                destino=extrair_destino(titulo)
            )
            promocoes.append(promo)
        except:
            continue
    
    return promocoes

def buscar_todas(notificar=True):
    """Busca todas as promoções e notifica as novas"""
    todas = []
    novas = []
    
    todas.extend(buscar_melhores_destinos())
    todas.extend(buscar_passagens_imperdiveis())
    
    for p in todas:
        is_nova = salvar_promocao(p)
        if is_nova:
            novas.append(p.__dict__ if hasattr(p, '__dict__') else asdict(p))
    
    set_ultima_atualizacao()
    
    # Notifica no Telegram se houver novas
    if notificar and novas and TELEGRAM_BOT_TOKEN:
        # Envia resumo
        notificar_resumo(novas)
        
        # Envia detalhes das melhores (top 3)
        # Prioriza: bonificadas com alto %, passagens baratas
        bonus_altos = sorted(
            [p for p in novas if p.get('bonus_percentual')],
            key=lambda x: x.get('bonus_percentual', 0),
            reverse=True
        )[:2]
        
        passagens_baratas = sorted(
            [p for p in novas if p.get('preco')],
            key=lambda x: x.get('preco', 999999)
        )[:2]
        
        destaques = bonus_altos + passagens_baratas
        for p in destaques[:3]:
            notificar_promocao(p)
            time.sleep(1)  # Evita flood
    
    return len(todas), len(novas)

# ============================================================
# HTML TEMPLATE
# ============================================================

HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛫 Promoções de Viagem</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        body { 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh; 
            color: #fff;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        .container { max-width: 1200px; padding: 20px; }
        
        .header {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 { 
            font-size: 1.8rem; 
            font-weight: 700;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .auto-badge {
            background: linear-gradient(90deg, #00ff88, #00d4ff);
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); 
            gap: 15px; 
            margin-bottom: 25px; 
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card .icon { font-size: 2rem; margin-bottom: 8px; }
        .stat-card .number { font-size: 1.8rem; font-weight: 700; }
        .stat-card .label { font-size: 0.8rem; opacity: 0.7; }
        
        .filters {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }
        .filter-btn {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9rem;
        }
        .filter-btn:hover, .filter-btn.active {
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            border-color: transparent;
        }
        
        .promo-card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid;
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s;
        }
        .promo-card:hover {
            background: rgba(255,255,255,0.08);
            transform: translateX(5px);
        }
        .promo-card.passagem { border-left-color: #00d4ff; }
        .promo-card.milhas { border-left-color: #00ff88; }
        .promo-card.transferencia_bonificada { border-left-color: #ff6b6b; }
        
        .promo-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-passagem { background: rgba(0,212,255,0.2); color: #00d4ff; }
        .badge-milhas { background: rgba(0,255,136,0.2); color: #00ff88; }
        .badge-bonificada { background: rgba(255,107,107,0.2); color: #ff6b6b; }
        
        .promo-title {
            color: #fff;
            text-decoration: none;
            font-weight: 600;
            font-size: 1rem;
            display: block;
            margin: 12px 0;
            line-height: 1.4;
        }
        .promo-title:hover { color: #00d4ff; }
        
        .promo-meta {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            font-size: 0.8rem;
            opacity: 0.7;
        }
        
        .price-tag {
            background: linear-gradient(90deg, #00ff88, #00d4ff);
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
        }
        .bonus-tag {
            background: linear-gradient(90deg, #ff6b6b, #ffa500);
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
        }
        
        .btn-atualizar {
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            border: none;
            color: #fff;
            padding: 12px 25px;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.3s;
        }
        .btn-atualizar:hover { transform: scale(1.05); color: #fff; }
        .btn-atualizar:disabled { opacity: 0.5; cursor: wait; }
        
        .telegram-box {
            background: rgba(0,136,204,0.1);
            border: 1px solid rgba(0,136,204,0.3);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            opacity: 0.5;
        }
        
        .destino-tag {
            background: rgba(255,255,255,0.1);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }
        
        @media (max-width: 768px) {
            .header h1 { font-size: 1.4rem; }
            .stat-card .number { font-size: 1.4rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-3">
                <div>
                    <h1>🛫 Promoções de Viagem</h1>
                    <div style="display:flex; gap:10px; align-items:center; margin-top:8px; flex-wrap:wrap;">
                        <small style="opacity:0.6">
                            <i class="bi bi-clock"></i> Atualizado: <span id="lastUpdate">{{ ultima }}</span>
                        </small>
                        <span class="auto-badge">🔄 Atualização automática</span>
                    </div>
                </div>
                <button class="btn-atualizar" onclick="atualizar()" id="btnAtualizar">
                    <i class="bi bi-arrow-clockwise"></i> Atualizar
                </button>
            </div>
        </div>
        
        {% if telegram_ativo %}
        <div class="telegram-box">
            <span style="font-size:1.5rem">📱</span>
            <div>
                <strong>Telegram ativo!</strong><br>
                <small style="opacity:0.7">Você receberá alertas de novas promoções automaticamente.</small>
            </div>
        </div>
        {% endif %}
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="icon">✈️</div>
                <div class="number" id="sPassagens">{{ stats.passagens }}</div>
                <div class="label">Passagens</div>
            </div>
            <div class="stat-card">
                <div class="icon">🎯</div>
                <div class="number" id="sMilhas">{{ stats.milhas }}</div>
                <div class="label">Milhas</div>
            </div>
            <div class="stat-card">
                <div class="icon">🔥</div>
                <div class="number" id="sBonificadas">{{ stats.bonificadas }}</div>
                <div class="label">Bonificadas</div>
            </div>
            <div class="stat-card">
                <div class="icon">💰</div>
                <div class="number" id="sBonus">{{ stats.maior_bonus or 0 }}%</div>
                <div class="label">Maior Bônus</div>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="filters">
            <button class="filter-btn active" onclick="filtrar('todas', this)">🌐 Todas</button>
            <button class="filter-btn" onclick="filtrar('passagem', this)">✈️ Passagens</button>
            <button class="filter-btn" onclick="filtrar('milhas', this)">🎯 Milhas</button>
            <button class="filter-btn" onclick="filtrar('transferencia_bonificada', this)">🔥 Bonificadas</button>
        </div>
        
        <!-- Lista -->
        <div id="lista">
            {% if promos %}
                {% for p in promos %}
                <div class="promo-card {{ p.tipo }}">
                    <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                        <span class="promo-badge badge-{{ 'bonificada' if p.tipo == 'transferencia_bonificada' else p.tipo }}">
                            {{ '✈️ Passagem' if p.tipo == 'passagem' else ('🎯 Milhas' if p.tipo == 'milhas' else '🔥 Bonificada') }}
                        </span>
                        <div>
                            {% if p.preco %}<span class="price-tag">R$ {{ "%.0f"|format(p.preco) }}</span>{% endif %}
                            {% if p.bonus_percentual %}<span class="bonus-tag">{{ p.bonus_percentual }}%</span>{% endif %}
                        </div>
                    </div>
                    <a href="{{ p.url }}" target="_blank" class="promo-title">{{ p.titulo }}</a>
                    <div class="promo-meta">
                        <span><i class="bi bi-newspaper"></i> {{ p.fonte }}</span>
                        <span><i class="bi bi-clock"></i> {{ p.data_encontrada }}</span>
                        {% if p.destino %}<span class="destino-tag">📍 {{ p.destino }}</span>{% endif %}
                        {% if p.programa %}<span><i class="bi bi-tag"></i> {{ p.programa }}</span>{% endif %}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h4>Clique em "Atualizar" para buscar promoções</h4>
                </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        async function atualizar() {
            const btn = document.getElementById('btnAtualizar');
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Buscando...';
            
            try {
                await fetch('/api/atualizar', {method: 'POST'});
                location.reload();
            } catch(e) {
                alert('Erro ao atualizar');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Atualizar';
            }
        }
        
        async function filtrar(tipo, el) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            el.classList.add('active');
            
            const res = await fetch('/api/promocoes?tipo=' + tipo);
            const data = await res.json();
            renderizar(data.promocoes);
        }
        
        function renderizar(promos) {
            const lista = document.getElementById('lista');
            if (!promos.length) {
                lista.innerHTML = '<div class="empty-state"><h4>Nenhuma promoção encontrada</h4></div>';
                return;
            }
            
            lista.innerHTML = promos.map(p => {
                const badge = p.tipo === 'passagem' ? '✈️ Passagem' : (p.tipo === 'milhas' ? '🎯 Milhas' : '🔥 Bonificada');
                const badgeClass = p.tipo === 'transferencia_bonificada' ? 'bonificada' : p.tipo;
                return `
                    <div class="promo-card ${p.tipo}">
                        <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                            <span class="promo-badge badge-${badgeClass}">${badge}</span>
                            <div>
                                ${p.preco ? `<span class="price-tag">R$ ${Math.round(p.preco)}</span>` : ''}
                                ${p.bonus_percentual ? `<span class="bonus-tag">${p.bonus_percentual}%</span>` : ''}
                            </div>
                        </div>
                        <a href="${p.url}" target="_blank" class="promo-title">${p.titulo}</a>
                        <div class="promo-meta">
                            <span><i class="bi bi-newspaper"></i> ${p.fonte}</span>
                            <span><i class="bi bi-clock"></i> ${p.data_encontrada}</span>
                            ${p.destino ? `<span class="destino-tag">📍 ${p.destino}</span>` : ''}
                            ${p.programa ? `<span><i class="bi bi-tag"></i> ${p.programa}</span>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        }
    </script>
</body>
</html>
'''

# ============================================================
# ROTAS
# ============================================================

@app.route('/')
def index():
    return render_template_string(HTML,
        stats=get_stats(),
        promos=get_promocoes(limite=50),
        ultima=get_ultima_atualizacao() or 'Nunca',
        telegram_ativo=bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    )

@app.route('/api/promocoes')
def api_promocoes():
    tipo = request.args.get('tipo', 'todas')
    return jsonify({'promocoes': get_promocoes(tipo=tipo, limite=50)})

@app.route('/api/atualizar', methods=['POST'])
def api_atualizar():
    total, novas = buscar_todas(notificar=True)
    return jsonify({'success': True, 'total': total, 'novas': novas})

@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())

# Endpoint para o CRON externo chamar
@app.route('/cron/atualizar')
def cron_atualizar():
    """Endpoint para ser chamado pelo cron-job.org"""
    secret = request.args.get('secret', '')
    
    if secret != CRON_SECRET:
        return jsonify({'error': 'Unauthorized'}), 401
    
    total, novas = buscar_todas(notificar=True)
    return jsonify({
        'success': True,
        'total': total,
        'novas': novas,
        'timestamp': datetime.now().isoformat()
    })

# Health check para manter o serviço ativo
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
