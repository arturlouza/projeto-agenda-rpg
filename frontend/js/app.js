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

// Cria o cartão de uma tarefa a partir do modelo do index.html. Os dados entram só por
// textContent (seção 6.7), então um título como <img src=x> aparece como texto.
function createTaskCard(task) {
  const card = taskCardTemplate.content.firstElementChild.cloneNode(true);

  card.querySelector(".task-title").textContent = task.title;
  card.querySelector(".task-check-name").textContent = task.title;
  card.querySelector(".task-notes-icon").hidden = task.notes === null;

  // O id serve só para o focusTask achar esta caixinha depois de desenhar a lista de novo.
  const checkbox = card.querySelector(".task-checkbox");
  checkbox.id = "task-check-" + task.id;
  checkbox.checked = task.completed;
  // saving fica na seção 6. Ele já existe aqui, porque os cartões só são criados depois de o
  // arquivo inteiro ter rodado.
  checkbox.disabled = saving;
  // A função abaixo "lembra" a tarefa deste cartão, então toggleTask sabe qual tarefa mandar.
  checkbox.addEventListener("change", function () {
    toggleTask(task);
  });

  if (task.completed) {
    card.classList.add("is-completed");
    const xp = card.querySelector(".task-xp");
    xp.textContent = "+" + numberFormat.format(task.xp_earned) + " XP";
    xp.hidden = false;
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

// Enquanto uma caixinha espera a resposta, todas ficam bloqueadas (uma gravação por vez).
let saving = false;

function disableAllCheckboxes() {
  for (const checkbox of document.querySelectorAll(".task-checkbox")) {
    checkbox.disabled = true;
  }
}

function showSaveMessage() {
  const message = document.getElementById("save-message");
  message.textContent = "Não foi possível salvar. Tente de novo.";
  message.hidden = false;
}

function hideSaveMessage() {
  const message = document.getElementById("save-message");
  message.textContent = "";
  message.hidden = true;
}

// Conclui ou desmarca a tarefa e depois recarrega a lista e o topo, com o que o servidor diz.
async function toggleTask(task) {
  saving = true;
  disableAllCheckboxes();
  hideSaveMessage();

  // A ação vem do que o servidor mandou na lista, não do desenho da caixinha.
  const action = task.completed ? "uncomplete" : "complete";
  try {
    await apiRequest("tasks/" + task.id + "/" + action, { method: "POST" });
  } catch (error) {
    // 409: a tela estava desatualizada. Recarregar resolve, então não há mensagem.
    if (error.status !== 409) {
      console.error(error);
      showSaveMessage();
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
// 7. Início
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

loadPlayer();
loadDay();
