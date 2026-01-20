# 🛫 Guia Completo: Dashboard com Atualização Automática

## O que você vai ter:
- ✅ Site online 24/7 (gratuito)
- ✅ Atualização automática a cada 30 minutos
- ✅ Alertas no Telegram quando aparecer uma promoção nova
- ✅ Tudo 100% gratuito

---

## PARTE 1: Criar Bot do Telegram (5 minutos)

### 1.1 Criar o Bot
1. Abra o **Telegram** no celular ou computador
2. Busque por **@BotFather**
3. Envie: `/newbot`
4. Nome do bot: `Promoções Viagem`
5. Username: `ukpromos_bot` (precisa ser único, adicione números se necessário)
6. **Guarde o TOKEN** que apareceu (algo como `7123456789:AAHxxxxxx...`)

### 1.2 Pegar seu Chat ID
1. Busque por **@userinfobot** no Telegram
2. Envie: `/start`
3. **Guarde o número do ID** (algo como `123456789`)

### 1.3 Ativar o bot
1. Busque pelo seu bot (o username que você criou)
2. Clique em **Iniciar** ou envie `/start`

---

## PARTE 2: Colocar o Site Online (10 minutos)

### 2.1 Criar conta no GitHub
1. Acesse: **github.com**
2. Clique em **Sign up**
3. Crie uma conta gratuita
4. Confirme seu email

### 2.2 Criar repositório
1. Clique no botão verde **"New"** (canto superior esquerdo)
2. Repository name: `promo-viagem`
3. Marque **Public**
4. Clique em **Create repository**

### 2.3 Subir os arquivos
1. Na tela do repositório, clique em **"uploading an existing file"**
2. Arraste os 3 arquivos da pasta:
   - `app.py`
   - `requirements.txt`
   - `Procfile`
3. Clique em **Commit changes**

### 2.4 Criar conta no Render
1. Acesse: **render.com**
2. Clique em **Get Started for Free**
3. Escolha **Sign up with GitHub**
4. Autorize o acesso

### 2.5 Deploy
1. Clique em **New +** → **Web Service**
2. Selecione o repositório `promo-viagem`
3. Configure:
   - **Name**: `promo-viagem`
   - **Region**: Oregon (US West)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### 2.6 Configurar variáveis de ambiente (IMPORTANTE!)
1. Role para baixo até **Environment Variables**
2. Adicione:

| Key | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | Seu token do bot (ex: `7123456789:AAHxxx...`) |
| `TELEGRAM_CHAT_ID` | Seu chat ID (ex: `123456789`) |
| `CRON_SECRET` | Uma senha qualquer (ex: `minha-senha-secreta-2024`) |

3. Em **Instance Type**, escolha **Free**
4. Clique em **Create Web Service**

### 2.7 Aguardar deploy
- Aguarde 2-3 minutos
- Quando aparecer **"Live"**, seu site está no ar!
- Anote a URL (algo como: `https://promo-viagem.onrender.com`)

---

## PARTE 3: Configurar Atualização Automática (5 minutos)

Vamos usar o **cron-job.org** (gratuito) para chamar seu site a cada 30 minutos.

### 3.1 Criar conta
1. Acesse: **cron-job.org**
2. Clique em **Sign Up**
3. Crie uma conta gratuita

### 3.2 Criar o cron job
1. Clique em **CREATE CRONJOB**
2. Configure:

| Campo | Valor |
|-------|-------|
| **Title** | Atualizar Promoções |
| **URL** | `https://SEU-SITE.onrender.com/cron/atualizar?secret=SUA-SENHA` |
| **Schedule** | Every 30 minutes |

⚠️ **Substitua**:
- `SEU-SITE` pela URL do seu Render
- `SUA-SENHA` pelo valor do `CRON_SECRET` que você configurou

3. Clique em **CREATE**

### 3.3 Testar
1. Na lista de cron jobs, clique no que você criou
2. Clique em **Test Run**
3. Deve aparecer `{"success": true, ...}`

---

## PARTE 4: Manter o Site Sempre Ativo (Opcional)

No plano gratuito do Render, o site "dorme" após 15 min sem acesso. O cron já resolve isso, mas para garantir:

### Opção A: Usar o UptimeRobot
1. Acesse: **uptimerobot.com**
2. Crie conta gratuita
3. Clique em **Add New Monitor**
4. Configure:
   - **Monitor Type**: HTTP(s)
   - **URL**: sua URL do Render + `/health`
   - **Monitoring Interval**: 5 minutes
5. Clique em **Create Monitor**

---

## ✅ Pronto! Como funciona agora:

1. **A cada 30 minutos** o cron-job.org chama seu site
2. O site **busca novas promoções** automaticamente
3. Se encontrar promoções **NOVAS**, envia no Telegram
4. Você pode acessar o site a qualquer momento para ver todas

---

## 📱 Adicionar atalho no celular

### iPhone
1. Abra o Safari
2. Acesse seu site
3. Toque em Compartilhar → "Adicionar à Tela de Início"

### Android
1. Abra o Chrome
2. Acesse seu site
3. Menu (⋮) → "Adicionar à tela inicial"

---

## 🔧 Comandos úteis

### Forçar atualização
Acesse no navegador:
```
https://SEU-SITE.onrender.com/cron/atualizar?secret=SUA-SENHA
```

### Ver estatísticas
```
https://SEU-SITE.onrender.com/api/stats
```

---

## ❓ Problemas comuns

### "Não recebo mensagens no Telegram"
1. Verifique se enviou `/start` para o bot
2. Confira o TOKEN e CHAT_ID nas variáveis do Render
3. Verifique se as variáveis estão sem espaços extras

### "Site demora para carregar"
Normal! O plano gratuito "dorme" e leva ~30s para acordar.

### "Cron não funciona"
1. Verifique se a URL está correta
2. Confirme que o `secret` na URL é igual ao `CRON_SECRET` no Render

### "Build failed no Render"
Verifique se subiu todos os arquivos: `app.py`, `requirements.txt`, `Procfile`

---

## 📊 Resumo dos serviços usados

| Serviço | Função | Custo |
|---------|--------|-------|
| **Render** | Hospeda o site | Grátis |
| **GitHub** | Armazena o código | Grátis |
| **Telegram** | Envia alertas | Grátis |
| **Cron-job.org** | Agenda atualizações | Grátis |
| **UptimeRobot** | Mantém site ativo | Grátis (opcional) |

---

Pronto! Agora você tem um sistema completo rodando 24/7 sem custo! 🎉
