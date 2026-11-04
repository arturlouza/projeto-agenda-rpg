// Endereço da API (seção 6.5). Front e API têm a mesma origem, então é um caminho relativo.
const API_BASE = "./";

// Toda chamada à API passa por aqui (seção 6.5). Na tarefa 15, esta função passa a tratar o 401.
async function apiRequest(path, options) {
  const response = await fetch(API_BASE + path, options);
  if (!response.ok) {
    throw new Error("A API respondeu " + response.status);
  }
  return response.json();
}

// Só formata o número com ponto de milhar (2.039). Não faz conta.
const numberFormat = new Intl.NumberFormat("pt-BR");

// Mostra no topo o que o servidor mandou, sem nenhuma conta de XP (regra 9 do CLAUDE.md).
function showPlayer(player) {
  document.getElementById("player-level").textContent = "Nível " + numberFormat.format(player.level);
  document.getElementById("player-xp").textContent =
    numberFormat.format(player.xp_into_level) + " / " + numberFormat.format(player.xp_for_next_level) + " XP";
  document.getElementById("player-progress").value = player.progress_percent;
  document.getElementById("player-message").hidden = true;
}

// Busca o jogador. Se a rede ou a API falhar, troca o "Carregando…" pelo aviso de erro.
async function loadPlayer() {
  try {
    showPlayer(await apiRequest("player"));
  } catch (error) {
    console.error(error);
    const message = document.getElementById("player-message");
    message.textContent = "Não foi possível carregar o nível. Recarregue a página.";
    message.classList.add("is-error");
  }
}

loadPlayer();
