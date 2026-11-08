// top-bar.js: o topo fixo. Mostra o nível, o XP e a barra, e escreve a linha de erro ao salvar
// e o aviso de que a tarefa saiu da tela. Carrega depois do api.js.

// ---------------------------------------------------------------------------------------------
// 1. Topo: nível, XP e barra
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
// 2. Topo: erro ao salvar e aviso
// ---------------------------------------------------------------------------------------------

// A linha de erro do topo. O texto muda: erro ao salvar ou a última data possível (seção 5 do day.js).
function showSaveMessage(text) {
  const message = document.getElementById("save-message");
  message.textContent = text;
  message.hidden = false;
}

// Quanto tempo o aviso fica no topo.
const NOTICE_MS = 10000;
let noticeTimer = null;

// O aviso de que a tarefa saiu da tela: adiada, criada para outro dia, concluída olhando outro
// dia ou desmarcada de volta ao dia marcado. Também a data nova de uma tarefa editada, e se ela
// contou como adiamento, e a tarefa excluída. E o tipo criado com o formulário já fechado (dois Esc
// durante a criação). Uma linha só, para todos; o texto novo substitui o anterior.
function showNotice(text) {
  const notice = document.getElementById("notice");
  notice.textContent = text;
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(hideNotice, NOTICE_MS);
}

function hideNotice() {
  clearTimeout(noticeTimer);
  const notice = document.getElementById("notice");
  notice.textContent = "";
  notice.hidden = true;
}

// Esconde a linha de erro e o aviso. Toda gravação nova começa por aqui.
function hideMessages() {
  const message = document.getElementById("save-message");
  message.textContent = "";
  message.hidden = true;
  hideNotice();
}
