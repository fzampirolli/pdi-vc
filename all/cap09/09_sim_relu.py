#| label: fig-09-sim-relu
#| fig-cap: "Simulador interativo da função de ativação ReLU: arraste o controle para ver como valores negativos são zerados e valores positivos são preservados, tanto na curva quanto em um mapa de características real."
#| echo: false
#| output: true

from IPython.display import HTML
HTML('''
<div id="cap09relu_Root" style="background-color:#fef9ef;border-radius:18px;border:1px solid #ede6d8;overflow:hidden;margin-top:20px;font-family:sans-serif;">
  <div style="background:#f3efe6;padding:8px 16px;font-size:12px;color:#5e5a4a;border-bottom:1px solid #e9dfcf;display:flex;justify-content:space-between;align-items:center;">
    <span>⚡ Simulador: Função de Ativação ReLU</span>
    <span style="background:#e8e0cf;border-radius:40px;padding:2px 10px;font-weight:600;font-size:10px;">ReLU(x) = max(0, x)</span>
  </div>
  <div style="padding:20px;background:white;overflow:auto">

    <div style="background:#fafafa;border:1px solid #ddd;border-radius:12px;padding:14px;margin-bottom:14px;">
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:11px;font-weight:600;color:#374151;">x =</span>
        <input type="range" id="cap09relu_slider" min="-5" max="5" step="0.1" value="-2.5" style="flex:1;min-width:160px;">
        <span id="cap09relu_valTxt" style="font-family:monospace;font-size:12px;min-width:190px;color:#374151;">x = -2.50  →  ReLU(x) = 0.00</span>
      </div>
    </div>

    <div style="display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;justify-content:center;">
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Curva da função ReLU</div>
        <canvas id="cap09relu_canvasCurva" width="280" height="220"></canvas>
      </div>
      <div>
        <div style="font-size:11px;font-weight:600;text-align:center;margin-bottom:4px;color:#4b5563;">Mapa de características: antes / depois</div>
        <canvas id="cap09relu_canvasMapa" width="260" height="220"></canvas>
        <div style="display:flex;gap:8px;justify-content:center;margin-top:8px;">
          <button id="cap09relu_btnAplicar" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #16a34a;background:#16a34a;color:#fff;cursor:pointer;">Aplicar ReLU ao mapa</button>
          <button id="cap09relu_btnReset" style="font-size:11px;padding:6px 12px;border-radius:4px;border:1px solid #d1d5db;background:#fff;cursor:pointer;">↺ Resetar</button>
        </div>
      </div>
    </div>

  </div>
</div>

<script>
(function(){
  var cap09relu_MAPA = [
    [ 1.2, -0.8,  3.4, -2.1, 0.5],
    [-1.5,  2.7, -0.3,  1.1, -4.0],
    [ 0.9, -2.9,  4.8, -0.6,  2.2],
    [-3.3,  0.2, -1.1,  3.9, -0.4],
    [ 2.0, -1.7,  0.8, -2.6,  1.4]
  ];

  function init(root){
    if(!root || root.dataset.init) return;
    root.dataset.init = "1";

    var aplicado = false;

    var ctxCurva = root.querySelector('#cap09relu_canvasCurva').getContext('2d');
    var ctxMapa  = root.querySelector('#cap09relu_canvasMapa').getContext('2d');
    var slider   = root.querySelector('#cap09relu_slider');
    var valTxt   = root.querySelector('#cap09relu_valTxt');

    var W = 280, H = 220;
    var origemX = 40, origemY = H - 30;
    var escala = 22;

    function xParaPixel(x){ return origemX + x*escala; }
    function yParaPixel(y){ return origemY - y*escala; }

    function desenharCurva(x){
      ctxCurva.clearRect(0,0,W,H);

      ctxCurva.strokeStyle = "#9ca3af";
      ctxCurva.lineWidth = 1;
      ctxCurva.beginPath();
      ctxCurva.moveTo(0, origemY); ctxCurva.lineTo(W, origemY);
      ctxCurva.moveTo(origemX, 0); ctxCurva.lineTo(origemX, H);
      ctxCurva.stroke();

      ctxCurva.fillStyle = "#6b7280";
      ctxCurva.font = "10px sans-serif";
      ctxCurva.fillText("x", W-12, origemY-4);
      ctxCurva.fillText("ReLU(x)", origemX+4, 10);

      ctxCurva.strokeStyle = "#4f46e5";
      ctxCurva.lineWidth = 2.5;
      ctxCurva.beginPath();
      ctxCurva.moveTo(xParaPixel(-5), yParaPixel(0));
      ctxCurva.lineTo(xParaPixel(0), yParaPixel(0));
      ctxCurva.lineTo(xParaPixel(5), yParaPixel(5));
      ctxCurva.stroke();

      var y = Math.max(0, x);
      ctxCurva.fillStyle = "#dc2626";
      ctxCurva.beginPath();
      ctxCurva.arc(xParaPixel(x), yParaPixel(y), 5, 0, 2*Math.PI);
      ctxCurva.fill();

      ctxCurva.strokeStyle = "#fca5a5";
      ctxCurva.setLineDash([3,3]);
      ctxCurva.beginPath();
      ctxCurva.moveTo(xParaPixel(x), origemY);
      ctxCurva.lineTo(xParaPixel(x), yParaPixel(y));
      ctxCurva.lineTo(origemX, yParaPixel(y));
      ctxCurva.stroke();
      ctxCurva.setLineDash([]);
    }

    function corValor(v, apl){
      if (apl && v < 0) v = 0;
      if (v < 0){
        var inten = Math.min(1, Math.abs(v)/5);
        var c = Math.round(255 - inten*180);
        return 'rgb('+c+','+c+',255)';
      } else {
        var inten2 = Math.min(1, v/5);
        var c2 = Math.round(255 - inten2*200);
        return 'rgb('+c2+',255,'+c2+')';
      }
    }

    function desenharMapa(){
      var tam = 42, offX = 20, offY = 10;
      ctxMapa.clearRect(0,0,260,220);
      for (var r=0;r<5;r++){
        for (var c=0;c<5;c++){
          var vOrig = cap09relu_MAPA[r][c];
          var v = aplicado ? Math.max(0, vOrig) : vOrig;
          ctxMapa.fillStyle = corValor(vOrig, aplicado);
          ctxMapa.fillRect(offX+c*tam, offY+r*tam, tam, tam);
          ctxMapa.strokeStyle = "#d1d5db";
          ctxMapa.strokeRect(offX+c*tam, offY+r*tam, tam, tam);
          ctxMapa.fillStyle = "#1f2937";
          ctxMapa.font = "10px monospace";
          ctxMapa.textAlign = "center";
          ctxMapa.fillText(v.toFixed(1), offX+c*tam+tam/2, offY+r*tam+tam/2+4);
        }
      }
      ctxMapa.fillStyle = "#6b7280";
      ctxMapa.font = "10px sans-serif";
      ctxMapa.textAlign = "left";
      ctxMapa.fillText(aplicado ? "Depois da ReLU (negativos → 0)" : "Antes da ReLU (valores brutos da convolução)", offX, 210);
    }

    function atualizarSlider(){
      var x = parseFloat(slider.value);
      var y = Math.max(0, x);
      valTxt.textContent = 'x = ' + x.toFixed(2) + '  →  ReLU(x) = ' + y.toFixed(2);
      desenharCurva(x);
    }

    slider.addEventListener('input', atualizarSlider);

    root.querySelector('#cap09relu_btnAplicar').addEventListener('click', function(){
      aplicado = true;
      desenharMapa();
    });
    root.querySelector('#cap09relu_btnReset').addEventListener('click', function(){
      aplicado = false;
      desenharMapa();
    });

    atualizarSlider();
    desenharMapa();
  }

  function tryInit(){
    var root = document.getElementById('cap09relu_Root');
    if(root) init(root); else setTimeout(tryInit, 200);
  }
  tryInit();
})();
</script>
''')
