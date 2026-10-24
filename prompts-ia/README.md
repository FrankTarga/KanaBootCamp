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

## Como adicionar o seu

1. Exporte a conversa da ferramenta que você usou (ChatGPT, Claude, Gemini, Copilot...).
2. Salve aqui como `AAAA-MM-DD_<papel>_<ferramenta>.md` ou `.txt`.
3. Antes de commitar, apague tokens, senhas, e-mails pessoais e qualquer dado sensível.
