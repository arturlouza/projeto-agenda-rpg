// task-form.js: o formulário de tarefa nova. Abre o <dialog>, busca os tipos, grava pelo
// POST /tasks e mostra os erros 422 em português. Carrega depois do day.js. Ao carregar, só usa
// o HTML e os nomes deste arquivo; saving, shownDay, loadDay, showNotice e companhia, dos
// arquivos anteriores, só são usados depois de um toque.

// ---------------------------------------------------------------------------------------------
// 1. Abrir e fechar
// ---------------------------------------------------------------------------------------------

// Partes da página usadas por várias funções. Com o defer, o HTML já está pronto aqui.
const newTaskButton = document.getElementById("new-task");
const taskFormDialog = document.getElementById("task-form-dialog");
const taskForm = document.getElementById("task-form");
const formTitle = document.getElementById("task-form-title");
const formDueDate = document.getElementById("task-form-due-date");
const formDifficulty = document.getElementById("task-form-difficulty");
const formColor = document.getElementById("task-form-color");
const formDefaultColor = document.getElementById("task-form-default-color");
const formType = document.getElementById("task-form-type");
const formTypesError = document.getElementById("task-form-types-error");
const formNotes = document.getElementById("task-form-notes");
const formError = document.getElementById("task-form-error");
const formCancel = document.getElementById("task-form-cancel");
const formSave = document.getElementById("task-form-save");
// O "Sem tipo" escrito no HTML. Fica guardado para a lista de tipos sempre começar por ele.
const formNoTypeOption = formType.options[0];

// Falso enquanto a cor não for escolhida. Assim o pedido não leva a cor, e o servidor aplica a
// cor padrão dele (DEFAULT_TASK_COLOR): o JavaScript não tem a cor escrita em lugar nenhum.
let colorChosen = false;

// Abre o formulário vazio. reset() volta cada campo ao que está escrito no HTML (Fácil, cor
// padrão, textos vazios). A data sugerida vem pronta do servidor (new_task_due_date): o dia da
// tela ou, se ele já passou, hoje. A tela não compara datas. O botão só aparece com um dia na
// tela, então shownDay nunca é null aqui. O foco vai para o Título, pelo autofocus do HTML.
function openTaskForm() {
  taskForm.reset();
  colorChosen = false;
  clearFormErrors();
  formDueDate.value = shownDay.new_task_due_date;
  loadTaskTypes();
  taskFormDialog.showModal();
}

newTaskButton.addEventListener("click", openTaskForm);

// Fecha sem gravar. O Chrome devolve o foco ao "Nova tarefa" sozinho.
formCancel.addEventListener("click", function () {
  taskFormDialog.close();
});

// O Esc e o gesto de voltar do Android disparam "cancel" antes de fechar. Durante a gravação,
// o formulário não fecha, para um erro poder aparecer nele com o que foi digitado. O Chrome só
// deixa bloquear uma vez por toque: um segundo Esc seguido fecha de qualquer jeito, e o erro,
// se houver, vai para o topo (seção 4).
taskFormDialog.addEventListener("cancel", function (event) {
  if (saving) {
    event.preventDefault();
  }
});

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

// Número do pedido mais recente dos tipos. Abrir, fechar e abrir rápido não mistura listas.
let latestTypesRequest = 0;

// Busca os tipos a cada abertura, para a lista nunca ficar velha. Enquanto o pedido não chega,
// o campo fica bloqueado em "Sem tipo"; o resto do formulário já funciona. Se der erro, o
// formulário continua utilizável, só com "Sem tipo", e o aviso embaixo do campo explica.
async function loadTaskTypes() {
  latestTypesRequest = latestTypesRequest + 1;
  const thisRequest = latestTypesRequest;
  formType.replaceChildren(formNoTypeOption);
  formType.disabled = true;
  formTypesError.hidden = true;
  try {
    const types = await apiRequest("task-types");
    if (thisRequest === latestTypesRequest) {
      showTaskTypes(types);
      formType.disabled = false;
    }
  } catch (error) {
    if (thisRequest === latestTypesRequest) {
      console.error(error);
      formTypesError.hidden = false;
      formType.disabled = false;
    }
  }
}

// Um <option> por tipo, na ordem da API, depois do "Sem tipo". O nome entra por textContent
// (seção 6.7). Um <option> não tem estrutura, então não usa <template> (decisão da etapa 11.3).
function showTaskTypes(types) {
  for (const type of types) {
    const option = document.createElement("option");
    option.value = type.id;
    option.textContent = type.name;
    formType.append(option);
  }
}

// ---------------------------------------------------------------------------------------------
// 3. Erros
// ---------------------------------------------------------------------------------------------

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
// 4. Salvar
// ---------------------------------------------------------------------------------------------

// O corpo do POST /tasks, com os campos como estão: cortar espaços e conferir tamanhos é do
// servidor. O tipo vai como número, ou null para "Sem tipo". A cor só vai se foi escolhida.
function newTaskBody() {
  const body = {
    title: formTitle.value,
    due_date: formDueDate.value,
    difficulty: formDifficulty.value,
    task_type_id: formType.value === "" ? null : Number(formType.value),
    notes: formNotes.value,
  };
  if (colorChosen) {
    body.color = formColor.value;
  }
  return body;
}

// Criar não é idempotente: dois pedidos criariam duas tarefas. O JavaScript faz uma coisa por
// vez, e esta função roda sem pausa até o await do fetch. Nesse trecho, saving vira true e o
// "Salvar" fica bloqueado, antes de o navegador atender um segundo toque: ele cai num botão
// bloqueado, que não envia o formulário (o Enter também não). Se algo ainda chamasse esta
// função, o "if (saving)" pararia.
async function saveNewTask() {
  if (saving) {
    return;
  }
  saving = true;
  formSave.disabled = true;
  formCancel.disabled = true;
  disableTaskControls();
  hideMessages();
  clearFormErrors();

  let created = null;
  let failure = null;
  try {
    created = await apiRequest("tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newTaskBody()),
    });
  } catch (error) {
    failure = error;
  }

  saving = false;
  formSave.disabled = false;
  formCancel.disabled = false;

  if (failure !== null) {
    if (taskFormDialog.open) {
      showFormErrors(failure);
    } else {
      // O Chrome fechou o formulário durante a gravação (dois Esc seguidos): o erro vai para o
      // topo, como nas outras gravações.
      console.error(failure);
      showSaveMessage(SAVE_ERROR_TEXT);
    }
    // A lista de trás é desenhada de novo para liberar as caixinhas e os Adiar que
    // disableTaskControls bloqueou. O formulário não muda.
    loadDay();
    return;
  }

  taskFormDialog.close();
  await loadDay();
  showCreatedNotice(created);
  newTaskButton.focus();
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

// O <form> existe para o Enter salvar. preventDefault() cancela o envio do navegador, e a
// gravação vai por fetch (seção 6.7).
taskForm.addEventListener("submit", function (event) {
  event.preventDefault();
  saveNewTask();
});
