// task-form.js: o formulário de criar, de editar e de excluir tarefa. Abre o <dialog> vazio
// ("Nova tarefa") ou preenchido com uma tarefa da lista (Editar), busca os tipos, grava pelo
// POST /tasks ou pelo PUT /tasks/{id}, exclui pelo DELETE /tasks/{id}, com confirmação em dois
// toques, e mostra os erros em português. Carrega depois do day.js. Ao carregar, só usa o HTML e
// os nomes deste arquivo; saving, shownDay, loadDay, showNotice, cancelConfirmation e companhia,
// dos arquivos anteriores, só são usados depois de um toque.

// ---------------------------------------------------------------------------------------------
// 1. Abrir e fechar
// ---------------------------------------------------------------------------------------------

// Partes da página usadas por várias funções. Com o defer, o HTML já está pronto aqui.
const newTaskButton = document.getElementById("new-task");
const taskFormDialog = document.getElementById("task-form-dialog");
const taskForm = document.getElementById("task-form");
const formHeading = document.getElementById("task-form-heading");
const formTitle = document.getElementById("task-form-title");
const formDueDate = document.getElementById("task-form-due-date");
const formDatePostpone = document.getElementById("task-form-date-postpone");
const formDateLocked = document.getElementById("task-form-date-locked");
const formDateCompleted = document.getElementById("task-form-date-completed");
const formDifficulty = document.getElementById("task-form-difficulty");
const formDifficultyCompleted = document.getElementById("task-form-difficulty-completed");
const formColor = document.getElementById("task-form-color");
const formDefaultColor = document.getElementById("task-form-default-color");
const formType = document.getElementById("task-form-type");
const formTypesError = document.getElementById("task-form-types-error");
const formTypesKept = document.getElementById("task-form-types-kept");
const formTypeGone = document.getElementById("task-form-type-gone");
const formNotes = document.getElementById("task-form-notes");
const formError = document.getElementById("task-form-error");
const formConfirm = document.getElementById("task-form-confirm");
const formCancel = document.getElementById("task-form-cancel");
const formSave = document.getElementById("task-form-save");
const formDeleteArea = document.getElementById("task-form-delete-area");
const formDeletePending = document.getElementById("task-form-delete-pending");
const formDeleteCompleted = document.getElementById("task-form-delete-completed");
const formDelete = document.getElementById("task-form-delete");
// O "Sem tipo" escrito no HTML. Fica guardado para a lista de tipos sempre começar por ele.
const formNoTypeOption = formType.options[0];

const NEW_TASK_HEADING = "Nova tarefa";
const EDIT_TASK_HEADING = "Editar tarefa";

// Falso enquanto a cor não for escolhida. Assim o pedido de criar não leva a cor, e o servidor
// aplica a cor padrão dele (DEFAULT_TASK_COLOR): o JavaScript não tem a cor escrita em lugar
// nenhum. A edição manda sempre a cor do campo (seção 5).
let colorChosen = false;

// A tarefa que está sendo editada, como veio da lista quando o Editar foi tocado, ou null ao
// criar. É daqui que sai o shown_due_date, a data que o formulário mostrou ao abrir. Não muda
// enquanto o formulário está aberto, nem se a lista de trás for desenhada de novo.
let editingTask = null;

