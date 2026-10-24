# RFC-005: Pipeline de Upload, Fusão e Validação de CSVs

- **Status:** Proposta
- **Data de Criação:** 24/10/2026
- **Área:** Upload / Processamento de Arquivos / Pipeline de Dados

---

## 1. Contexto
A experiência central do **ANTECIPE PRO** inicia-se pela submissão de títulos a receber. Para evitar que empresas tenham que consolidar planilhas manualmente, o sistema oferece leitura recursiva de pastas inteiras via Drag & Drop, unificando múltiplos CSVs antes do envio para a API REST (`POST /batches/validate`).

Recentemente, identificou-se que o processamento do arquivo de estoque completo (100.554 linhas) no modo carteira demanda entre 7 e 16 segundos, exigindo que o timeout do cliente de upload seja dimensionado para até 120 segundos para evitar abortos prematuros.

---

## 2. Problema
1. **Limitação de memória do navegador ao ler pastas gigantescas:** A função `juntarCsvs` em [`frontend/src/utils/pastaNotas.ts`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/utils/pastaNotas.ts) carrega todo o conteúdo em strings na memória (`textos = await Promise.all(ordenados.map((f) => f.text()))`). Se o usuário arrasta uma pasta contendo dezenas de arquivos pesando centenas de megabytes, o consumo de RAM da aba pode provocar congelamento (*tab crash*).
2. **Validação prévia de formato e tamanho antes do tráfego de rede:** A validação de tamanho máximo de 50 MB e de arquivo vazio ocorre apenas quando o arquivo atinge o backend, gerando tráfego de rede inútil que poderia ser barrado em frações de milissegundo no frontend.
3. **Persistência de entrada para recálculo:** Quando o usuário altera parâmetros operacionais (Data-Base, Taxa, Otimizador) ou aplica uma regra na Gaveta do Gestor, o arquivo original mantido em `arquivoAtual` é reenviado. Se a referência ao arquivo for perdida ou se o navegador revogar o handle do arquivo, o recálculo falha sem aviso claro.

---

## 3. Evidências no Código
- [`frontend/src/utils/pastaNotas.ts:33-51`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/utils/pastaNotas.ts#L33-L51):
  ```typescript
  export async function juntarCsvs(arquivos: File[]): Promise<File> {
    if (arquivos.length === 0) throw new Error("Nenhum arquivo .csv encontrado...");
    if (arquivos.length === 1) return arquivos[0];
    const textos = await Promise.all(ordenados.map((f) => f.text())); // Leitura em RAM de todos os arquivos simultaneamente
  ```
- [`frontend/src/services/api.ts:246-250`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/services/api.ts#L246-L250): Configuração de timeout estendido para `120_000` ms para acomodar os 100k registros sem falsa desconexão.
- [`frontend/src/components/telas/TelaEnvio.tsx:121-125`](file:///c:/Users/Frank%20Targa/Desktop/Kanastra/KanaBootCamp/frontend/src/components/telas/TelaEnvio.tsx#L121-L125): Inputs de arquivo com `webkitdirectory` para leitura nativa de pastas.

---

## 4. Objetivos
- Otimizar o pipeline de unificação de arquivos com processamento por streaming ou validação em blocos.
- Implementar validação rápida no client-side: tamanho total < 50 MB, arquivo não-vazio, presença de colunas obrigatórias essenciais antes de disparar o POST.
- Prover feedback visual progressivo de upload (ex.: barra de progresso ou percentual quando suportado pelo `XMLHttpRequest` / fetch streaming).
- Garantir que recálculos what-if funcionem perfeitamente a partir do arquivo retido em memória.

---

## 5. Não Objetivos
- Implementar parsing completo de todas as 100 mil linhas no client-side; a regra e o contrato estipulam que o motor de análise e julgamento pertence exclusivamente ao RuleEngine FastAPI.

---

## 6. Proposta Técnica

### 6.1. Pré-Validação Client-Side Leve
```typescript
const LIMITE_UPLOAD_BYTES = 50 * 1024 * 1024; // 50 MB
const COLUNAS_OBRIGATORIAS = ["DOC_CEDENTE", "DOC_SACADO", "NU_DOCUMENTO", "VALOR_NOMINAL"];

export function validarArquivoPreliminar(arquivo: File): void {
  if (arquivo.size === 0) {
    throw new Error("O arquivo selecionado está vazio.");
  }
  if (arquivo.size > LIMITE_UPLOAD_BYTES) {
    throw new Error(`O arquivo tem ${(arquivo.size / (1024 * 1024)).toFixed(1)} MB e ultrapassa o limite de 50 MB.`);
  }
}
```

### 6.2. Leitura Rápida do Cabeçalho por Fatiamento (Blob.slice)
Em vez de ler arquivos de 50 MB inteiros na memória apenas para checar o cabeçalho:
```typescript
export async function validarCabecalhoCsv(arquivo: File): Promise<void> {
  // Lê apenas os primeiros 2 KB do arquivo
  const pedaco = arquivo.slice(0, 2048);
  const texto = await pedaco.text();
  const primeiraLinha = texto.split(/\r?\n/)[0] || "";
  
  const faltantes = COLUNAS_OBRIGATORIAS.filter((col) => !primeiraLinha.toUpperCase().includes(col));
  if (faltantes.length > 0) {
    throw new Error(`Arquivo inválido. Colunas obrigatórias não encontradas no cabeçalho: ${faltantes.join(", ")}`);
  }
}
```

---

## 7. Alternativas Consideradas
- **Utilizar biblioteca PapaParse:** PapaParse é robusto, mas focado em transformar CSV em objetos JS. Como nosso objetivo é enviar o arquivo binário direto no FormData para o FastAPI processar em C/Python, a biblioteca adicionaria peso desnecessário.
- **Upload particionado (Chunked/Resumable):** Desnecessário para arquivos de até 50 MB em rede corporativa ou local.

---

## 8. Impacto
- **Benefícios:** Feedback instantâneo para o usuário ao soltar arquivo incorreto sem esperar ida e volta ao servidor; eliminação de travamentos de memória no navegador.
- **Riscos:** Necessidade de garantir que a checagem client-side seja 100% fiel à validação do backend (`backend/app/main.py:343-350`), para não rejeitar arquivos válidos.

---

## 9. Plano de Adoção
1. Adicionar `validarArquivoPreliminar` em `frontend/src/utils/pastaNotas.ts`.
2. Integrar na ação de drop em `TelaEnvio.tsx`.
3. Manter o timeout de 120s para lotes grandes.

---

## 10. Critérios de Aceitação
- Soltar arquivo vazio exibe erro imediato em menos de 100 ms na UI.
- Soltar arquivo de 51 MB exibe erro claro de limite sem enviar bytes pela rede.
- Lote de 100k notas é transmitido, processado e renderizado com sucesso no modo carteira.

---

## 11. Testes Necessários
- Teste unitário de `juntarCsvs` com cabeçalhos compatíveis e incompatíveis.
- Teste de pré-validação com arquivos de diferentes tamanhos e formatos.

---

## 12. Dependências
- [RFC-002: Camada Padronizada de Comunicação com a API](RFC-002-api-client.md).

---

## 13. Questões em Aberto
- Nenhuma. Timeout de 120s e limites de 50MB estão perfeitamente alinhados com o backend.
