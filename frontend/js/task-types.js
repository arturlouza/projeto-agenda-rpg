// task-types.js: a tela de tipos. Lista os tipos com quantas tarefas usam cada um, renomeia pelo
// PATCH /task-types/{id} e exclui pelo DELETE /task-types/{id}, com confirmação em dois toques.
// Abre só a partir da tela principal, nunca de dentro do formulário de tarefa. Carrega depois do
// task-form.js. Ao carregar, só usa o HTML e os nomes deste arquivo; saving, loadDay,
// handleConfirmClick, fieldErrorText, showNotice e companhia, dos arquivos anteriores, só são
// usados depois de um toque.

// ---------------------------------------------------------------------------------------------
// 1. Abrir e fechar
// ---------------------------------------------------------------------------------------------

// Partes da página usadas por várias funções. Com o defer, o HTML já está pronto aqui.
const openTypesButton = document.getElementById("open-task-types");
const typesDialog = document.getElementById("task-types-dialog");
const typesClose = document.getElementById("task-types-close");
const typesNotice = document.getElementById("task-types-notice");
const typesStatus = document.getElementById("task-types-status");
const typesError = document.getElementById("task-types-error");
const typesRetry = document.getElementById("task-types-retry");
const typesEmpty = document.getElementById("task-types-empty");
const typesList = document.getElementById("task-types-list");
const typeRowTemplate = document.getElementById("task-type-row-template");

// Abre a tela e busca os tipos. Uma gravação por vez: enquanto outra gravação espera a resposta,
// a tela não abre, como o formulário de tarefa (decisão da etapa 11.4). showModal() deixa o resto
// da página sem toque e põe o foco no primeiro botão da tela, o "Fechar".
function openTypesScreen() {
  if (saving) {
    return;
  }
  editingTypeId = null;
  hideTypesNotice();
  loadTypeList();
  typesDialog.showModal();
}

openTypesButton.addEventListener("click", openTypesScreen);

typesClose.addEventListener("click", function () {
  typesDialog.close();
});

// O Esc e o gesto de voltar do Android disparam "cancel" antes de fechar. Durante a gravação, a
// tela não fecha, para o resultado aparecer nela. O Chrome só deixa bloquear uma vez por toque:
// dois Esc seguidos fecham, e o resultado vai para o topo (seções 4 e 5).
typesDialog.addEventListener("cancel", function (event) {
  if (saving) {
    event.preventDefault();
  }
});

// Ao fechar, o navegador devolve o foco ao "Tipos de tarefa", que nunca é desenhado de novo. A
// confirmação do Excluir, se houver, vale só para esta abertura.
typesDialog.addEventListener("close", function () {
  cancelConfirmation();
});

// O resultado da última gravação, dentro da tela, porque o topo fica atrás do fundo escuro.
function showTypesNotice(text) {
  typesNotice.textContent = text;
  typesNotice.hidden = false;
}

function hideTypesNotice() {
  typesNotice.textContent = "";
  typesNotice.hidden = true;
}

// ---------------------------------------------------------------------------------------------
// 2. Lista: buscar e desenhar
// ---------------------------------------------------------------------------------------------

// Os tipos como vieram da API, na ordem dela, ou null enquanto a lista não chegou ou deu erro.
// Renomear e excluir atualizam esta lista com a resposta do servidor, sem pedir a lista de novo
// (seção 4).
let shownTypes = null;

// Número do pedido mais recente da lista. Fechar e abrir rápido não mistura listas.
let latestTypeListRequest = 0;

// Busca os tipos. Só ao abrir a tela e no "Tentar de novo": nunca há uma linha em edição nesse
// momento, então nada do que foi digitado se perde quando a lista chega.
async function loadTypeList() {
  latestTypeListRequest = latestTypeListRequest + 1;
  const thisRequest = latestTypeListRequest;
  shownTypes = null;
  typesList.replaceChildren();
  typesEmpty.hidden = true;
  typesError.hidden = true;
  typesStatus.hidden = false;
  try {
    const types = await apiRequest("task-types");
    if (thisRequest === latestTypeListRequest) {
      shownTypes = types;
      showTypeList();
    }
  } catch (error) {
    if (thisRequest === latestTypeListRequest) {
      console.error(error);
      typesStatus.hidden = true;
      typesError.hidden = false;
      typesRetry.focus();
    }
  }
}

