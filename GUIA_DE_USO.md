# Guia de uso do ANTECIPE PRO

Guia para a equipe subir o sistema, entender cada parte do site e testar. Siga na ordem.

---

## 1. Subir o sistema

**Precisa ter:** Git e Docker Desktop (aberto e com a baleia verde "Engine running").

### 1.1 Baixar a versão mais nova

```powershell
cd $HOME\Documents\KanaBootCamp
git pull
```

### 1.2 Criar o arquivo `.env` (só na primeira vez)

O `.env` guarda as senhas e **não vai para o GitHub**. Sem ele, o login com senha não funciona.

```powershell
Copy-Item .env.example .env
notepad .env
```

Troque os valores que começam com `troque-`:

| variável | para que serve |
|---|---|
| `ADMIN_API_KEY` | chave que o gestor digita em "Chave do gestor" para **salvar** regras |
| `BANCA_SENHA` | senha da conta `banca@antecipe.com.br` (perfil **Gestor do fundo**) |
| `CEDENTE_SENHA` | senha da conta `empresa@antecipe.com.br` (perfil **Empresa (cedente)**) |
| `SESSAO_SEGREDO` | qualquer texto longo; assina o login (sem ele, reiniciar o servidor desloga todo mundo) |

Combinem as senhas no grupo da equipe. Não coloquem senha em arquivo que vai para o Git.

### 1.3 Ligar

```powershell
docker compose up -d --build
docker compose ps
```

Espere `backend` e `mock-receita` aparecerem como **healthy** (cerca de 1 minuto na primeira vez). Depois abra:

- Site: **http://localhost:5173**
- Documentação da API: http://localhost:8000/docs

Para desligar: `docker compose down`. Depois de mudar o `.env`, rode `docker compose up -d --build` de novo.

---

## 2. Contas de acesso

| perfil na tela de login | e-mail | senha | o que vê |
|---|---|---|---|
| **Gestor do fundo** | `banca@antecipe.com.br` | a de `BANCA_SENHA` | tudo, inclusive **Regras do fundo** |
| **Empresa (cedente)** | `empresa@antecipe.com.br` | a de `CEDENTE_SENHA` | tudo, menos Regras do fundo |

Escolha o perfil antes de digitar a senha. Entrar com a conta da empresa no perfil de gestor (ou o contrário) é barrado de propósito.

---

## 3. Cada parte do site

### Página inicial
**Para que serve:** explica o que o sistema faz, com um exemplo de nota aprovada e recusada e os 3 passos.
**Como usar:** clique numa opção do menu de cima (Enviar notas, Resumo...) ou role a página para baixo. A tela desce sozinha para o login (ou para o painel, se já tiver entrado).

### Login
**Para que serve:** identificar quem está usando: empresa ou gestor.
**Como usar:** escolha o perfil, confira o e-mail (já vem preenchido), digite a senha e clique em "Entrar como...". O login dura 8 horas e continua valendo depois de apertar F5. Para sair, use o botão ao lado do seu nome, no pé do menu lateral. Ao sair, o lote que estava aberto é apagado da tela.

### Menu lateral
**Para que serve:** navegar entre as telas. Fica parado; só o conteúdo à direita rola.
- Mostra quanto cai na conta hoje (em "Resumo") e quantas notas foram recusadas (bolinha vermelha em "Notas").
- O quadro de baixo diz **"Análise ligada"** (números do servidor) ou **"Modo demonstração"** (números de exemplo).
- No celular, o menu abre pelo botão ☰ no topo.

### Enviar notas
**Para que serve:** mandar as notas para análise.
**Como usar:**
1. Escolha o tipo:
   - **Notas para antecipar:** um lote novo da empresa (o uso normal).
   - **Carteira do fundo:** analisa o estoque inteiro do fundo com as regras do gabarito (use o `backend/data/estoque_antecipe.csv`, 100 mil notas, cerca de 10 segundos).
2. Arraste uma **pasta** (pode ter subpastas) ou arquivos CSV para a caixa, ou use "Escolher pasta" ou "Escolher arquivos". Vários arquivos viram um lote só, desde que tenham o mesmo cabeçalho.
3. Opcional, antes de enviar: **data da operação**, **taxa** ao mês (se não mexer, vale a do fundo, 2%) e **Otimizar** (reorganiza o lote para caber mais notas quando o limite de um cliente aperta).

