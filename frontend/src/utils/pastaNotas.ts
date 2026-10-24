// Recebe o que a pessoa arrastou (uma pasta, vários CSVs ou um só) e devolve UM arquivo de lote,
// porque POST /batches/validate recebe um arquivo por vez.

const ehCsv = (nome: string) => nome.toLowerCase().endsWith(".csv");

function lerEntrada(entrada: FileSystemEntry): Promise<File[]> {
  if (entrada.isFile) {
    return new Promise((ok, falha) => (entrada as FileSystemFileEntry).file((f) => ok([f]), falha));
  }
  const leitor = (entrada as FileSystemDirectoryEntry).createReader();
  // readEntries devolve no máximo ~100 itens por chamada: lê até vir vazio
  const lerTudo = (acumulado: FileSystemEntry[]): Promise<FileSystemEntry[]> =>
    new Promise((ok, falha) =>
      leitor.readEntries((lote) => (lote.length ? lerTudo([...acumulado, ...lote]).then(ok, falha) : ok(acumulado)), falha),
    );
  return lerTudo([]).then((filhos) => Promise.all(filhos.map(lerEntrada)).then((l) => l.flat()));
}

/** Arquivos CSV de um drop, entrando em pastas e subpastas. */
export async function csvsDoDrop(dados: DataTransfer): Promise<File[]> {
  const entradas = Array.from(dados.items)
    .map((item) => (item.kind === "file" ? item.webkitGetAsEntry() : null))
    .filter((e): e is FileSystemEntry => e !== null);
  const arquivos = entradas.length ? (await Promise.all(entradas.map(lerEntrada))).flat() : Array.from(dados.files);
  return arquivos.filter((f) => ehCsv(f.name));
}

export function csvsDaLista(lista: FileList | null): File[] {
  return Array.from(lista ?? []).filter((f) => ehCsv(f.name));
}

/** Junta vários CSVs do mesmo formato num só, mantendo o cabeçalho uma vez. */
export async function juntarCsvs(arquivos: File[]): Promise<File> {
  if (arquivos.length === 0) throw new Error("Nenhum arquivo .csv encontrado. Arraste a pasta com as notas em CSV.");
  if (arquivos.length === 1) return arquivos[0];

  const ordenados = [...arquivos].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
  const textos = await Promise.all(ordenados.map((f) => f.text()));
  let cabecalho = "";
  const linhas: string[] = [];
  textos.forEach((texto, i) => {
    const [primeira = "", ...resto] = texto.replace(/^﻿/, "").split(/\r?\n/);
    const atual = primeira.trim();
    if (!cabecalho) cabecalho = atual;
    else if (atual.toUpperCase() !== cabecalho.toUpperCase()) {
      throw new Error(`O arquivo "${ordenados[i].name}" tem colunas diferentes dos outros. Todos precisam usar o mesmo cabeçalho.`);
    }
    linhas.push(...resto.filter((l) => l.trim()));
  });
  return new File([[cabecalho, ...linhas].join("\n") + "\n"], `lote-${arquivos.length}-arquivos.csv`, { type: "text/csv" });
}