typesRetry.addEventListener("click", loadTypeList);

// Desenha a lista a partir de shownTypes e de editingTypeId (seção 3). Os botões antigos vão ser
// trocados por novos: a confirmação em dois toques, se houver, acaba aqui.
function showTypeList() {
  cancelConfirmation();
  typesStatus.hidden = true;
  typesError.hidden = true;
  typesList.replaceChildren();
  for (const type of shownTypes) {
    typesList.append(createTypeRow(type));
  }
  typesEmpty.hidden = shownTypes.length > 0;
}

// "Nenhuma tarefa", "1 tarefa" ou "3 tarefas". O número vem pronto do servidor (task_count); a
// tela só formata e escolhe o singular ou o plural.
function taskCountText(count) {
  if (count === 0) {
    return "Nenhuma tarefa";
  }
  if (count === 1) {
    return "1 tarefa";
  }
  return numberFormat.format(count) + " tarefas";
}

// O mesmo número, escrito acima do Excluir.
function deleteCountText(count) {
  if (count === 0) {
    return "Nenhuma tarefa usa este tipo.";
  }
  if (count === 1) {
    return "1 tarefa vai ficar sem tipo.";
  }
  return numberFormat.format(count) + " tarefas vão ficar sem tipo.";
}

// Cria a linha de um tipo a partir do modelo do index.html. O nome entra por textContent e, no
// campo, por value (seção 6.7), então um nome como <img src=x> aparece como texto. A linha em
// edição mostra o campo e o Excluir no lugar do nome e do "Editar".
function createTypeRow(type) {
  const row = typeRowTemplate.content.firstElementChild.cloneNode(true);
  // Os ids servem só para achar a linha e o campo depois: foco e rótulo. Nada depende de o id
  // ser sequencial.
  row.id = "task-type-" + type.id;
  row.querySelector(".type-name").textContent = type.name;
  row.querySelector(".type-count").textContent = taskCountText(type.task_count);
  // O texto escondido da vista dá ao "Editar" o nome do tipo, para o leitor de tela.
  row.querySelector(".type-edit-name").textContent = type.name;
  row.querySelector(".type-edit").addEventListener("click", function () {
    startTypeEdit(type.id);
  });

  const editing = type.id === editingTypeId;
  row.querySelector(".type-view").hidden = editing;
  row.querySelector(".type-editor").hidden = !editing;

  // O rótulo aponta para o campo pelo id. fieldErrorText (task-form.js) usa o texto dele nos erros.
  const input = row.querySelector(".type-name-input");
  input.id = "task-type-name-" + type.id;
  row.querySelector(".type-name-label").htmlFor = input.id;
  input.value = type.name;
  row.querySelector(".type-delete-count").textContent = deleteCountText(type.task_count);

  // O Enter no campo envia este <form>, que fica fora do formulário de tarefa: renomeia o tipo e
  // nunca salva uma tarefa. preventDefault() cancela o envio do navegador, e a gravação vai por
  // fetch (seção 6.7).
  const form = row.querySelector(".type-rename-form");
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    renameType(type, row);
  });
  // Digitar no nome desfaz a confirmação do Excluir: quem voltou a editar desistiu de excluir.
  form.addEventListener("input", function () {
    cancelConfirmation();
  });
  row.querySelector(".type-rename-cancel").addEventListener("click", stopTypeEdit);

  // O Excluir pede confirmação com o mecanismo do Adiar (seção 5 do day.js) e o mesmo texto do
  // Excluir de tarefa. A função entregue só roda no segundo toque.
  const deleteButton = row.querySelector(".type-delete");
  deleteButton.addEventListener("click", function () {
    handleConfirmClick(deleteButton, CONFIRM_DELETE_LABEL, function () {
      deleteType(type, row);
    });
  });

  return row;
}

// ---------------------------------------------------------------------------------------------
// 3. Editar uma linha
// ---------------------------------------------------------------------------------------------

// O id do tipo da linha em edição, ou null. Uma linha por vez: abrir uma fecha a outra, como o
// cartão da tarefa. Quando a lista é desenhada, createTypeRow lê esta variável.
let editingTypeId = null;