Ao terminar, o site vai sozinho para o Resumo. Um arquivo com colunas erradas mostra um aviso vermelho explicando o que falta.

### Resumo
**Para que serve:** responder "quanto eu recebo hoje".
**Como ler:** um extrato com valor enviado, menos o que ficou de fora, menos o custo da antecipação, igual ao que cai na conta. Mostra também quantas notas foram aprovadas, o ganho do otimizador e o alerta de fraude, se houver. Os botões levam direto às notas de cada caso.

### Estatística
**Para que serve:** entender por que as notas ficaram de fora e onde está o dinheiro.
- **Por que as notas foram recusadas:** cada nota recusada entra em um único grupo, então os percentuais somam 100%. Cada cartão diz quanto aquele problema libera se for corrigido. Clicar num cartão abre a lista de notas daquele problema. O cartão **"Mais de um problema"** abre por quantidade de problemas e por combinação.
- **Liquidez:** do valor enviado ao que cai na conta, em barras.
- **Valor por problema** e **Vencimentos** (quanto vence em cada faixa de prazo).

### Análise de perda
**Para que serve:** mostrar quanto custa esperar e por que notas curtas rendem mais.
**Como usar:** digite o **valor da nota** e escolha o **prazo** (no controle ou clicando no gráfico). Os quadros mostram quanto se **recebe hoje** e quanto se **perde**. Exemplo a 2% ao mês: R$ 50.000 em 60 dias recebe R$ 48.000 e perde R$ 2.000 (4%). Embaixo, "Mesmo valor, prazos diferentes" e o custo por faixa de prazo das notas aprovadas.

### Notas
**Para que serve:** ver nota por nota.
**Como usar:**
- Use as abas Todas, Aprovadas, Recusadas, Salvas pela reorganização e Suspeita de fraude, ou a busca por número, cliente, CNPJ ou tipo.
- Clique numa nota: a explicação abre logo abaixo, com o motivo e **"Como resolver"**.
- **Baixar aprovadas** e **Relatório de recusas** geram planilhas CSV que abrem no Excel.
- Com 100 mil notas, a tela desenha 300 por vez; use a busca para achar as outras.

### Histórico
**Para que serve:** tudo o que já foi analisado fica salvo no servidor, mesmo fechando o navegador.
- **Procurar uma nota:** digite o número (zeros à esquerda não importam) para ver em quais envios ela apareceu e o que aconteceu em cada um. Clique numa linha para abrir aquele envio.
- **Lotes validados:** cada envio com data, tipo, notas, aprovadas, recusadas e líquido. "Ver notas" abre as notas daquele envio, com os motivos. Etiquetas: **Repetido** (mesmo arquivo e mesmos parâmetros, resposta guardada), **Simulação** (teste do gestor) e **Aberto agora**.
- **Mudanças nas regras:** cada vez que o gestor salvou regras.
- Envios de **carteira** guardam só o resumo, não nota por nota.

### Regras do fundo (só gestor)
**Para que serve:** mudar o que o fundo aceita, sem reiniciar nada.
**Como usar:**
1. Ligue ou desligue regras e ajuste valores: taxa ao mês, valor mínimo, prazo máximo, limite por cliente, tipos e situações aceitos (botões de marcar).
2. **Testar sem salvar:** recalcula o lote aberto com as regras novas e mostra o efeito (dinheiro liberado e notas aprovadas), sem mudar o fundo.
3. **Salvar e recalcular:** digite a **Chave do gestor** (a `ADMIN_API_KEY` do `.env`) e salve. Passa a valer na hora para todos e aparece no Histórico.

Abre sozinha ao entrar como gestor. Esc ou o X fecham.

### Carregar lote demo
**Para que serve:** ver as telas com números de exemplo, sem enviar arquivo. Os números são de demonstração e o menu avisa "Modo demonstração".

---

## 4. Arquivos de teste (pasta `samples/`)

