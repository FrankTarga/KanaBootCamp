# Guia de uso do ANTECIPE PRO

Passo a passo para a equipe ligar o sistema, entrar e testar cada parte do site. Siga na ordem.

---

## Usuários e senhas

| perfil (escolha na tela de login) | e-mail | senha |
|---|---|---|
| **Gestor do fundo** | `banca@antecipe.com.br` | `Gestor-Kana-4821` |
| **Empresa (cedente)** | `empresa@antecipe.com.br` | `Empresa-Kana-7364` |

**Chave do gestor** (para salvar regras na gaveta "Regras do fundo"): `xk-antecipe-9f3b27d14e8c6a05`

Essas senhas só funcionam se o arquivo `.env` estiver como no Passo 2.

---

## PARTE 1: Ligar o sistema

### Passo 1: Baixar a versão final

Precisa ter o **Git** e o **Docker Desktop** instalados. Abra o Docker Desktop e espere aparecer "Engine running".

No PowerShell:

```powershell
cd $HOME\Documents\KanaBootCamp
git pull
```

Se ainda não tiver o projeto no computador:

```powershell
cd $HOME\Documents
git clone https://github.com/FrankTarga/KanaBootCamp.git
cd KanaBootCamp
```

### Passo 2: Criar o arquivo `.env`

```powershell
notepad .env
```

Se o Notepad perguntar se quer criar o arquivo, clique em **Sim**. Apague o que houver e cole exatamente isto:

```
# Copie para .env (o .env não vai para o Git) e troque os valores.
# Chave que o gestor digita na gaveta para salvar regras (header X-API-Key)
ADMIN_API_KEY=xk-antecipe-9f3b27d14e8c6a05

# Login do portal: usuários criados no startup; sem a senha, aquele usuário não é criado
BANCA_EMAIL=banca@antecipe.com.br
BANCA_SENHA=Gestor-Kana-4821
CEDENTE_EMAIL=empresa@antecipe.com.br
CEDENTE_SENHA=Empresa-Kana-7364

# Segredo que assina o token de sessão (string aleatória longa)
SESSAO_SEGREDO=b7e41c9a0f2d58e6a3c1974fd06b25e8c3a9f17d4e60b2a8

# URL da API vista pelo navegador (na VPS: http://IP-DA-VPS:8000/api/v1)
VITE_API_URL=http://localhost:8000/api/v1

# Fonte da situação cadastral do mock da Receita
SITUACAO_FONTE=gabarito
```

Salve (Ctrl+S) e feche.

### Passo 3: Ligar

Se houver algum `npm run dev` aberto, feche com Ctrl+C. Depois:

```powershell
docker compose up -d --build
docker compose ps
```

Espere `backend` e `mock-receita` aparecerem como **healthy**. Na primeira vez leva cerca de 1 minuto; repita o `docker compose ps` até aparecer.

### Passo 4: Abrir o site

Abra **http://localhost:5173** no navegador.

Para desligar no fim: `docker compose down`.

---

## PARTE 2: Testar, passo a passo

Os números abaixo valem com a taxa padrão de 2% ao mês e a data 22/10/2026. Os arquivos de teste ficam na pasta `samples` do projeto.

### Passo 5: Página inicial
1. Veja o texto explicando o sistema, o exemplo de nota aprovada e recusada e os 3 passos.
2. Role a página para baixo, ou clique numa opção do menu de cima. A tela desce até o login.

### Passo 6: Login como empresa
1. Clique em **Empresa (cedente)**. O e-mail `empresa@antecipe.com.br` já vem preenchido.
2. Digite uma senha errada e clique em **Entrar**. Deve aparecer "E-mail ou senha incorretos."
3. Digite `Empresa-Kana-7364` e entre.
4. Confira: o menu lateral mostra "Metalúrgica Silva LTDA" embaixo e **não** tem "Regras do fundo".

### Passo 7: Enviar notas
1. No menu lateral, clique em **Enviar notas**.
2. Deixe marcado **Notas para antecipar**.
3. Arraste o arquivo `samples\01_lote_empresarial_padrao.csv` para a caixa, ou clique em **Escolher arquivos**.
4. O site vai sozinho para o **Resumo**.

