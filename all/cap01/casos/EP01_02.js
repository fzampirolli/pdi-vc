function escreva(s) { try { document.write(s); } catch(e) { console.log(s); } }
function ler(linhas, i) { return linhas.toString().split('\n')[i]; }

process.stdin.once('data', linhas => {
  var C = ler(linhas, 0); // ATENÇÃO NESTA INSTRUÇÃO!
  var F = C * 9/5 + 32;
  escreva(C + " graus Celsius corresponde a " + F.toFixed(1) + " graus Fahrenheit");
});