| arquivo | o que mostra |
|---|---|
| `01_lote_empresarial_padrao.csv` | lote típico: 22 notas, 13 aprovadas, **R$ 184.221,52** na conta, com vários tipos de recusa e uma nota com 3 problemas |
| `02_demo_otimizador_concentracao.csv` | cliente perto do limite: o otimizador troca uma nota longa por duas curtas, **+R$ 1.620.133,33** e 2 notas salvas |
| `03_demo_radar_antifraude.csv` | nota repetida, notas já compradas pelo fundo e **3 alertas de fraude** (já vendidas a outros fundos) |
| `backend/data/estoque_antecipe.csv` | carteira inteira (100.554 notas), para o modo **Carteira do fundo** |

Os valores acima são com taxa de 2% ao mês e a data padrão (22/10/2026).

---

## 5. Roteiro de teste (marque cada item)

- [ ] Página inicial abre; rolar para baixo leva ao login
- [ ] Senha errada mostra "E-mail ou senha incorretos"
- [ ] Entrar como **Empresa**: não aparece "Regras do fundo"
- [ ] Enviar `01`: Resumo com R$ 184,2 mil; Estatística com grupos que somam 100%
- [ ] Clicar num grupo da Estatística abre as notas daquele problema
- [ ] Abrir uma nota recusada mostra "Como resolver"
- [ ] Baixar aprovadas e Relatório de recusas abrem no Excel
- [ ] Análise de perda: R$ 50.000 em 60 dias recebe R$ 48.000
- [ ] Enviar uma pasta com dois CSVs: vira um lote só
- [ ] Enviar `03`: aba "Suspeita de fraude" com 3 notas
- [ ] Sair e entrar como **Gestor**: a gaveta abre; o lote anterior não aparece mais
- [ ] Enviar `02` e conferir o ganho do otimizador (+R$ 1,6 mi)
- [ ] Testar sem salvar (desligar uma regra) mostra o efeito; salvar com chave errada dá erro; com a certa, salva
- [ ] Carteira do fundo com o estoque: termina em cerca de 10 s e mostra "300 de 100.554"
- [ ] Histórico: procurar a nota 353104, abrir um envio antigo, ver a mudança de regras
- [ ] F5 mantém o login; "Sair" volta ao login
- [ ] Celular (ou janela estreita): menu ☰ funciona e nada vaza para os lados

Achou algo errado? Anote a tela, o que fez, o que esperava e um print.

---

## 6. Ver só o design, sem servidor

Para mexer na aparência sem Docker:

```powershell
cd $HOME\Documents\KanaBootCamp\frontend
npm install
$env:VITE_USE_MOCK="true"
npm run dev
```

Abra http://localhost:5173. O login aceita **qualquer senha** e as telas usam o lote de demonstração. Envio de arquivo real, Histórico e salvar regras precisam do servidor. Esse modo vale só para aquela janela do PowerShell e não afeta o site de verdade.

---

## 7. Problemas comuns

| sintoma | causa e solução |
|---|---|
| "Falha de conexão com a API" no login | o servidor não está rodando. Abra o Docker Desktop e rode `docker compose up -d --build`; confira com `docker compose ps` |
| "E-mail ou senha incorretos" com a senha certa | falta `BANCA_SENHA` ou `CEDENTE_SENHA` no `.env`, ou o perfil escolhido não é o da conta. Corrija o `.env` e rode `docker compose up -d --build` |
| site não abre em localhost:5173 | um `npm run dev` está usando a porta. Feche-o (Ctrl+C) e rode o compose de novo |
| "estes números não são do seu arquivo" | o servidor caiu no meio; ligue-o e envie de novo |
| salvar regras dá erro de chave | digite em "Chave do gestor" exatamente a `ADMIN_API_KEY` do `.env` |
| todo mundo deslogado depois de reiniciar | falta `SESSAO_SEGREDO` no `.env` |
| na VPS o site não fala com a API | `VITE_API_URL` no `.env` precisa ser `http://IP-DA-VPS:8000/api/v1`, e depois `docker compose up -d --build` |
| na VPS Linux o `backend` não fica healthy e o log diz `unable to open database file` | o container roda como usuário 1000 e não consegue gravar o banco em `backend/data`. Na VPS, rode `sudo chown -R 1000:1000 backend/data` e `docker compose up -d` |
| quero zerar o histórico | `docker compose down`, apague `backend/data/historico.db` e suba de novo |
