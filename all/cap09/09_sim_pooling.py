#| label: fig-09-sim-pooling
#| fig-cap: "Simulador interativo de pooling: escolha entre max-pooling e average-pooling e avance passo a passo para observar a redução da resolução espacial do mapa de características."
#| echo: false
#| output: true

from IPython.display import HTML
HTML('''
<div id="cap09pool_Root" style="background-color:#fef9ef;border-radius:18px;border:1px solid #ede6d8;overflow:hidden;margin-top:20px;font-family:sans-serif;">
  <div style="background:#f3efe6;padding:8px 16px;font-size:12px;color:#5e5a4a;border-bottom:1px solid #e9dfcf;display:flex;justify-content:space-between;align-items:center;">
    <span>🔻 Simulador: Pooling</span>
    <span style="background:#e8e0cf;border-radius:40px;padding:2px 10px;font-weight:600;font-size:10px;">janela 2×2, stride 2</span>
  </div>
  <div style="padding:20px;background:white;overflow:auto">

    <div style="background:#fafafa;border:1px solid #ddd;border-radius:12px;padding:14px;margin-bottom:14px;">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
        <span style="font-size:11px;font-weight:600;color:#374151;">Tipo:</span>
        <button id="cap09pool_btnMax" class="cap09pool_active" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #4f46e5;background:#4f46e5;color:#fff;cursor:pointer;">Max-pooling</button>
        <button id="cap09pool_btnAvg" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">Average-pooling</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <button id="cap09pool_btnPasso" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #16a34a;background:#16a34a;color:#fff;cursor:pointer;">▶ Avançar 1 Passo</button>
        <button id="cap09pool_btnTudo" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">⏭ Calcular Tudo</button>
        <button id="cap09pool_btnReset" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">↺ Resetar</button>
        <span style="font-size:11px;color:#6b7280;">Janela atual: <b id="cap09pool_posTxt">(0, 0)</b> de 4×4</span>
      </div>
      <div id="cap09pool_explicacao" style="font-size:10.5px;color:#6b7280;margin-top:8px;line-height:1.4;">O <b>max-pooling</b> mantém apenas o maior valor de cada janela 2×2, reduzindo a resolução espacial pela metade e preservando as respostas mais fortes do mapa de características.</div>
    </div>

    <div style="display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;justify-content:center;">
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Mapa de entrada (8×8) — janela atual destacada</div>
        <canvas id="cap09pool_canvasEntrada" width="240" height="240"></canvas>
      </div>
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Mapa reduzido (4×4)</div>
        <canvas id="cap09pool_canvasSaida" width="160" height="160"></canvas>
      </div>
    </div>

  </div>
</div>

<style>
  #cap09pool_Root button.cap09pool_active { background: #4f46e5 !important; color: #fff !important; border-color: #4f46e5 !important; }
</style>

<script>
(function(){
  var cap09pool_ENTRADA = [
    [1, 3, 2, 8,  5, 1, 0, 2],
    [4, 6, 1, 2,  3, 9, 1, 0],
    [0, 1, 9, 3,  1, 2, 8, 4],
    [2, 5, 4, 7,  0, 1, 3, 6],
    [3, 8, 1, 0,  6, 2, 5, 1],
    [1, 2, 6, 4,  9, 0, 2, 3],
    [7, 0, 3, 1,  2, 8, 1, 4],
    [2, 4, 1, 5,  3, 1, 6, 9]
  ];
  var MAX_GLOBAL = 9;

  function init(root){
    if(!root || root.dataset.init) return;
    root.dataset.init = "1";

    var tipo = "max";
    var saida = Array.from({length:4}, function(){ return Array(4).fill(null); });
    var pos = {r:0, c:0};

    var ctxEnt = root.querySelector('#cap09pool_canvasEntrada').getContext('2d');
    var ctxSai = root.querySelector('#cap09pool_canvasSaida').getContext('2d');
    var posTxt = root.querySelector('#cap09pool_posTxt');
    var explicacao = root.querySelector('#cap09pool_explicacao');

    function corEscala(v, max){
      var inten = Math.min(1, v/max);
      var c = Math.round(245 - inten*160);
      return 'rgb('+c+','+(c+8)+',255)';
    }

    function desenharEntrada(){
      var tam = 30;
      ctxEnt.clearRect(0,0,240,240);
      for (var r=0;r<8;r++){
        for (var c=0;c<8;c++){
          var v = cap09pool_ENTRADA[r][c];
          ctxEnt.fillStyle = corEscala(v, MAX_GLOBAL);
          ctxEnt.fillRect(c*tam, r*tam, tam, tam);
          ctxEnt.strokeStyle = "#e5e7eb";
          ctxEnt.strokeRect(c*tam, r*tam, tam, tam);
          ctxEnt.fillStyle = "#1f2937";
          ctxEnt.font = "11px monospace";
          ctxEnt.textAlign = "center";
          ctxEnt.fillText(v, c*tam+tam/2, r*tam+tam/2+4);
        }
      }
      if (pos.r < 4){
        ctxEnt.strokeStyle = "#dc2626";
        ctxEnt.lineWidth = 3;
        ctxEnt.strokeRect(pos.c*2*tam, pos.r*2*tam, tam*2, tam*2);
        ctxEnt.lineWidth = 1;
      }
    }

    function desenharSaida(){
      var tam = 40;
      ctxSai.clearRect(0,0,160,160);
      for (var r=0;r<4;r++){
        for (var c=0;c<4;c++){
          var v = saida[r][c];
          ctxSai.fillStyle = (v === null) ? "#f3f4f6" : corEscala(v, MAX_GLOBAL);
          ctxSai.fillRect(c*tam, r*tam, tam, tam);
          ctxSai.strokeStyle = "#e5e7eb";
          ctxSai.strokeRect(c*tam, r*tam, tam, tam);
          if (v !== null){
            ctxSai.fillStyle = "#1f2937";
            ctxSai.font = "11px monospace";
            ctxSai.textAlign = "center";
            ctxSai.fillText(v.toFixed(1), c*tam+tam/2, r*tam+tam/2+4);
          }
        }
      }
      if (pos.r < 4){
        ctxSai.strokeStyle = "#dc2626";
        ctxSai.lineWidth = 2;
        ctxSai.strokeRect(pos.c*tam, pos.r*tam, tam, tam);
        ctxSai.lineWidth = 1;
      }
    }

    function calcularJanela(r, c){
      var vals = [];
      for (var i=0;i<2;i++) for (var j=0;j<2;j++) vals.push(cap09pool_ENTRADA[r*2+i][c*2+j]);
      if (tipo === "max") return Math.max.apply(null, vals);
      return vals.reduce(function(a,b){return a+b;},0) / vals.length;
    }

    function avancarPasso(){
      if (pos.r >= 4) return;
      saida[pos.r][pos.c] = calcularJanela(pos.r, pos.c);
      pos.c++;
      if (pos.c >= 4){ pos.c = 0; pos.r++; }
      render();
    }

    function calcularTudo(){
      while (pos.r < 4) avancarPasso();
    }

    function resetar(){
      saida = Array.from({length:4}, function(){ return Array(4).fill(null); });
      pos = {r:0, c:0};
      render();
    }

    function render(){
      desenharEntrada();
      desenharSaida();
      posTxt.textContent = pos.r < 4 ? '(' + pos.r + ', ' + pos.c + ')' : 'concluído';
    }

    function selecionarTipo(t){
      tipo = t;
      root.querySelector('#cap09pool_btnMax').classList.toggle('cap09pool_active', t === "max");
      root.querySelector('#cap09pool_btnAvg').classList.toggle('cap09pool_active', t === "avg");
      explicacao.innerHTML = t === "max"
        ? "O <b>max-pooling</b> mantém apenas o maior valor de cada janela 2×2, reduzindo a resolução espacial pela metade e preservando as respostas mais fortes do mapa de características."
        : "O <b>average-pooling</b> calcula a média dos quatro valores de cada janela 2×2, suavizando a informação em vez de preservar apenas o pico de resposta.";
      resetar();
    }

    root.querySelector('#cap09pool_btnMax').addEventListener('click', function(){ selecionarTipo("max"); });
    root.querySelector('#cap09pool_btnAvg').addEventListener('click', function(){ selecionarTipo("avg"); });
    root.querySelector('#cap09pool_btnPasso').addEventListener('click', avancarPasso);
    root.querySelector('#cap09pool_btnTudo').addEventListener('click', calcularTudo);
    root.querySelector('#cap09pool_btnReset').addEventListener('click', resetar);

    render();
  }

  function tryInit(){
    var root = document.getElementById('cap09pool_Root');
    if(root) init(root); else setTimeout(tryInit, 200);
  }
  tryInit();
})();
</script>
''')
