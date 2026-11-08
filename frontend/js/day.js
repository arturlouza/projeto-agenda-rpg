// day.js: a lista do dia. Desenha e busca o dia, conclui e desmarca pela caixinha, abre o
// cartão, adia com confirmação e navega entre os dias. Carrega depois do api.js e do
// top-bar.js. Chama refreshScreen, do app.js, e openTaskForm, do task-form.js, só depois de um
// toque, com tudo já carregado.

// ---------------------------------------------------------------------------------------------
// 1. Lista do dia: desenhar
// ---------------------------------------------------------------------------------------------

// Partes da página usadas por várias funções. Com o defer, o HTML já está pronto aqui.
const dayStatus = document.getElementById("day-status");
const dayError = document.getElementById("day-error");
const dayView = document.getElementById("day-view");
const dayEmpty = document.getElementById("day-empty");
const overdueSection = document.getElementById("overdue-section");
const overdueList = document.getElementById("overdue-list");
const pendingSection = document.getElementById("pending-section");
const pendingTitle = document.getElementById("pending-title");
const pendingList = document.getElementById("pending-list");
const completedSection = document.getElementById("completed-section");
const completedSummary = document.getElementById("completed-summary");
const completedCount = document.getElementById("completed-count");
const completedList = document.getElementById("completed-list");
const taskCardTemplate = document.getElementById("task-card-template");
const dayPrevious = document.getElementById("day-previous");
const dayNext = document.getElementById("day-next");
const dayToday = document.getElementById("day-today");
const dayPicker = document.getElementById("day-picker");

const EMPTY_TODAY_TEXT = "Nenhuma tarefa para hoje.";
const EMPTY_DAY_TEXT = "Nenhuma tarefa neste dia.";