// Abre o formulário: vazio no "Nova tarefa" (task é null) ou preenchido no Editar (task é a
// tarefa da lista). reset() volta cada campo ao que está escrito no HTML (Fácil, cor padrão,
// textos vazios). O foco vai para o Título, pelo autofocus do HTML.
function openTaskForm(task) {
  // Uma gravação por vez (decisão da etapa 11.4): enquanto outra gravação espera a resposta, o
  // formulário não abre. Sem isso, depois de dois Esc durante uma gravação lenta, o fim dela
  // fecharia o formulário aberto de novo, ou mostraria nele um erro que não é dele.
  if (saving) {
    return;
  }
  editingTask = task;
  taskForm.reset();
  colorChosen = false;
  clearFormErrors();
  cancelDateConfirmation();
  // Cada abertura começa com o "Excluir" normal, sem confirmação armada.
  cancelConfirmation();
  if (task === null) {
    formHeading.textContent = NEW_TASK_HEADING;
    // A data sugerida vem pronta do servidor (new_task_due_date): o dia da tela ou, se ele já
    // passou, hoje. A tela não compara datas. O botão só aparece com um dia na tela, então
    // shownDay nunca é null aqui.
    formDueDate.value = shownDay.new_task_due_date;
  } else {
    formHeading.textContent = EDIT_TASK_HEADING;
    fillTaskForm(task);
  }
  showLockedFields(task);
  showDeleteArea(task);
  loadTaskTypes(task === null ? null : task.task_type_id);
  taskFormDialog.showModal();
}

// Preenche os campos com a tarefa, por value (seção 6.7). O tipo fica para loadTaskTypes (seção 2),
// porque depende da lista de tipos.
function fillTaskForm(task) {
  formTitle.value = task.title;
  formDueDate.value = task.due_date;
  formDifficulty.value = task.difficulty;
  // O campo de cor aceita a cor em maiúsculas que vem do servidor ("#F5E6C8") e a guarda em
  // minúsculas ("#f5e6c8"). Ao salvar, o servidor grava de novo em maiúsculas.
  formColor.value = task.color;
  // Sem notas, o servidor manda null; o campo fica vazio.
  formNotes.value = task.notes === null ? "" : task.notes;
}

// Bloqueia o que não pode mudar e mostra o motivo embaixo do campo. As travas vêm prontas do
// servidor: completed e due_date_locked. Na concluída, completed decide sozinho (decisão da etapa
// 10.1). Os campos bloqueados continuam com o valor da tarefa, que vai no pedido, e para o
// servidor o mesmo valor não é mudança (seção 6.1). Ao criar (task é null), libera tudo: o
// reset() não mexe no disabled, que não é valor de campo.
function showLockedFields(task) {
  const editing = task !== null;
  const completed = editing && task.completed;
  const dateLocked = editing && !completed && task.due_date_locked;

  formDueDate.disabled = completed || dateLocked;
  formDifficulty.disabled = completed;

  formDatePostpone.hidden = !(editing && !completed && !dateLocked);
  formDateLocked.hidden = !dateLocked;
  formDateCompleted.hidden = !completed;
  formDifficultyCompleted.hidden = !completed;
}

// A área do Excluir aparece só na edição, nunca no "Nova tarefa". O texto sobre o XP vem do
// completed do servidor: a pendente (inclusive a atrasada) ou a concluída (seção 6).
function showDeleteArea(task) {
  const editing = task !== null;
  formDeleteArea.hidden = !editing;
  formDeletePending.hidden = !(editing && !task.completed);
  formDeleteCompleted.hidden = !(editing && task.completed);
}

newTaskButton.addEventListener("click", function () {
  openTaskForm(null);
});

// Fecha sem gravar.
formCancel.addEventListener("click", function () {
  taskFormDialog.close();
});

// O Esc e o gesto de voltar do Android disparam "cancel" antes de fechar. Durante a gravação,
// o formulário não fecha, para um erro poder aparecer nele com o que foi digitado. O Chrome só
// deixa bloquear uma vez por toque: um segundo Esc seguido fecha de qualquer jeito, e o erro,
// se houver, vai para o topo (seção 5).
taskFormDialog.addEventListener("cancel", function (event) {
  if (saving) {
    event.preventDefault();
  }
});

