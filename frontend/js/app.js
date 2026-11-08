// app.js: o início. Liga os ouvintes da página inteira e faz os primeiros pedidos. Carrega por
// último, porque, ao carregar, já usa loadPlayer e loadDay, que vêm dos arquivos anteriores.

// ---------------------------------------------------------------------------------------------
// 1. Início
// ---------------------------------------------------------------------------------------------

// Pede a lista e o topo ao mesmo tempo. Cada um trata o próprio erro. A lista é a do dia da
// tela (dayPath): em hoje, /tasks/today; em outro dia, esse mesmo dia.
async function refreshScreen() {
  await Promise.all([loadDay(), loadPlayer()]);
}

document.getElementById("day-retry").addEventListener("click", function () {
  showDayLoading();
  loadDay();
});

// Quando o app volta do segundo plano, pede a lista e o topo de novo. Em hoje, o servidor diz que
// dia é: se a meia-noite passou enquanto o app estava escondido, a tela já mostra o dia novo. Em
// outro dia, a tela continua nele.
document.addEventListener("visibilitychange", function () {
  if (document.visibilityState === "visible") {
    refreshScreen();
  }
});

// Todo clique da página "sobe" até o document, também os de dentro do formulário. Se ele não
// começou no botão que pede confirmação (Adiar ou Excluir), a confirmação acaba. O clique que a
// iniciou chega aqui depois, com o alvo igual ao botão, e por isso não a cancela.
document.addEventListener("click", function (event) {
  if (confirmButton !== null && event.target !== confirmButton) {
    cancelConfirmation();
  }
});

loadPlayer();
loadDay();