### Passo 8: Resumo
- Deve mostrar **R$ 184,2 mil** na conta hoje, com **13 notas aprovadas de 22**.
- O extrato é: valor enviado, menos o que ficou de fora, menos o custo da antecipação, igual ao que cai na conta.
- Clique em **Contratar por R$ 184.221,52** e depois em **Confirmar contratação**. Aparece o comprovante "Antecipação contratada · 13 notas compradas pelo fundo". A partir daí essas notas são do fundo: enviar o mesmo arquivo de novo mostra todas como "já comprada".

### Passo 9: Estatística
1. Clique em **Estatística**.
2. **Por que as notas foram recusadas:** cada nota recusada está em um único cartão, e os percentuais somam 100%.
3. Clique no cartão **Mais de um problema** para abrir as combinações.
4. Clique em qualquer outro cartão: abre a tela **Notas** só com as notas daquele problema.
5. Mais abaixo: **Liquidez** (barras do enviado ao recebido), **Valor por problema** e **Vencimentos**.

### Passo 10: Notas
1. Clique numa nota recusada: a explicação abre logo abaixo, com o motivo e **Como resolver**.
2. Use as abas (Todas, Aprovadas, Recusadas...) e a busca por número, cliente ou CNPJ.
3. Clique em **Baixar aprovadas** e em **Relatório de recusas**: as duas planilhas abrem no Excel.

### Passo 11: Análise de perda
1. Clique em **Análise de perda**.
2. Em **Valor da nota**, digite `50000` e deixe o prazo em 60 dias.
3. Deve mostrar: **Recebe hoje R$ 48.000,00** e **Perde R$ 2.000,00 (4%)**.
4. Mude o prazo no controle ou clicando no gráfico e veja os valores mudarem.

### Passo 12: Enviar uma pasta e o radar de fraude
1. Volte em **Enviar notas** e envie `samples\03_demo_radar_antifraude.csv`.
2. Em **Notas**, deve aparecer a aba **Suspeita de fraude (3)**: notas já vendidas a outros fundos.
3. Teste também **Escolher pasta** com uma pasta que tenha dois CSVs: eles viram um lote só.

### Passo 13: Sair e entrar como gestor
1. No pé do menu lateral, clique no botão de sair, ao lado do nome.
2. Clique em **Gestor do fundo**, digite `Gestor-Kana-4821` e entre.
3. Confira: o lote da empresa **não** aparece mais, e a gaveta **Regras do fundo** abre sozinha. Feche com Esc.

### Passo 14: Otimizador
1. Envie `samples\02_demo_otimizador_concentracao.csv`.
2. No **Resumo**, deve aparecer o ganho do otimizador: **+R$ 1,6 mi** e 2 notas salvas. O cliente estava perto do limite, e o sistema trocou uma nota longa por duas curtas.

### Passo 15: Regras do fundo (só o gestor)
1. No menu lateral, clique em **Regras do fundo**.
2. Desligue a regra **Limite por cliente** e clique em **Testar sem salvar**. Com o lote 02 aberto, passa de 6 para 7 notas aprovadas. Aparece o efeito no lote (dinheiro liberado e notas aprovadas), sem mudar o fundo.
3. Ligue a regra de novo.
4. Em **Chave do gestor**, digite algo errado e clique em **Salvar e recalcular**: deve dar erro.
5. Digite `xk-antecipe-9f3b27d14e8c6a05` e salve: aparece "Regras salvas e lote recalculado".

### Passo 16: Carteira do fundo (100 mil notas)
1. Em **Enviar notas**, marque **Carteira do fundo**.
2. Envie o arquivo `backend\data\estoque_antecipe.csv`.
3. Leva cerca de 10 segundos. Em **Notas**, aparece "Mostrando 300 de 100.554"; use a busca para achar as outras.
4. Volte para **Notas para antecipar** antes de enviar outro lote.

### Passo 17: Histórico
1. Clique em **Histórico**.
2. **Procurar uma nota:** digite `353104` e clique em **Procurar**. Aparece em quais envios a nota esteve; clique numa linha para abrir aquele envio.
3. **Lotes validados:** clique em **Ver notas** num envio para ver as notas dele, com os motivos. Envio de carteira guarda só o resumo.
4. **Mudanças nas regras:** aparece a versão salva no Passo 15.
5. O gestor vê os envios de todos. A empresa vê só os dela.