// Ao fechar (Salvar, Cancelar, Esc), o navegador devolve o foco a quem abriu o formulário. Na
// criação, é o "Nova tarefa", que continua na página. Na edição, o Editar que abriu pode ter sido
// trocado por um novo, se a lista foi desenhada de novo nesse meio tempo (depois de um erro, ou
// na volta ao app). O evento "close" chega depois de o navegador devolver o foco, então o foco
// fica onde focusEditedTask mandar. Fechar também desfaz a confirmação do Excluir, se houver: ela
// vale só para esta abertura.
taskFormDialog.addEventListener("close", function () {
  cancelConfirmation();
  if (editingTask !== null) {
    focusEditedTask(editingTask.id);
  }
});

// O foco vai para o Editar da tarefa, se ela está na lista desenhada; se ela saiu (data nova,
// excluída), vai para o "Nova tarefa", que nunca é desenhado de novo.
function focusEditedTask(taskId) {
  const card = document.getElementById("task-card-" + taskId);
  if (card === null) {
    newTaskButton.focus();
    return;
  }
  card.querySelector(".task-edit").focus();
}

// Mexer na cor marca a cor como escolhida.
formColor.addEventListener("input", function () {
  colorChosen = true;
});

// defaultValue é o value escrito no HTML: a cor padrão, sem repeti-la aqui.
formDefaultColor.addEventListener("click", function () {
  formColor.value = formColor.defaultValue;
  colorChosen = false;
});

// ---------------------------------------------------------------------------------------------
// 2. Tipos
// ---------------------------------------------------------------------------------------------

// O texto da opção que guarda o tipo da tarefa na edição, enquanto a lista de tipos não chega.
const CURRENT_TYPE_TEXT = "Tipo atual";

// Número do pedido mais recente dos tipos. Abrir, fechar e abrir rápido não mistura listas.
let latestTypesRequest = 0;

// Busca os tipos a cada abertura, para a lista nunca ficar velha. Enquanto o pedido não chega,
// o campo fica bloqueado; o resto do formulário já funciona. currentTypeId é o tipo da tarefa
// editada, ou null (ao criar, ou numa tarefa sem tipo).
//
// O pedido leva o value do campo, então o campo precisa mostrar, desde o começo, o que deve ir
// no pedido. Na edição de uma tarefa com tipo, ele nasce numa opção "Tipo atual", com o id do
// tipo dela. Assim, salvar antes de os tipos chegarem, ou com o pedido dos tipos falhando,
// mantém o tipo, em vez de mandar "Sem tipo" e apagá-lo.
async function loadTaskTypes(currentTypeId) {
  latestTypesRequest = latestTypesRequest + 1;
  const thisRequest = latestTypesRequest;
  formType.replaceChildren(formNoTypeOption);
  if (currentTypeId !== null) {
    const current = document.createElement("option");
    current.value = currentTypeId;
    current.textContent = CURRENT_TYPE_TEXT;
    formType.append(current);
  }
  formType.value = currentTypeId === null ? "" : String(currentTypeId);
  formType.disabled = true;
  formTypesError.hidden = true;
  formTypesKept.hidden = true;
  formTypeGone.hidden = true;
  try {
    const types = await apiRequest("task-types");
    if (thisRequest === latestTypesRequest) {
      showTaskTypes(types, currentTypeId);
      formType.disabled = false;
    }
  } catch (error) {
    if (thisRequest === latestTypesRequest) {
      // O campo continua utilizável. Na criação, só com "Sem tipo"; na edição, com o tipo da
      // tarefa ainda escolhido, e o aviso diz isso.
      console.error(error);
      if (currentTypeId === null) {
        formTypesError.hidden = false;
      } else {
        formTypesKept.hidden = false;
      }
      formType.disabled = false;
    }
  }
}