// Abre a edição do tipo e põe o foco no campo do nome.
function startTypeEdit(typeId) {
  editingTypeId = typeId;
  hideTypesNotice();
  showTypeList();
  document.getElementById("task-type-name-" + typeId).focus();
}

// Fecha a edição sem gravar, e o foco volta ao "Editar" da linha.
function stopTypeEdit() {
  const typeId = editingTypeId;
  editingTypeId = null;
  showTypeList();
  focusTypeEdit(typeId);
}

// O foco vai para o "Editar" do tipo ou, se ele saiu da lista, para o "Fechar", que sempre existe.
function focusTypeEdit(typeId) {
  const row = document.getElementById("task-type-" + typeId);
  if (row === null) {
    typesClose.focus();
    return;
  }
  row.querySelector(".type-edit").focus();
}

// Bloqueia ou libera a tela durante uma gravação: o "Fechar" e todos os botões da lista. O campo
// do nome fica readOnly, e não disabled: não aceita digitação, mas continua com o foco (e o
// teclado do celular aberto).
function setTypesBusy(busy) {
  typesClose.disabled = busy;
  for (const button of typesList.querySelectorAll("button")) {
    button.disabled = busy;
  }
  for (const input of typesList.querySelectorAll(".type-name-input")) {
    input.readOnly = busy;
  }
}

// Apaga os erros da linha: o texto e a borda vermelha do campo.
function clearTypeErrors(row) {
  row.querySelector(".type-name-input").removeAttribute("aria-invalid");
  for (const message of row.querySelectorAll(".type-rename-error, .type-delete-error")) {
    message.textContent = "";
    message.hidden = true;
  }
}

// Tira o tipo da lista desenhada: ele foi excluído, aqui ou em outro lugar.
function removeShownType(typeId) {
  shownTypes = shownTypes.filter(function (type) {
    return type.id !== typeId;
  });
}

// ---------------------------------------------------------------------------------------------
// 4. Renomear
// ---------------------------------------------------------------------------------------------

// O texto quando o erro ao renomear não é legível (rede caída, erro 500).
const TYPE_RENAME_ERROR_TEXT = "Não foi possível renomear o tipo. Tente de novo.";

// Mostra o erro embaixo do campo do nome. O que foi digitado fica, e o foco volta ao campo. O
// "detail" é um texto (o 409, já em português, com o nome do tipo que já existe) ou uma lista (a
// validação automática), que vira uma frase com o rótulo "Nome do tipo" e, no nome longo, com o
// número que veio do servidor (ctx.max_length), nunca daqui.
function showRenameError(row, error) {
  const input = row.querySelector(".type-name-input");
  const texts = [];
  let unknown = false;

  if (typeof error.detail === "string") {
    texts.push(error.detail);
  } else if (Array.isArray(error.detail)) {
    for (const item of error.detail) {
      if (item.loc[1] === "name") {
        texts.push(fieldErrorText(input, item));
      } else {
        unknown = true;
      }
    }
  }

  // Sem nada legível: a mensagem genérica, e o erro completo no console. Com um erro sobre o
  // nome, o campo fica com a borda vermelha.
  if (unknown || texts.length === 0) {
    console.error(error);
    texts.push(TYPE_RENAME_ERROR_TEXT);
  } else {
    input.setAttribute("aria-invalid", "true");
  }

  const message = row.querySelector(".type-rename-error");
  message.textContent = texts.join(" ");
  message.hidden = false;
  input.focus();
}

