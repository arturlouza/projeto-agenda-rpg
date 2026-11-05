// ---------------------------------------------------------------------------------------------
// 1. API
// ---------------------------------------------------------------------------------------------

// Endereço da API (seção 6.5). Front e API têm a mesma origem, então é um caminho relativo.
const API_BASE = "./";

// Toda chamada à API passa por aqui (seção 6.5). Na tarefa 15, esta função passa a tratar o 401.
// Se a resposta não for de sucesso, o erro leva o código em error.status, para a tela
// reconhecer o 409 sem ler texto. Erro de rede não tem código: error.status fica undefined.
async function apiRequest(path, options) {
  const response = await fetch(API_BASE + path, options);
  if (!response.ok) {
    const error = new Error("A API respondeu " + response.status);
    error.status = response.status;
    throw error;
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

// ---------------------------------------------------------------------------------------------
// 3. Topo: nível, XP e barra
// ---------------------------------------------------------------------------------------------

// Mostra no topo o que o servidor mandou, sem nenhuma conta de XP (regra 9 do CLAUDE.md).
function showPlayer(player) {
  document.getElementById("player-level").textContent = "Nível " + numberFormat.format(player.level);
  document.getElementById("player-xp").textContent =
    numberFormat.format(player.xp_into_level) + " / " + numberFormat.format(player.xp_for_next_level) + " XP";
  document.getElementById("player-progress").value = player.progress_percent;
  document.getElementById("player-message").hidden = true;
}

// Número do pedido mais recente do topo. Se dois pedidos se cruzarem, só o último é mostrado.
let latestPlayerRequest = 0;

// Busca o jogador. Se a rede ou a API falhar, mostra o aviso de erro no lugar do "Carregando…".
async function loadPlayer() {
  latestPlayerRequest = latestPlayerRequest + 1;
  const thisRequest = latestPlayerRequest;
  try {
    const player = await apiRequest("player");
    if (thisRequest === latestPlayerRequest) {
      showPlayer(player);
    }
  } catch (error) {
    if (thisRequest === latestPlayerRequest) {
      console.error(error);
      const message = document.getElementById("player-message");
      message.textContent = "Não foi possível carregar o nível. Recarregue a página.";
      message.classList.add("is-error");
      // Um sucesso anterior escondeu a linha; o erro precisa aparecer de novo.
      message.hidden = false;
    }
  }
}

// ---------------------------------------------------------------------------------------------
// 4. Lista do dia: desenhar
// ---------------------------------------------------------------------------------------------

// Partes da página usadas por várias funções. Com o defer, o HTML já está pronto aqui.
const dayStatus = document.getElementById("day-status");
const dayError = document.getElementById("day-error");
const dayView = document.getElementById("day-view");
const dayEmpty = document.getElementById("day-empty");
const overdueSection = document.getElementById("overdue-section");
const overdueList = document.getElementById("overdue-list");
const pendingSection = document.getElementById("pending-section");
const pendingList = document.getElementById("pending-list");
const completedSection = document.getElementById("completed-section");
const completedSummary = document.getElementById("completed-summary");
const completedCount = document.getElementById("completed-count");
const completedList = document.getElementById("completed-list");
const taskCardTemplate = document.getElementById("task-card-template");

// A última lista desenhada, como veio da API, ou null se a última busca deu erro. O Adiar usa
// para saber se recarregar explicou um 409 (seção 8).
let shownDay = null;

// Cria o cartão de uma tarefa a partir do modelo do index.html. Os dados entram só por
// textContent (seção 6.7), então um título como <img src=x> aparece como texto.
function createTaskCard(task) {
  const card = taskCardTemplate.content.firstElementChild.cloneNode(true);
  // O id serve só para achar o cartão depois: abrir, fechar e devolver o foco.
  card.id = "task-card-" + task.id;

  card.querySelector(".task-title").textContent = task.title;
  card.querySelector(".task-check-name").textContent = task.title;
  card.querySelector(".task-notes-icon").hidden = task.notes === null;

  // O id serve só para o focusTask achar esta caixinha depois de desenhar a lista de novo.
  const checkbox = card.querySelector(".task-checkbox");
  checkbox.id = "task-check-" + task.id;
  checkbox.checked = task.completed;
  // saving fica na seção 6, e openTaskId na seção 7. Eles já existem aqui, porque os cartões só
  // são criados depois de o arquivo inteiro ter rodado.
  checkbox.disabled = saving;
  // A função abaixo "lembra" a tarefa deste cartão, então toggleTask sabe qual tarefa mandar.
  checkbox.addEventListener("change", function () {
    toggleTask(task);
  });

  // O botão do título abre e fecha a parte de baixo. Se este era o cartão aberto antes de a
  // lista ser desenhada de novo, ele já nasce aberto.
  const toggle = card.querySelector(".task-toggle");
  const isOpen = task.id === openTaskId;
  toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  card.querySelector(".task-details").hidden = !isOpen;
  toggle.addEventListener("click", function () {
    toggleCard(task.id);
  });

  // As notas entram por textContent; o CSS (white-space: pre-wrap) mostra as quebras de linha.
  if (task.notes !== null) {
    const notes = card.querySelector(".task-notes");
    notes.textContent = task.notes;
    notes.hidden = false;
  }

  if (task.completed) {
    card.classList.add("is-completed");
    const xp = card.querySelector(".task-xp");
    xp.textContent = "+" + numberFormat.format(task.xp_earned) + " XP";
    xp.hidden = false;

    // A concluída não tem Adiar (seção 6.2). Sem notas, o cartão aberto diz isso, para não
    // abrir vazio até o Editar da tarefa 11.
    card.querySelector(".task-postpone-area").hidden = true;
    card.querySelector(".task-no-notes").hidden = task.notes !== null;
  } else {
    // A trava vem pronta do servidor (due_date_locked): a tela não conta adiamentos.
    const postpone = card.querySelector(".task-postpone");
    postpone.disabled = saving || task.due_date_locked;
    card.querySelector(".task-postpone-locked").hidden = !task.due_date_locked;
    postpone.addEventListener("click", function () {
      handlePostponeClick(task, postpone);
    });
  }

  return card;
}

// O cartão de uma atrasada: o mesmo cartão, com a data marcada escrita.
function createOverdueCard(task) {
  const card = createTaskCard(task);
  const dueDate = card.querySelector(".task-due-date");
  dueDate.textContent = "Marcada para " + formatDueDate(task.due_date);
  dueDate.hidden = false;
  return card;
}

// Desenha o dia que a API mandou. Só as listas são esvaziadas e preenchidas: o <details> das
// Concluídas continua o mesmo elemento, então fica aberto se estava aberto.
function showDay(day) {
  // Os botões antigos vão ser trocados por novos: a confirmação do Adiar, se houver, acaba aqui.
  cancelPostponeConfirmation();
  shownDay = day;

  overdueList.replaceChildren();
  for (const task of day.overdue) {
    overdueList.append(createOverdueCard(task));
  }

  pendingList.replaceChildren();
  for (const task of day.pending) {
    pendingList.append(createTaskCard(task));
  }

  completedList.replaceChildren();
  for (const task of day.completed) {
    completedList.append(createTaskCard(task));
  }

  // Se a tarefa do cartão aberto saiu da lista (adiada, excluída, dia novo), nenhum fica aberto.
  // Assim ela não reaparece aberta quando voltar a outra lista.
  if (openTaskId !== null && document.getElementById("task-card-" + openTaskId) === null) {
    openTaskId = null;
  }

  overdueSection.hidden = day.overdue.length === 0;
  pendingSection.hidden = day.pending.length === 0;
  completedSection.hidden = day.completed.length === 0;
  completedCount.textContent = numberFormat.format(day.completed.length);
  dayEmpty.hidden = !(day.overdue.length === 0 && day.pending.length === 0 && day.completed.length === 0);

  dayStatus.hidden = true;
  dayError.hidden = true;
  dayView.hidden = false;
}

// ---------------------------------------------------------------------------------------------
// 5. Lista do dia: buscar
// ---------------------------------------------------------------------------------------------

function showDayLoading() {
  dayError.hidden = true;
  dayView.hidden = true;
  dayStatus.hidden = false;
}

// Troca a lista pelo aviso de erro. Melhor do que deixar na tela uma lista que pode ser velha.
function showDayError() {
  shownDay = null;
  dayStatus.hidden = true;
  dayView.hidden = true;
  dayError.hidden = false;
}

// Número do pedido mais recente da lista. Se dois pedidos se cruzarem, só o último é desenhado.
let latestDayRequest = 0;

// Busca a lista de hoje. O servidor diz que dia é: a tela nunca lê o relógio do celular.
async function loadDay() {
  latestDayRequest = latestDayRequest + 1;
  const thisRequest = latestDayRequest;
  try {
    const day = await apiRequest("tasks/today");
    if (thisRequest === latestDayRequest) {
      showDay(day);
    }
  } catch (error) {
    if (thisRequest === latestDayRequest) {
      console.error(error);
      showDayError();
    }
  }
}

// ---------------------------------------------------------------------------------------------
// 6. Caixinha: concluir e desmarcar
// ---------------------------------------------------------------------------------------------

const SAVE_ERROR_TEXT = "Não foi possível salvar. Tente de novo.";

// Enquanto uma gravação espera a resposta (caixinha ou Adiar), as caixinhas e os botões Adiar
// ficam bloqueados (uma gravação por vez). Os botões do título continuam livres: abrir e fechar
// não grava nada.
let saving = false;

function disableTaskControls() {
  for (const control of document.querySelectorAll(".task-checkbox, .task-postpone")) {
    control.disabled = true;
  }
}

// A linha de erro do topo. O texto muda: erro ao salvar ou a última data possível (seção 8).
function showSaveMessage(text) {
  const message = document.getElementById("save-message");
  message.textContent = text;
  message.hidden = false;
}

// Esconde a linha de erro e o aviso do Adiar. Toda gravação nova começa por aqui.
function hideMessages() {
  const message = document.getElementById("save-message");
  message.textContent = "";
  message.hidden = true;
  hidePostponeNotice();
}

// Conclui ou desmarca a tarefa e depois recarrega a lista e o topo, com o que o servidor diz.
async function toggleTask(task) {
  saving = true;
  disableTaskControls();
  hideMessages();

  // A ação vem do que o servidor mandou na lista, não do desenho da caixinha.
  const action = task.completed ? "uncomplete" : "complete";
  try {
    await apiRequest("tasks/" + task.id + "/" + action, { method: "POST" });
  } catch (error) {
    // 409: a tela estava desatualizada. Recarregar resolve, então não há mensagem.
    if (error.status !== 409) {
      console.error(error);
      showSaveMessage(SAVE_ERROR_TEXT);
    }
  }

  saving = false;
  await refreshScreen();
  focusTask(task.id);
}

// Devolve o foco à caixinha da tarefa depois de desenhar a lista de novo. Se ela foi para as
// Concluídas fechadas, o foco vai para o "Concluídas (N)". Se ela sumiu, não faz nada.
function focusTask(taskId) {
  const checkbox = document.getElementById("task-check-" + taskId);
  if (checkbox === null) {
    return;
  }
  if (completedSection.contains(checkbox) && !completedSection.open) {
    completedSummary.focus();
  } else {
    checkbox.focus();
  }
}

// ---------------------------------------------------------------------------------------------
// 7. Cartão: abrir e fechar
// ---------------------------------------------------------------------------------------------

// O id da tarefa do cartão aberto, ou null. Um cartão aberto por vez. Quando a lista é
// desenhada de novo, o createTaskCard lê esta variável, e o cartão continua aberto.
let openTaskId = null;

// Abre o cartão tocado e fecha o que estava aberto. Tocar no cartão aberto só fecha. Não
// desenha a lista de novo, então o foco continua no botão tocado.
function toggleCard(taskId) {
  cancelPostponeConfirmation();
  const previousTaskId = openTaskId;
  if (previousTaskId !== null) {
    setCardOpen(previousTaskId, false);
  }
  if (previousTaskId === taskId) {
    openTaskId = null;
  } else {
    openTaskId = taskId;
    setCardOpen(taskId, true);
  }
}

// aria-expanded diz ao leitor de tela se o cartão está aberto ("expandido") ou fechado.
function setCardOpen(taskId, open) {
  const card = document.getElementById("task-card-" + taskId);
  if (card === null) {
    return;
  }
  card.querySelector(".task-toggle").setAttribute("aria-expanded", open ? "true" : "false");
  card.querySelector(".task-details").hidden = !open;
}

// Devolve o foco ao botão do título depois de desenhar a lista de novo. Se a tarefa sumiu
// (foi adiada), não faz nada, como o focusTask.
function focusCardToggle(taskId) {
  const card = document.getElementById("task-card-" + taskId);
  if (card === null) {
    return;
  }
  card.querySelector(".task-toggle").focus();
}

// ---------------------------------------------------------------------------------------------
// 8. Adiar, com confirmação
// ---------------------------------------------------------------------------------------------

// Os textos do botão. O "−25% XP" é fixo: cada adiamento tira 25% (seção 4.2), e a tela não faz conta.
const POSTPONE_LABEL = "Adiar";
const POSTPONE_CONFIRM_LABEL = "Confirmar adiar (−25% XP)";
const LAST_DATE_TEXT = "Esta tarefa já está na última data possível e não pode ser adiada.";

// Quanto tempo a confirmação espera antes de voltar ao normal; quanto tempo ela ignora o toque,
// para um toque duplo no "Adiar" não confirmar sozinho; e quanto tempo o aviso fica no topo.
const POSTPONE_CONFIRM_TIMEOUT_MS = 5000;
const DOUBLE_TAP_GUARD_MS = 500;
const POSTPONE_NOTICE_MS = 10000;

// O botão que está pedindo confirmação, ou null.
let confirmButton = null;
// Falso no primeiro meio segundo da confirmação: o segundo toque de um toque duplo não vale.
let confirmReady = false;
// Os números que o setTimeout devolve, para o clearTimeout desistir deles.
let confirmTimer = null;
let readyTimer = null;
let noticeTimer = null;

// Primeiro toque: pede confirmação. Segundo toque no mesmo botão, depois do meio segundo: adia.
function handlePostponeClick(task, button) {
  if (confirmButton !== button) {
    startPostponeConfirmation(button);
    return;
  }
  if (!confirmReady) {
    return;
  }
  cancelPostponeConfirmation();
  postponeTask(task);
}

function startPostponeConfirmation(button) {
  cancelPostponeConfirmation();
  confirmButton = button;
  confirmReady = false;
  button.textContent = POSTPONE_CONFIRM_LABEL;
  button.classList.add("is-confirming");
  readyTimer = setTimeout(function () {
    confirmReady = true;
  }, DOUBLE_TAP_GUARD_MS);
  confirmTimer = setTimeout(cancelPostponeConfirmation, POSTPONE_CONFIRM_TIMEOUT_MS);
}

// Volta o botão ao normal. Chamada pelo tempo, por um toque em outra coisa (seção 9), ao abrir
// ou fechar um cartão e ao desenhar a lista de novo. Sem confirmação em andamento, não faz nada.
function cancelPostponeConfirmation() {
  clearTimeout(readyTimer);
  clearTimeout(confirmTimer);
  if (confirmButton !== null) {
    confirmButton.textContent = POSTPONE_LABEL;
    confirmButton.classList.remove("is-confirming");
    confirmButton = null;
  }
}

// Adia a tarefa e depois recarrega a lista e o topo. A tarefa adiada sai da lista de hoje, e o
// aviso no topo diz para onde ela foi.
async function postponeTask(task) {
  saving = true;
  disableTaskControls();
  hideMessages();

  let postponed = null;
  let refused = false;
  try {
    // Manda a data que veio da lista. A data nova é o servidor quem calcula (tarefa 7). O
    // Content-Type diz ao servidor que o corpo do pedido está em JSON.
    postponed = await apiRequest("tasks/" + task.id + "/postpone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shown_due_date: task.due_date }),
    });
  } catch (error) {
    if (error.status === 409) {
      refused = true;
    } else {
      console.error(error);
      showSaveMessage(SAVE_ERROR_TEXT);
    }
  }

  saving = false;
  await refreshScreen();

  if (postponed !== null) {
    showPostponeNotice(postponed);
  }
  // 409 que recarregar explicou (tela desatualizada, concluída, travada): sem mensagem.
  if (refused && reloadDidNotExplain(task)) {
    showSaveMessage(LAST_DATE_TEXT);
  }
  focusCardToggle(task.id);
}

// Depois de um 409 e da lista recarregada: se a tarefa continua pendente, com a mesma data e sem
// trava, recarregar não explicou a recusa. Das recusas da rota (tarefa 7), só sobra a última
// data possível. A comparação é de igualdade entre dois textos do servidor, sem conta de data.
function reloadDidNotExplain(task) {
  if (shownDay === null) {
    return false;
  }
  for (const listed of shownDay.overdue.concat(shownDay.pending)) {
    if (listed.id === task.id) {
      return listed.due_date === task.due_date && !listed.due_date_locked;
    }
  }
  return false;
}

// A data nova vem da resposta do servidor, só formatada.
function showPostponeNotice(postponed) {
  const notice = document.getElementById("postpone-notice");
  notice.textContent = "Adiada para " + formatDueDate(postponed.due_date) + ": " + postponed.title;
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(hidePostponeNotice, POSTPONE_NOTICE_MS);
}

function hidePostponeNotice() {
  clearTimeout(noticeTimer);
  const notice = document.getElementById("postpone-notice");
  notice.textContent = "";
  notice.hidden = true;
}

// ---------------------------------------------------------------------------------------------
// 9. Início
// ---------------------------------------------------------------------------------------------

// Pede a lista e o topo ao mesmo tempo. Cada um trata o próprio erro.
async function refreshScreen() {
  await Promise.all([loadDay(), loadPlayer()]);
}

document.getElementById("day-retry").addEventListener("click", function () {
  showDayLoading();
  loadDay();
});

// Quando o app volta do segundo plano, pede a lista e o topo de novo. O servidor diz que dia é:
// se a meia-noite passou enquanto o app estava escondido, a tela já mostra o dia novo.
document.addEventListener("visibilitychange", function () {
  if (document.visibilityState === "visible") {
    refreshScreen();
  }
});

// Todo clique da página "sobe" até o document. Se ele não começou no botão que pede
// confirmação, a confirmação acaba. O clique que a iniciou chega aqui depois, com o alvo igual
// ao botão, e por isso não a cancela.
document.addEventListener("click", function (event) {
  if (confirmButton !== null && event.target !== confirmButton) {
    cancelPostponeConfirmation();
  }
});

loadPlayer();
loadDay();