// Um <option> por tipo, na ordem da API, depois do "Sem tipo". O nome entra por textContent
// (seção 6.7). Um <option> não tem estrutura, então não usa <template> (decisão da etapa 11.3).
// Depois, o campo volta ao tipo da tarefa.
function showTaskTypes(types, currentTypeId) {
  formType.replaceChildren(formNoTypeOption);
  for (const type of types) {
    const option = document.createElement("option");
    option.value = type.id;
    option.textContent = type.name;
    formType.append(option);
  }
  formType.value = currentTypeId === null ? "" : String(currentTypeId);
  // Dar a um <select> um value sem opção igual deixa nenhuma opção escolhida (selectedIndex -1).
  // Isso quer dizer que o tipo da tarefa foi excluído depois de a lista do dia ser desenhada.
  // Excluir um tipo já deixa as tarefas dele sem tipo no banco, então "Sem tipo" é o que a
  // tarefa já tem.
  if (formType.selectedIndex === -1) {
    formType.value = "";
    formTypeGone.hidden = false;
  }
}

// ---------------------------------------------------------------------------------------------
// 3. Erros
// ---------------------------------------------------------------------------------------------

// Frases que a tela acrescenta pelo código da resposta, sem ler o texto do servidor. Só a edição
// recebe 409 e 404: em todos esses casos, a tarefa mudou em outro lugar desde que o formulário
// abriu, e só abrir de novo mostra como ela está.
const CHANGED_TASK_TEXT =
  "A lista já foi atualizada: cancele e abra a tarefa de novo para ver como ela está agora.";
const DELETED_TASK_TEXT = "Ela foi excluída em outro lugar.";

// A frase de um erro da validação automática, com o rótulo do campo que deu o erro. Os números
// vêm do servidor (ctx.max_length), nunca daqui.
function fieldErrorText(field, item) {
  const label = field.labels[0].textContent;
  if (item.type === "string_too_short") {
    return label + ": não pode ficar vazio.";
  }
  if (item.type === "string_too_long") {
    return label + ": no máximo " + numberFormat.format(item.ctx.max_length) + " caracteres.";
  }
  return label + ": está inválida.";
}

// Mostra o erro ao salvar dentro do formulário, que continua aberto e preenchido. O "detail"
// pode ser um texto (as recusas das rotas, já em português), que aparece como veio, ou uma
// lista (a validação automática, em inglês), que vira uma frase por item. Cada item traz em
// loc o caminho do campo, como ["body", "title"]: o name do campo no HTML é o mesmo da API.
function showFormErrors(error) {
  const texts = [];
  let unknown = false;

  if (typeof error.detail === "string") {
    texts.push(error.detail);
  } else if (Array.isArray(error.detail)) {
    for (const item of error.detail) {
      const field = taskForm.elements.namedItem(item.loc[1]);
      if (field === null) {
        unknown = true;
      } else {
        field.setAttribute("aria-invalid", "true");
        texts.push(fieldErrorText(field, item));
      }
    }
  }

  // 409: tela desatualizada, concluída ou travada em outro lugar. 404: excluída.
  if (error.status === 409) {
    texts.push(CHANGED_TASK_TEXT);
  } else if (error.status === 404) {
    texts.push(DELETED_TASK_TEXT);
  }

  // Sem nada legível (rede caída, erro 500, campo que não está no formulário): a mensagem
  // genérica, e o erro completo no console.
  if (unknown || texts.length === 0) {
    console.error(error);
    texts.push(SAVE_ERROR_TEXT);
  }

  formError.textContent = texts.join(" ");
  formError.hidden = false;

  // O foco vai para o primeiro campo marcado, na ordem do formulário (querySelector acha o
  // primeiro na ordem do HTML). Sem campo marcado, volta ao "Salvar", que perdeu o foco quando
  // foi bloqueado.
  const firstInvalid = taskForm.querySelector('[aria-invalid="true"]');
  if (firstInvalid !== null) {
    firstInvalid.focus();
  } else {
    formSave.focus();
  }
}

function clearFormErrors() {
  for (const field of taskForm.querySelectorAll("[aria-invalid]")) {
    field.removeAttribute("aria-invalid");
  }
  formError.textContent = "";
  formError.hidden = true;
}

// ---------------------------------------------------------------------------------------------
// 4. Data nova: confirmação
// ---------------------------------------------------------------------------------------------

