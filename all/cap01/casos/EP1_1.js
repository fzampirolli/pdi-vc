function escreva(s) { try { document.write(s); } catch(e) { console.log(s); } }

  var C = 65;
  var F = C * 9/5 + 32;
  escreva(C + " graus Celsius corresponde a " + F.toFixed(1) + " graus Fahrenheit");
