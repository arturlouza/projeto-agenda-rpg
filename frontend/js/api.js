// api.js: a conversa com a API e a formatação de números e datas. Carrega primeiro: os outros
// arquivos usam apiRequest, numberFormat e as funções de formatar.

// ---------------------------------------------------------------------------------------------
// 1. API
// ---------------------------------------------------------------------------------------------

// Endereço da API (seção 6.5). Front e API têm a mesma origem, então é um caminho relativo.
const API_BASE = "./";

// Toda chamada à API passa por aqui (seção 6.5). Na tarefa 15, esta função passa a tratar o 401.
// Se a resposta não for de sucesso, o erro leva o código em error.status, para a tela
// reconhecer o 409 sem ler texto, e o motivo da recusa em error.detail, para o formulário
// mostrar o 422. Erro de rede não tem resposta: error.status e error.detail ficam undefined.
// No sucesso, devolve o JSON da resposta, ou null no 204, que não tem corpo.
async function apiRequest(path, options) {
  const response = await fetch(API_BASE + path, options);
  if (!response.ok) {
    const error = new Error("A API respondeu " + response.status);
    error.status = response.status;
    // O "detail" é um texto (as recusas das rotas, em português) ou uma lista (a validação
    // automática). Se a resposta não for JSON com "detail" (um erro 500 em texto, um corpo
    // vazio), fica undefined, e a tela mostra a mensagem genérica.
    try {
      error.detail = (await response.json()).detail;
    } catch {
      error.detail = undefined;
    }
    throw error;
  }
  // 204: deu certo, mas a resposta não tem corpo (o DELETE). Não há JSON para ler, então
  // devolve null, que aqui quer dizer "deu certo, sem dados". As outras rotas respondem 200 ou
  // 201, sempre com JSON, e nunca entram aqui.
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

// ---------------------------------------------------------------------------------------------
// 2. Formatação: só escreve números e datas que vieram prontos da API. Não faz conta.
// ---------------------------------------------------------------------------------------------

// Formata o número com ponto de milhar (2.039).
const numberFormat = new Intl.NumberFormat("pt-BR");

// Escreve a data "2026-11-01" como "01/11/2026", sem conta de data. new Date("2026-11-01") é
// meia-noite em UTC; formatada no fuso do celular (Brasília), viraria 31/10/2026. Com o
// timeZone "UTC", sai o mesmo dia que está no texto.
const dueDateFormat = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "UTC",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

function formatDueDate(text) {
  return dueDateFormat.format(new Date(text));
}

// O mesmo cuidado do timeZone "UTC", agora com o dia da semana por extenso.
const dayTitleFormat = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "UTC",
  weekday: "long",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

// "2026-11-06" vira "Sexta-feira, 06/11/2026". O Intl escreve o dia da semana em minúsculas, então
// a primeira letra passa para maiúscula. É troca de letra, não conta de data.
function formatDayTitle(text) {
  const formatted = dayTitleFormat.format(new Date(text));
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}