// Na edição, mudar a data para depois conta como adiamento e tira 25% do XP (seção 4.2), como o
// Adiar, que pede confirmação. A tela não sabe se a data nova é depois ou antes da marcada (isso
// seria conta de data), então pede confirmação sempre que a data mudou. Os textos são fixos.
const SAVE_LABEL = "Salvar";
const CONFIRM_DATE_LABEL = "Confirmar nova data";

// Verdadeiro enquanto o "Salvar" pede a confirmação da data nova.
let dateConfirming = false;
// Falso no primeiro meio segundo da confirmação: o segundo toque de um toque duplo não vale.
let dateConfirmReady = false;
// O número que o setTimeout devolve, para o clearTimeout desistir dele.
let dateReadyTimer = null;

// Se a data do campo é outra que não a que o formulário mostrou ao abrir. É uma comparação de
// igualdade entre dois textos AAAA-MM-DD, não uma conta de data. Na criação não há o que
// confirmar. Com o campo vazio também não: o servidor recusa com 422, como na criação.
function dateChanged() {
  return editingTask !== null && formDueDate.value !== "" && formDueDate.value !== editingTask.due_date;
}

// Primeiro toque no "Salvar" com a data mudada: não grava, troca o texto do botão e mostra o
// aviso, com role="alert" para o leitor de tela. DOUBLE_TAP_GUARD_MS vem do day.js (seção 5 dele).
function startDateConfirmation() {
  dateConfirming = true;
  dateConfirmReady = false;
  formSave.textContent = CONFIRM_DATE_LABEL;
  formSave.classList.add("is-confirming");
  formConfirm.hidden = false;
  dateReadyTimer = setTimeout(function () {
    dateConfirmReady = true;
  }, DOUBLE_TAP_GUARD_MS);
}

// Volta o "Salvar" ao normal. Chamada ao abrir o formulário, ao mexer na data e ao gravar. Não
// volta sozinha com o tempo, como o Adiar: o formulário fica por cima de tudo, e o aviso continua
// escrito nele.
function cancelDateConfirmation() {
  clearTimeout(dateReadyTimer);
  dateConfirming = false;
  dateConfirmReady = false;
  formSave.textContent = SAVE_LABEL;
  formSave.classList.remove("is-confirming");
  formConfirm.hidden = true;
}

formDueDate.addEventListener("input", cancelDateConfirmation);

// ---------------------------------------------------------------------------------------------
// 5. Salvar
// ---------------------------------------------------------------------------------------------

// O corpo do pedido, com os campos como estão: cortar espaços e conferir tamanhos é do servidor.
// O tipo vai como número, ou null para "Sem tipo". O corpo lê o value de cada campo direto,
// então um campo bloqueado também vai (um envio comum de <form> o deixaria de fora). task é a
// tarefa editada, ou null ao criar.
function taskBody(task) {
  const body = {
    title: formTitle.value,
    due_date: formDueDate.value,
    difficulty: formDifficulty.value,
    task_type_id: formType.value === "" ? null : Number(formType.value),
    notes: formNotes.value,
  };
  if (task !== null) {
    // A edição exige todos os campos e manda sempre a cor do campo. "Cor padrão" deixa nele a
    // cor do HTML, que é a do servidor.
    body.color = formColor.value;
    // A data que o formulário mostrou ao abrir, vinda da lista, e nunca a do campo: o campo é a
    // data que se quer; esta é a data que se viu. O servidor compara as duas para saber se a
    // data mudou e só grava se a tarefa ainda tiver a data vista.
    body.shown_due_date = task.due_date;
  } else if (colorChosen) {
    // Ao criar, a cor só vai se foi escolhida.
    body.color = formColor.value;
  }
  return body;
}