// A última lista desenhada, como veio da API, ou null se a última busca deu erro. O Adiar usa
// para saber se recarregar explicou um 409 (seção 5).
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
  // saving fica na seção 3, e openTaskId na seção 4. Eles já existem aqui, porque os cartões só
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

  // O Editar abre o formulário preenchido com esta tarefa, como veio da lista. Uma gravação por
  // vez: enquanto outra espera a resposta, ele fica bloqueado, como a caixinha e o Adiar.
  const edit = card.querySelector(".task-edit");
  edit.disabled = saving;
  edit.addEventListener("click", function () {
    openTaskForm(task);
  });

  if (task.completed) {
    card.classList.add("is-completed");
    const xp = card.querySelector(".task-xp");
    xp.textContent = "+" + numberFormat.format(task.xp_earned) + " XP";
    xp.hidden = false;

    // A concluída não tem Adiar (seção 6.2): o cartão aberto mostra as notas, se houver, e o
    // Editar.
    card.querySelector(".task-postpone").hidden = true;
  } else {
    // A trava vem pronta do servidor (due_date_locked): a tela não conta adiamentos.
    const postpone = card.querySelector(".task-postpone");
    postpone.disabled = saving || task.due_date_locked;
    card.querySelector(".task-postpone-locked").hidden = !task.due_date_locked;
    // O Adiar pede confirmação (seção 5). A função entregue só roda no segundo toque.
    postpone.addEventListener("click", function () {
      handleConfirmClick(postpone, POSTPONE_CONFIRM_LABEL, function () {
        postponeTask(task);
      });
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
  // Os botões antigos vão ser trocados por novos: a confirmação em dois toques, se houver, acaba
  // aqui (também a do Excluir, se a lista recarregar com o formulário aberto).
  cancelConfirmation();
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

  // O dia escrito na tela vem do "day" da resposta, e o "é hoje?", do is_today: a tela não
  // compara datas. As setas usam os vizinhos que vieram prontos; null bloqueia a seta. dayPath
  // e TODAY_PATH ficam na seção 2.
  pendingTitle.textContent = day.is_today ? "Hoje" : formatDayTitle(day.day);
  dayEmpty.textContent = day.is_today ? EMPTY_TODAY_TEXT : EMPTY_DAY_TEXT;
  dayPicker.value = day.day;
  dayPrevious.disabled = day.previous_day === null;
  dayNext.disabled = day.next_day === null;
  // Chegou a hoje por uma seta ou pelo calendário: daqui em diante, recarrega como "Hoje", para
  // a virada da meia-noite levar a tela ao dia novo.
  if (day.is_today) {
    dayPath = TODAY_PATH;
  }

  dayStatus.hidden = true;
  dayError.hidden = true;
  dayView.hidden = false;
}

// ---------------------------------------------------------------------------------------------
// 2. Lista do dia: buscar
// ---------------------------------------------------------------------------------------------

function showDayLoading() {
  dayError.hidden = true;
  dayView.hidden = true;
  dayStatus.hidden = false;
}

// Troca a lista pelo aviso de erro. Melhor do que deixar na tela uma lista que pode ser velha.
// Sem dia na tela, as setas não têm de onde partir e ficam bloqueadas; "Hoje" e o calendário
// continuam livres.
function showDayError() {
  shownDay = null;
  dayPrevious.disabled = true;
  dayNext.disabled = true;
  dayStatus.hidden = true;
  dayView.hidden = true;
  dayError.hidden = false;
}

const TODAY_PATH = "tasks/today";

// O caminho do dia da tela: "tasks/today" em hoje, ou "tasks/day/AAAA-MM-DD" em outro dia. As
// recargas (depois de gravar, ao voltar ao app e no "Tentar de novo") pedem este caminho. É um
// texto montado com o que veio da API ou do campo de data, sem conta de data.
let dayPath = TODAY_PATH;

// Número do pedido mais recente da lista. Se dois pedidos se cruzarem, só o último é desenhado.
let latestDayRequest = 0;

// Busca o dia de dayPath. O servidor diz que dia é hoje: a tela nunca lê o relógio do celular.
async function loadDay() {
  latestDayRequest = latestDayRequest + 1;
  const thisRequest = latestDayRequest;
  try {
    const day = await apiRequest(dayPath);
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
// 3. Caixinha: concluir e desmarcar
// ---------------------------------------------------------------------------------------------

const SAVE_ERROR_TEXT = "Não foi possível salvar. Tente de novo.";

// Enquanto uma gravação espera a resposta (caixinha, Adiar, Salvar ou Excluir), as caixinhas e
// os botões Editar e Adiar ficam bloqueados (uma gravação por vez), e o formulário não abre
// (seção 1 do task-form.js). Os botões do título continuam livres: abrir e fechar não grava nada.
let saving = false;

function disableTaskControls() {
  for (const control of document.querySelectorAll(".task-checkbox, .task-edit, .task-postpone")) {
    control.disabled = true;
  }
}

// Conclui ou desmarca a tarefa e depois recarrega a lista e o topo, com o que o servidor diz.
async function toggleTask(task) {
  saving = true;
  disableTaskControls();
  hideMessages();

  // A ação vem do que o servidor mandou na lista, não do desenho da caixinha.
  const action = task.completed ? "uncomplete" : "complete";
  let result = null;
  try {
    result = await apiRequest("tasks/" + task.id + "/" + action, { method: "POST" });
  } catch (error) {
    // 409: a tela estava desatualizada. Recarregar resolve, então não há mensagem.
    if (error.status !== 409) {
      console.error(error);
      showSaveMessage(SAVE_ERROR_TEXT);
    }
  }

  saving = false;
  await refreshScreen();
  if (result !== null) {
    showMovedNotice(result.task);
  }
  focusTask(task.id);
}

// Depois de concluir ou desmarcar e de recarregar: se a tarefa não está mais na lista desenhada,
// o aviso diz para onde ela foi. A tela não prevê se ela some: olha o resultado. A concluída vai
// para as Concluídas do dia em que foi concluída, hoje (seção 6.2); a desmarcada volta ao dia
// marcado, com a data da resposta do servidor, só formatada. Sem lista (erro), não avisa: o
// aviso de erro já está na tela.
function showMovedNotice(savedTask) {
  if (shownDay === null || document.getElementById("task-card-" + savedTask.id) !== null) {
    return;
  }
  if (savedTask.completed) {
    showNotice("Foi para as Concluídas de hoje: " + savedTask.title);
  } else {
    showNotice("Desmarcada, voltou para " + formatDueDate(savedTask.due_date) + ": " + savedTask.title);
  }
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
// 4. Cartão: abrir e fechar
// ---------------------------------------------------------------------------------------------

// O id da tarefa do cartão aberto, ou null. Um cartão aberto por vez. Quando a lista é
// desenhada de novo, o createTaskCard lê esta variável, e o cartão continua aberto.
let openTaskId = null;

// Abre o cartão tocado e fecha o que estava aberto. Tocar no cartão aberto só fecha. Não
// desenha a lista de novo, então o foco continua no botão tocado.
function toggleCard(taskId) {
  cancelConfirmation();
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

// Fecha o cartão aberto, se houver, e cancela a confirmação em dois toques. Usada ao mudar de dia.
function closeOpenCard() {
  cancelConfirmation();
  if (openTaskId !== null) {
    setCardOpen(openTaskId, false);
    openTaskId = null;
  }
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
// 5. Confirmação em dois toques (Adiar e Excluir) e o Adiar
// ---------------------------------------------------------------------------------------------

// Quanto tempo a confirmação espera antes de voltar ao normal, e quanto tempo ela ignora o toque,
// para um toque duplo não confirmar sozinho. Vale para o Adiar e para o Excluir do formulário
// (task-form.js), e o meio segundo também para a confirmação da data nova.
const CONFIRM_TIMEOUT_MS = 5000;
const DOUBLE_TAP_GUARD_MS = 500;

// O botão que está pedindo confirmação, ou null, e o texto que ele tinha antes, para voltar a ele.
let confirmButton = null;
let confirmButtonLabel = "";
// Falso no primeiro meio segundo da confirmação: o segundo toque de um toque duplo não vale.
let confirmReady = false;
// Os números que o setTimeout devolve, para o clearTimeout desistir deles.
let confirmTimer = null;
let readyTimer = null;

// Primeiro toque: pede confirmação, com o texto confirmLabel no botão. Segundo toque no mesmo
// botão, depois do meio segundo: desfaz a confirmação e faz a ação. action é uma função, que esta
// aqui chama só na hora certa: o Adiar entrega uma que adia a tarefa do cartão, e o Excluir
// entrega deleteTask.
function handleConfirmClick(button, confirmLabel, action) {
  if (confirmButton !== button) {
    startConfirmation(button, confirmLabel);
    return;
  }
  if (!confirmReady) {
    return;
  }
  cancelConfirmation();
  action();
}

function startConfirmation(button, confirmLabel) {
  cancelConfirmation();
  confirmButton = button;
  confirmButtonLabel = button.textContent;
  confirmReady = false;
  button.textContent = confirmLabel;
  button.classList.add("is-confirming");
  readyTimer = setTimeout(function () {
    confirmReady = true;
  }, DOUBLE_TAP_GUARD_MS);
  confirmTimer = setTimeout(cancelConfirmation, CONFIRM_TIMEOUT_MS);
}

// Volta o botão ao texto de antes. Chamada pelo tempo, por um toque em outra coisa (no app.js),
// ao abrir ou fechar um cartão, ao mudar de dia, ao desenhar a lista de novo e, no formulário, ao
// mexer num campo, ao abrir e ao fechar. Sem confirmação em andamento, não faz nada.
function cancelConfirmation() {
  clearTimeout(readyTimer);
  clearTimeout(confirmTimer);
  if (confirmButton !== null) {
    confirmButton.textContent = confirmButtonLabel;
    confirmButton.classList.remove("is-confirming");
    confirmButton = null;
  }
}

// O texto da confirmação do Adiar. O "−25% XP" é fixo: cada adiamento tira 25% (seção 4.2), e a
// tela não faz conta.
const POSTPONE_CONFIRM_LABEL = "Confirmar adiar (−25% XP)";
const LAST_DATE_TEXT = "Esta tarefa já está na última data possível e não pode ser adiada.";

// Adia a tarefa e depois recarrega a lista e o topo. A tarefa adiada sai da lista do dia, e o
// aviso no topo diz para onde ela foi, com a data nova da resposta do servidor, só formatada.
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
    showNotice("Adiada para " + formatDueDate(postponed.due_date) + ": " + postponed.title);
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

// ---------------------------------------------------------------------------------------------
// 6. Navegar entre os dias
// ---------------------------------------------------------------------------------------------

// Leva a tela para outro dia. O cartão fecha já no toque, e não só quando o dia novo chegar. A
// lista antiga fica na tela até a nova chegar, para a tela não piscar a cada toque.
function goToDay(path) {
  closeOpenCard();
  dayPath = path;
  loadDay();
}

// As setas apontam para os vizinhos do dia que está na tela, que vieram prontos da API. Enquanto
// o dia novo não chega, a seta aponta para o mesmo vizinho: um toque duplo anda um dia só. Elas
// só ficam livres com um dia na tela (showDay), então shownDay nunca é null aqui.
dayPrevious.addEventListener("click", function () {
  goToDay("tasks/day/" + shownDay.previous_day);
});

dayNext.addEventListener("click", function () {
  goToDay("tasks/day/" + shownDay.next_day);
});

dayToday.addEventListener("click", function () {
  goToDay(TODAY_PATH);
});

// O campo entrega "" (vazio ou data incompleta) ou uma data AAAA-MM-DD, o mesmo formato da API.
// Fora do min e do max do HTML, o próprio navegador marca validity.valid como falso. Nos dois
// casos, nada é pedido. Se não, a data vai para a API exatamente como o campo a entregou.
dayPicker.addEventListener("change", function () {
  if (dayPicker.value === "" || !dayPicker.validity.valid) {
    return;
  }
  goToDay("tasks/day/" + dayPicker.value);
});

// Ao sair do campo vazio ou inválido, ele volta a mostrar o dia da tela. Não volta no change,
// para não atrapalhar quem ainda está digitando a data.
dayPicker.addEventListener("blur", function () {
  if (shownDay !== null && (dayPicker.value === "" || !dayPicker.validity.valid)) {
    dayPicker.value = shownDay.day;
  }
});
