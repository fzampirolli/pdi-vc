#| label: fig-09-sim-convolucao
#| fig-cap: "Simulador interativo de convolução: escolha um kernel e avance passo a passo (ou calcule tudo de uma vez) para observar a construção do mapa de características."
#| echo: false
#| output: true

from IPython.display import HTML
HTML('''
<div id="cap09conv_Root" style="background-color:#fef9ef;border-radius:18px;border:1px solid #ede6d8;overflow:hidden;margin-top:20px;font-family:sans-serif;">
  <div style="background:#f3efe6;padding:8px 16px;font-size:12px;color:#5e5a4a;border-bottom:1px solid #e9dfcf;display:flex;justify-content:space-between;align-items:center;">
    <span>🎯 Simulador: Convolução Passo a Passo</span>
    <span style="background:#e8e0cf;border-radius:40px;padding:2px 10px;font-weight:600;font-size:10px;">kernel 3×3, stride 1, sem preenchimento</span>
  </div>
  <div style="padding:20px;background:white;overflow:auto">

    <div style="background:#fafafa;border:1px solid #ddd;border-radius:12px;padding:14px;margin-bottom:14px;">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
        <span style="font-size:11px;font-weight:600;color:#374151;">Kernel:</span>
        <button id="cap09conv_btnIdentidade" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">Identidade</button>
        <button id="cap09conv_btnBordas" class="cap09conv_active" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #4f46e5;background:#4f46e5;color:#fff;cursor:pointer;">Bordas (Sobel-h)</button>
        <button id="cap09conv_btnBlur" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">Borrão (média)</button>
        <button id="cap09conv_btnRealce" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">Realce</button>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <button id="cap09conv_btnPasso" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #16a34a;background:#16a34a;color:#fff;cursor:pointer;">▶ Avançar 1 Passo</button>
        <button id="cap09conv_btnTudo" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">⏭ Calcular Tudo</button>
        <button id="cap09conv_btnReset" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">↺ Resetar</button>
        <span style="font-size:11px;color:#6b7280;">Posição atual: <b id="cap09conv_posTxt">(0, 0)</b> de 6×6</span>
      </div>
      <div style="font-size:10.5px;color:#6b7280;margin-top:8px;line-height:1.4;">O mesmo kernel 3×3 é aplicado em <b>todas</b> as posições da imagem (compartilhamento de pesos): apenas a janela de entrada muda a cada passo, os valores do filtro permanecem fixos.</div>
    </div>

    <div style="display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;justify-content:center;">
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Entrada (8×8) — janela atual destacada</div>
        <canvas id="cap09conv_canvasEntrada" width="240" height="240"></canvas>
      </div>
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Kernel (3×3)</div>
        <canvas id="cap09conv_canvasKernel" width="120" height="120"></canvas>
      </div>
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Mapa de Características (6×6)</div>
        <canvas id="cap09conv_canvasSaida" width="180" height="180"></canvas>
      </div>
    </div>

  </div>
</div>

<style>
  #cap09conv_Root button.cap09conv_active { background: #4f46e5 !important; color: #fff !important; border-color: #4f46e5 !important; }
</style>

<script>
(function(){
  var cap09conv_ENTRADA = [
    [230,225,220,60,55,50,45,40],
    [228,222,218,58,52,48,42,38],
    [225,220,215,55,50,45,40,35],
    [235,230,50,50,180,175,170,165],
    [232,228,48,45,178,172,168,162],
    [230,225,45,42,175,170,165,160],
    [220,215,210,55,50,45,182,178],
    [218,212,208,52,48,42,180,175]
  ];

  var cap09conv_KERNELS = {
    identidade: {nome:"Identidade", k:[[0,0,0],[0,1,0],[0,0,0]], div:1},
    bordas:     {nome:"Bordas (Sobel-h)", k:[[-1,0,1],[-2,0,2],[-1,0,1]], div:1},
    blur:       {nome:"Borrão (média)", k:[[1,1,1],[1,1,1],[1,1,1]], div:9},
    realce:     {nome:"Realce", k:[[0,-1,0],[-1,5,-1],[0,-1,0]], div:1}
  };

  function init(root){
    if(!root || root.dataset.init) return;
    root.dataset.init = "1";

    var kernelAtual = cap09conv_KERNELS.bordas;
    var saida = Array.from({length:6}, function(){ return Array(6).fill(null); });
    var pos = {r:0, c:0};

    var ctxEnt = root.querySelector('#cap09conv_canvasEntrada').getContext('2d');
    var ctxKer = root.querySelector('#cap09conv_canvasKernel').getContext('2d');
    var ctxSai = root.querySelector('#cap09conv_canvasSaida').getContext('2d');
    var posTxt = root.querySelector('#cap09conv_posTxt');

    function corCinza(v){
      var c = Math.max(0, Math.min(255, Math.round(v)));
      return 'rgb('+c+','+c+','+c+')';
    }

    function desenharEntrada(){
      var tam = 30;
      ctxEnt.clearRect(0,0,240,240);
      for (var r=0;r<8;r++){
        for (var c=0;c<8;c++){
          ctxEnt.fillStyle = corCinza(cap09conv_ENTRADA[r][c]);
          ctxEnt.fillRect(c*tam, r*tam, tam, tam);
          ctxEnt.strokeStyle = "#e5e7eb";
          ctxEnt.strokeRect(c*tam, r*tam, tam, tam);
        }
      }
      ctxEnt.strokeStyle = "#dc2626";
      ctxEnt.lineWidth = 3;
      ctxEnt.strokeRect(pos.c*tam, pos.r*tam, tam*3, tam*3);
      ctxEnt.lineWidth = 1;
    }

    function desenharKernel(){
      var tam = 40;
      ctxKer.clearRect(0,0,120,120);
      var k = kernelAtual.k;
      var maxAbs = 1;
      for (var i=0;i<3;i++) for (var j=0;j<3;j++) maxAbs = Math.max(maxAbs, Math.abs(k[i][j]));
      for (var i=0;i<3;i++){
        for (var j=0;j<3;j++){
          var val = k[i][j];
          var intensidade = Math.round(128 + (val/maxAbs)*127);
          ctxKer.fillStyle = corCinza(intensidade);
          ctxKer.fillRect(j*tam, i*tam, tam, tam);
          ctxKer.strokeStyle = "#9ca3af";
          ctxKer.strokeRect(j*tam, i*tam, tam, tam);
          ctxKer.fillStyle = Math.abs(val) > maxAbs/2 ? "#fff" : "#111827";
          ctxKer.font = "12px monospace";
          ctxKer.textAlign = "center";
          ctxKer.fillText(val.toFixed(0), j*tam+tam/2, i*tam+tam/2+4);
        }
      }
    }

    function desenharSaida(){
      var tam = 30;
      ctxSai.clearRect(0,0,180,180);
      for (var r=0;r<6;r++){
        for (var c=0;c<6;c++){
          var v = saida[r][c];
          ctxSai.fillStyle = (v === null) ? "#f3f4f6" : corCinza(v);
          ctxSai.fillRect(c*tam, r*tam, tam, tam);
          ctxSai.strokeStyle = "#e5e7eb";
          ctxSai.strokeRect(c*tam, r*tam, tam, tam);
        }
      }
      if (pos.r < 6){
        ctxSai.strokeStyle = "#dc2626";
        ctxSai.lineWidth = 2;
        ctxSai.strokeRect(pos.c*tam, pos.r*tam, tam, tam);
        ctxSai.lineWidth = 1;
      }
    }

    function calcularPosicao(r, c){
      var k = kernelAtual.k, div = kernelAtual.div;
      var soma = 0;
      for (var i=0;i<3;i++) for (var j=0;j<3;j++) soma += cap09conv_ENTRADA[r+i][c+j] * k[i][j];
      return soma / div;
    }

    function avancarPasso(){
      if (pos.r >= 6) return;
      saida[pos.r][pos.c] = calcularPosicao(pos.r, pos.c);
      pos.c++;
      if (pos.c >= 6){ pos.c = 0; pos.r++; }
      render();
    }

    function calcularTudo(){
      while (pos.r < 6) avancarPasso();
    }

    function resetar(){
      saida = Array.from({length:6}, function(){ return Array(6).fill(null); });
      pos = {r:0, c:0};
      render();
    }

    function render(){
      desenharEntrada();
      desenharKernel();
      desenharSaida();
      posTxt.textContent = pos.r < 6 ? '(' + pos.r + ', ' + pos.c + ')' : 'concluído';
    }

    function selecionarKernel(nomeBtn, kernel){
      kernelAtual = kernel;
      ["cap09conv_btnIdentidade","cap09conv_btnBordas","cap09conv_btnBlur","cap09conv_btnRealce"].forEach(function(id){
        var el = root.querySelector('#'+id);
        el.classList.toggle('cap09conv_active', id === nomeBtn);
      });
      resetar();
    }

    root.querySelector('#cap09conv_btnIdentidade').addEventListener('click', function(){ selecionarKernel('cap09conv_btnIdentidade', cap09conv_KERNELS.identidade); });
    root.querySelector('#cap09conv_btnBordas').addEventListener('click', function(){ selecionarKernel('cap09conv_btnBordas', cap09conv_KERNELS.bordas); });
    root.querySelector('#cap09conv_btnBlur').addEventListener('click', function(){ selecionarKernel('cap09conv_btnBlur', cap09conv_KERNELS.blur); });
    root.querySelector('#cap09conv_btnRealce').addEventListener('click', function(){ selecionarKernel('cap09conv_btnRealce', cap09conv_KERNELS.realce); });
    root.querySelector('#cap09conv_btnPasso').addEventListener('click', avancarPasso);
    root.querySelector('#cap09conv_btnTudo').addEventListener('click', calcularTudo);
    root.querySelector('#cap09conv_btnReset').addEventListener('click', resetar);

    render();
  }

  function tryInit(){
    var root = document.getElementById('cap09conv_Root');
    if(root) init(root); else setTimeout(tryInit, 200);
  }
  tryInit();
})();
</script>
''')