// Grava a tarefa: POST ao criar, PUT ao editar. Criar não é idempotente: dois pedidos criariam
// duas tarefas. O JavaScript faz uma coisa por vez, e esta função roda sem pausa até o await do
// fetch. Nesse trecho, saving vira true e o "Salvar" fica bloqueado, antes de o navegador
// atender um segundo toque: ele cai num botão bloqueado, que não envia o formulário (o Enter
// também não). Se algo ainda chamasse esta função, o "if (saving)" pararia.
async function saveTask() {
  if (saving) {
    return;
  }
  // A tarefa desta gravação, guardada numa constante: ela continua a mesma até o fim, aconteça o
  // que acontecer com editingTask.
  const task = editingTask;
  saving = true;
  formSave.disabled = true;
  formCancel.disabled = true;
  formDelete.disabled = true;
  cancelDateConfirmation();
  disableTaskControls();
  hideMessages();
  clearFormErrors();

  let saved = null;
  let failure = null;
  try {
    saved = await apiRequest(task === null ? "tasks" : "tasks/" + task.id, {
      method: task === null ? "POST" : "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(taskBody(task)),
    });
  } catch (error) {
    failure = error;
  }

  saving = false;
  formSave.disabled = false;
  formCancel.disabled = false;
  formDelete.disabled = false;

  if (failure !== null) {
    if (taskFormDialog.open) {
      showFormErrors(failure);
    } else {
      // O Chrome fechou o formulário durante a gravação (dois Esc seguidos): o erro vai para o
      // topo, como nas outras gravações.
      console.error(failure);
      showSaveMessage(SAVE_ERROR_TEXT);
    }
    // A lista de trás é desenhada de novo: libera as caixinhas e os botões que
    // disableTaskControls bloqueou e, depois de um 409 ou de um 404, mostra a tarefa como ela
    // está agora. O formulário não muda.
    loadDay();
    return;
  }

  taskFormDialog.close();
  await loadDay();
  if (task === null) {
    showCreatedNotice(saved);
    newTaskButton.focus();
  } else {
    showEditedNotice(task, saved);
    focusEditedTask(task.id);
  }
}

// Depois de criar e de recarregar: se a tarefa não está na lista desenhada (nasceu em outro
// dia), o aviso diz para onde ela foi, com a data e o título da resposta do servidor, só
// formatados. A tela não prevê: olha o resultado. Sem lista (erro), não avisa: o aviso de erro
// já está na tela.
function showCreatedNotice(task) {
  if (shownDay === null || document.getElementById("task-card-" + task.id) !== null) {
    return;
  }
  showNotice("Criada para " + formatDueDate(task.due_date) + ": " + task.title);
}

// Depois de editar e de recarregar: se a data mudou, o aviso diz para onde a tarefa foi e se o
// servidor contou um adiamento, mesmo que ela continue na tela. before é a tarefa como veio da
// lista, e saved, a resposta do servidor. As duas comparações são de igualdade entre valores do
// servidor: a data, e o contador de adiamentos, que nunca diminui. Se ele mudou, a data foi para
// depois. O "−25% XP" é texto fixo, como no Adiar.
function showEditedNotice(before, saved) {
  if (saved.due_date === before.due_date) {
    return;
  }
  if (saved.postponements !== before.postponements) {
    showNotice("Adiada para " + formatDueDate(saved.due_date) + " (−25% XP): " + saved.title);
  } else {
    showNotice("Data mudada para " + formatDueDate(saved.due_date) + ": " + saved.title);
  }
}

// O <form> existe para o Enter salvar. preventDefault() cancela o envio do navegador, e a
// gravação vai por fetch (seção 6.7). Com a data mudada, o primeiro envio só pede confirmação
// (seção 4), e o segundo, no primeiro meio segundo, é ignorado.
taskForm.addEventListener("submit", function (event) {
  event.preventDefault();
  if (dateChanged()) {
    if (!dateConfirming) {
      startDateConfirmation();
      return;
    }
    if (!dateConfirmReady) {
      return;
    }
  }
  saveTask();
});

// ---------------------------------------------------------------------------------------------
// 6. Excluir
// ---------------------------------------------------------------------------------------------

