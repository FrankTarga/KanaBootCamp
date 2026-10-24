# prompts-ia

Histórico das interações com IA durante o hackathon (requisito de submissão).

| arquivo | quem | conteúdo |
|---|---|---|
| `2026-10-24_dev1-backend_claude-code.md` | Dev 1 (Back-end) | conversa completa com o Claude Code: especificação, perguntas, decisões, revisões, conformidade com o gabarito, situação cadastral, Docker e entrega (reexportada ao fim do dia) |
| `2026-10-24_dev1-backend_plano-aprovado.md` | Dev 1 (Back-end) | plano de implementação aprovado antes de codar |
| `2026-10-24_dev2-frontend_prompt-e-resposta.txt` | Dev 2 (Front-end) | prompt com as 5 decisões de arquitetura e resposta completa da implementação |
| `2026-10-24_correcao-timeout-120s-carteira.txt` | Dev Front / IA | diagnóstico e correção cirúrgica do timeout de 120s na análise de 100k notas em modo carteira |
| `2026-10-24_campo-senha-gestor-sessionstorage.txt` | Dev Front / IA | implementação de campo de senha na gaveta de regras com persistência segura em sessionStorage e cabeçalho X-API-Key |
| `2026-10-24_correcao-contrato-front-back-4-falhas.txt` | Dev Front / IA | resolução cirúrgica das 4 falhas de contrato (X-API-Key, fallback indiscriminado, taxa padrão e .npmrc) |
| `2026-10-24_elaboracao-rfcs-arquitetura-e-testes.txt` | Arquiteto / IA | elaboração das especificações técnicas formais RFC-001 a RFC-006 e estratégia de testes do projeto |
| `2026-10-24_auditoria-rfcs-csv-injection-integridade.txt` | Auditoria / IA | auditoria estática de integridade, identificação de vulnerabilidade de CSV Formula Injection (CWE-1236) e crash por call stack |
| `2026-10-24_analise-testes-vulnerabilidades.txt` | Auditoria / IA | análise de testes da suíte completa, autenticação scrypt, concorrência e estabilidade |
| `2026-10-24_dev3-estatistica_01-revisao-prompt-e-raio-x-do-estoque.txt` | Dev 3 (Estatística) | revisão do prompt do estatístico (colunas, separador, taxa, raiz de CNPJ) e raio-x do estoque |
| `2026-10-24_dev3-estatistica_02-taxa-e-conferencia-com-o-gabarito.txt` | Dev 3 (Estatística) | precificação por desconto simples a 2% a.m. e conferência linha a linha com o gabarito de 100k |
| `2026-10-24_dev3-estatistica_03-analise-das-notas-recusadas.txt` | Dev 3 (Estatística) | análise descritiva das recusas e grupos que somam 100% (maiores restos, "mais de um problema") |
| `2026-10-24_dev3-estatistica_04-situacao-cadastral-e-banco-de-dados.txt` | Dev 3 (Estatística) | cnpj_situacao_mock.csv contra o gabarito e recomendação de SQLite para o histórico |
| `2026-10-24_dev3-estatistica_05-analise-de-perda-por-prazo.txt` | Dev 3 (Estatística) | fórmulas e números conferidos da Análise de perda (custo do prazo) |
| `2026-10-24_dev3-frontend_01-redesign-paleta-e-pasta-de-notas.txt` | Dev 3 (Front/Design) | paleta de cores da Kanastra, vídeo recolorido, envio por pasta e aviso de modo demonstração |
| `2026-10-24_dev3-frontend_02-menu-lateral-e-fundo-interativo.txt` | Dev 3 (Front/Design) | layout original com menu lateral, telas separadas e fundo interativo |
| `2026-10-24_dev3-frontend_03-tela-analise-de-perda.txt` | Dev 3 (Front/Design) | tela Análise de perda com valor digitado e gráfico em reais |
| `2026-10-24_dev3-frontend_04-historico-sqlite-no-front.txt` | Dev 3 (Front/Design) | tela Histórico, notas de envios antigos, busca de nota e chave do gestor |
| `2026-10-24_dev3-frontend_05-nomes-comuns-pagina-inicial-e-rolagem.txt` | Dev 3 (Front/Design) | nomes em português comum, página inicial e rolagem contida nos painéis |
| `2026-10-24_dev3-frontend_06-login-transicao-e-menu-fixo.txt` | Dev 3 (Front/Design) | integração do login, transição da página inicial, menu fixo e barras da liquidez |
| `2026-10-24_dev3-frontend_07-revisao-prompt-concorrencia.txt` | Dev 3 (revisão técnica) | avaliação do prompt de concorrência (WAL, IDs, threads) com medição de latência |

## Como adicionar o seu

1. Exporte a conversa da ferramenta que você usou (ChatGPT, Claude, Gemini, Copilot...).
2. Salve aqui como `AAAA-MM-DD_<papel>_<ferramenta>.md` ou `.txt`.
3. Antes de commitar, apague tokens, senhas, e-mails pessoais e qualquer dado sensível.