### Passo 18: Sessão e celular
1. Aperte F5: você continua logado.
2. Deixe a janela estreita (ou abra no celular pelo IP da máquina): o menu vira o botão ☰ no topo e nada vaza para os lados.

Achou algo errado? Anote o passo, o que fez, o que esperava e mande um print.

---

## O que é cada parte do site

| parte | para que serve |
|---|---|
| **Página inicial** | explica o sistema; rolar ou clicar no menu de cima leva ao login |
| **Login** | escolhe o perfil (empresa ou gestor); dura 8 horas e continua valendo depois do F5 |
| **Menu lateral** | navega entre as telas; mostra quanto cai na conta, quantas notas foram recusadas e se a análise está ligada |
| **Enviar notas** | manda um arquivo, vários arquivos ou uma pasta. "Notas para antecipar" é o uso normal; "Carteira do fundo" analisa o estoque inteiro. Também dá para mudar a data, a taxa e ligar ou desligar o Otimizar |
| **Resumo** | extrato de quanto cai na conta hoje, notas aprovadas, ganho do otimizador e alerta de fraude |
| **Contratar** (no Resumo) | a compra de verdade: o fundo compra as notas aprovadas e mostra o comprovante |
| **Estatística** | por que as notas foram recusadas (grupos que somam 100%, com quanto cada correção libera), liquidez, valor por problema e vencimentos |
| **Análise de perda** | quanto custa esperar: digite um valor e um prazo e veja quanto recebe e quanto perde |
| **Notas** | nota por nota, com busca, abas, explicação de cada recusa e as planilhas para baixar |
| **Histórico** | envios anteriores salvos no servidor, busca de nota por número e mudanças de regras |
| **Regras do fundo** | só o gestor: liga, desliga e ajusta as regras, testa o efeito e salva sem reiniciar nada |
| **Carregar lote demo** | mostra as telas com números de exemplo, sem enviar arquivo |

---

## Ver só o design, sem Docker

```powershell
cd $HOME\Documents\KanaBootCamp\frontend
npm install
$env:VITE_USE_MOCK="true"
npm run dev
```

Abra http://localhost:5173. O login aceita qualquer senha e as telas usam o lote de demonstração. Envio de arquivo real, Histórico e salvar regras precisam do Docker ligado.

---

## Problemas comuns

| o que aparece | o que fazer |
|---|---|
| "Falha de conexão com a API" no login | o Docker não está ligado. Abra o Docker Desktop e rode `docker compose up -d --build` |
| "E-mail ou senha incorretos" com a senha certa | o `.env` não está igual ao do Passo 2, ou o perfil escolhido não é o da conta. Corrija e rode `docker compose up -d --build` |
| o site não abre em localhost:5173 | um `npm run dev` está ocupando o endereço. Feche-o com Ctrl+C e rode o Passo 3 de novo |
| "estes números não são do seu arquivo" | o servidor caiu no meio. Rode `docker compose ps`, ligue de novo e reenvie |
| salvar regras dá erro de chave | digite `xk-antecipe-9f3b27d14e8c6a05` em "Chave do gestor" |
| `backend` não fica healthy | rode `docker compose logs backend --tail 30` e mande o print no grupo |
| na VPS Linux, o log diz `unable to open database file` | o container não tem permissão de gravar na pasta. Na VPS: `sudo chown -R 1000:1000 backend/data` e depois `docker compose up -d` |
| na VPS, o site não fala com a API | no `.env` da VPS, use `VITE_API_URL=http://IP-DA-VPS:8000/api/v1` e rode `docker compose up -d --build` |
| quero recomeçar do zero (envios e compras) | `docker compose down`, apague os arquivos `historico.db*` e `antecipe_acid.db*` em `backend\data` e rode o Passo 3 |
| reenviei um lote e tudo aparece como "já comprada" | é o esperado depois de **Contratar**; para repetir a demonstração, recomece do zero (linha acima) |