// Os textos fixos. Excluir nunca muda o XP (seção 4.3): o texto sobre isso fica no HTML, sempre à
// vista acima do botão, e o topo não é recarregado depois de excluir.
const CONFIRM_DELETE_LABEL = "Confirmar exclusão";
const DELETE_ERROR_TEXT = "Não foi possível excluir. Tente de novo.";

// Primeiro toque: arma a confirmação, com o mecanismo do Adiar (seção 5 do day.js): volta sozinha
// em 5 segundos ou num toque em qualquer outra coisa, e o segundo toque de um toque duplo não
// vale. A confirmação da data nova é desfeita antes, para não ficarem dois botões pedindo
// confirmação ao mesmo tempo. Segundo toque, depois do meio segundo: exclui.
formDelete.addEventListener("click", function () {
  cancelDateConfirmation();
  handleConfirmClick(formDelete, CONFIRM_DELETE_LABEL, deleteTask);
});

// Mexer num campo (também pelo teclado, sem clique) desfaz a confirmação do Excluir: quem voltou a
// editar desistiu de excluir. O evento "input" de cada campo sobe até o <form>.
taskForm.addEventListener("input", function () {
  cancelConfirmation();
});

// Exclui a tarefa do formulário. Segue o molde do saveTask: uma gravação por vez, tudo bloqueado
// antes do await, sem pausa. O DELETE não leva corpo: o que foi mudado no formulário e não foi
// salvo some junto com a tarefa. O apiRequest devolve null no 204, e aqui só importa se deu erro.
async function deleteTask() {
  if (saving) {
    return;
  }
  // A tarefa como veio da lista, guardada numa constante até o fim.
  const task = editingTask;
  saving = true;
  formSave.disabled = true;
  formCancel.disabled = true;
  formDelete.disabled = true;
  cancelConfirmation();
  cancelDateConfirmation();
  disableTaskControls();
  hideMessages();
  clearFormErrors();

  let failure = null;
  try {
    await apiRequest("tasks/" + task.id, { method: "DELETE" });
  } catch (error) {
    failure = error;
  }

  saving = false;
  formSave.disabled = false;
  formCancel.disabled = false;
  formDelete.disabled = false;

  // 404: a tarefa já tinha sido excluída em outro lugar. O que a pessoa queria já aconteceu, então
  // segue como o sucesso, com outro aviso. Qualquer outro erro (rede caída, erro 500) não excluiu.
  if (failure !== null && failure.status !== 404) {
    console.error(failure);
    if (taskFormDialog.open) {
      // O formulário continua aberto, com o que foi digitado. O "Excluir" perdeu o foco quando
      // foi bloqueado, e o recebe de volta para tentar de novo.
      formError.textContent = DELETE_ERROR_TEXT;
      formError.hidden = false;
      formDelete.focus();
    } else {
      // O Chrome fechou o formulário durante a gravação (dois Esc seguidos): o erro vai para o topo.
      showSaveMessage(DELETE_ERROR_TEXT);
    }
    // A lista de trás é desenhada de novo, para liberar o que disableTaskControls bloqueou.
    loadDay();
    return;
  }

  taskFormDialog.close();
  await loadDay();
  // O título é o da lista (task.title), e não o do campo: um título digitado e não salvo nunca
  // chegou ao banco. O aviso aparece sempre, porque a tarefa sempre sai da tela.
  if (failure === null) {
    showNotice("Excluída: " + task.title);
  } else {
    showNotice("Já tinha sido excluída em outro lugar: " + task.title);
  }
  focusAfterDelete();
}

// O foco vai para o "Nova tarefa", que nunca é desenhado de novo. Se a lista não carregou, ele
// está escondido e não recebe foco; então vai para o "Tentar de novo", que está na tela.
function focusAfterDelete() {
  if (shownDay === null) {
    document.getElementById("day-retry").focus();
  } else {
    newTaskButton.focus();
  }
}