// Renomeia o tipo pelo PATCH. Segue o molde do createTaskType (task-form.js): uma gravação por
// vez, tudo bloqueado antes do await, sem pausa. Um segundo toque cai no "Salvar nome" já
// bloqueado, e um segundo Enter não envia o <form> com o botão de envio bloqueado.
async function renameType(type, row) {
  if (saving) {
    return;
  }
  const input = row.querySelector(".type-name-input");
  // O texto não mudou: não manda nada, porque nada mudaria no servidor. É uma comparação de
  // igualdade entre dois textos, sem cortar espaços (isso é regra do servidor). Assim, num par de
  // tipos antigos com o mesmo nome (etapa 11.6a), salvar sem mudar não recebe o 409.
  if (input.value === type.name) {
    stopTypeEdit();
    return;
  }
  saving = true;
  setTypesBusy(true);
  cancelConfirmation();
  disableTaskControls();
  hideMessages();
  hideTypesNotice();
  clearTypeErrors(row);

  let saved = null;
  let failure = null;
  try {
    // O nome vai como está: cortar os espaços e conferir o tamanho é do servidor.
    saved = await apiRequest("task-types/" + type.id, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: input.value }),
    });
  } catch (error) {
    failure = error;
  }

  saving = false;
  setTypesBusy(false);
  // A lista do dia é desenhada de novo, para liberar o que disableTaskControls bloqueou.
  loadDay();

  if (!typesDialog.open) {
    // O Chrome fechou a tela durante a gravação (dois Esc seguidos). A pessoa não viu o resultado,
    // então ele vai para o topo.
    if (failure !== null) {
      console.error(failure);
      showSaveMessage(TYPE_RENAME_ERROR_TEXT);
    } else {
      showNotice("Tipo renomeado: " + saved.name);
    }
    return;
  }

  // 404: o tipo foi excluído em outro lugar. Não adianta manter o que foi digitado: ele sai da
  // lista, com o nome que estava na tela.
  if (failure !== null && failure.status === 404) {
    removeShownType(type.id);
    editingTypeId = null;
    showTypeList();
    showTypesNotice("Esse tipo já tinha sido excluído em outro lugar: " + type.name);
    typesClose.focus();
    return;
  }

  if (failure !== null) {
    showRenameError(row, failure);
    return;
  }

  // O nome novo é o da resposta do servidor, já sem os espaços das pontas. A ordem da lista não
  // muda ao renomear (ela vem da criação), e a contagem continua a mesma.
  type.name = saved.name;
  editingTypeId = null;
  showTypeList();
  showTypesNotice("Tipo renomeado: " + saved.name);
  focusTypeEdit(type.id);
}

// ---------------------------------------------------------------------------------------------
// 5. Excluir
// ---------------------------------------------------------------------------------------------

const TYPE_DELETE_ERROR_TEXT = "Não foi possível excluir o tipo. Tente de novo.";

// Exclui o tipo pelo DELETE, no segundo toque. Segue o molde de renameType. O servidor deixa as
// tarefas do tipo sem tipo e não apaga nenhuma. O apiRequest devolve null no 204, e aqui só
// importa se deu erro.
async function deleteType(type, row) {
  if (saving) {
    return;
  }
  saving = true;
  setTypesBusy(true);
  cancelConfirmation();
  disableTaskControls();
  hideMessages();
  hideTypesNotice();
  clearTypeErrors(row);

  let failure = null;
  try {
    await apiRequest("task-types/" + type.id, { method: "DELETE" });
  } catch (error) {
    failure = error;
  }

  saving = false;
  setTypesBusy(false);
  // Obrigatório aqui: a lista do dia volta com as tarefas deste tipo sem tipo, então o Editar
  // delas abre em "Sem tipo". Também libera o que disableTaskControls bloqueou.
  loadDay();

  // 404: o tipo já tinha sido excluído em outro lugar. O que a pessoa queria já aconteceu, então
  // segue como o sucesso, com outro aviso. Qualquer outro erro (rede caída, erro 500) não excluiu.
  const gone = failure === null || failure.status === 404;
  const goneText =
    failure === null
      ? "Tipo excluído: " + type.name + ". Nenhuma tarefa foi apagada."
      : "Já tinha sido excluído em outro lugar: " + type.name;

  if (!typesDialog.open) {
    // O Chrome fechou a tela durante a gravação (dois Esc seguidos): o resultado vai para o topo.
    if (gone) {
      showNotice(goneText);
    } else {
      console.error(failure);
      showSaveMessage(TYPE_DELETE_ERROR_TEXT);
    }
    return;
  }

  if (!gone) {
    // A edição continua aberta, com o que foi digitado no nome. O "Excluir" já voltou ao texto
    // normal (cancelConfirmation, acima) e recebe o foco para tentar de novo.
    console.error(failure);
    const message = row.querySelector(".type-delete-error");
    message.textContent = TYPE_DELETE_ERROR_TEXT;
    message.hidden = false;
    row.querySelector(".type-delete").focus();
    return;
  }

  removeShownType(type.id);
  editingTypeId = null;
  showTypeList();
  showTypesNotice(goneText);
  typesClose.focus();
}
