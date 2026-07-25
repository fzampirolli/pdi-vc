#| label: fig-09-sim-arquitetura
#| fig-cap: "Simulador interativo da arquitetura de uma CNN: clique em cada bloco do pipeline para ver como a dimensão dos dados muda, do mapa de entrada até as probabilidades finais do Softmax."
#| echo: false
#| output: true

from IPython.display import HTML
HTML('''
<div id="cap09arch_Root" style="background-color:#fef9ef;border-radius:18px;border:1px solid #ede6d8;overflow:hidden;margin-top:20px;font-family:sans-serif;">
  <div style="background:#f3efe6;padding:8px 16px;font-size:12px;color:#5e5a4a;border-bottom:1px solid #e9dfcf;display:flex;justify-content:space-between;align-items:center;">
    <span>🏗️ Simulador: Arquitetura de uma CNN</span>
    <span style="background:#e8e0cf;border-radius:40px;padding:2px 10px;font-weight:600;font-size:10px;">clique em um bloco do pipeline</span>
  </div>
  <div style="padding:20px;background:white;overflow:auto">

    <div style="background:#fafafa;border:1px solid #ddd;border-radius:12px;padding:10px;margin-bottom:14px;overflow-x:auto;">
      <div id="cap09arch_flow" style="display:flex;align-items:center;gap:2px;padding:6px 4px;min-width:640px;"></div>
    </div>

    <div style="background:#fafafa;border:1px solid #ddd;border-radius:12px;padding:14px;">
      <div id="cap09arch_desc" style="font-size:12px;line-height:1.6;color:#374151;min-height:60px;"></div>
      <div id="cap09arch_barsWrap" style="display:none;align-items:flex-end;gap:14px;height:120px;margin-top:10px;"></div>
    </div>

  </div>
</div>

<style>
  #cap09arch_Root .cap09arch_bloco { flex: 0 0 auto; min-width: 84px; text-align: center; padding: 10px 6px; border-radius: 6px; border: 2px solid #d1d5db; background: #fff; cursor: pointer; font-size: 10.5px; font-weight: 600; color: #374151; }
  #cap09arch_Root .cap09arch_bloco:hover { border-color: #a5b4fc; }
  #cap09arch_Root .cap09arch_bloco.cap09arch_sel { border-color: #4f46e5; background: #eef2ff; color: #3730a3; }
  #cap09arch_Root .cap09arch_shape { display:block; font-size: 9px; font-weight: 400; color: #6b7280; margin-top: 3px; }
  #cap09arch_Root .cap09arch_seta { flex: 0 0 auto; color: #9ca3af; font-size: 16px; padding: 0 2px; }
  #cap09arch_Root .cap09arch_bar_wrap { display:flex; flex-direction:column; align-items:center; font-size: 10.5px; color:#4b5563; }
  #cap09arch_Root .cap09arch_bar { width: 34px; background: linear-gradient(#4f46e5,#818cf8); border-radius: 4px 4px 0 0; }
  #cap09arch_Root code { background:#f3f4f6; padding:1px 4px; border-radius:3px; }
</style>

<script>
(function(){
  var cap09arch_ETAPAS = [
    {
      id: "entrada", nome: "Entrada", forma: "32×32×3",
      desc: "A <b>imagem de entrada</b> é representada como uma matriz de pixels com 3 canais de cor (R, G, B). Aqui, uma imagem de 32×32 pixels."
    },
    {
      id: "conv1", nome: "Conv + ReLU", forma: "30×30×16",
      desc: "A <b>camada convolucional</b> aplica 16 filtros 3×3 aprendidos, gerando 16 mapas de características. Em seguida, a <b>ReLU</b> zera os valores negativos, introduzindo não linearidade."
    },
    {
      id: "pool1", nome: "Pooling", forma: "15×15×16",
      desc: "O <b>max-pooling</b> reduz a resolução espacial pela metade, mantendo o valor mais forte de cada janela e diminuindo o custo computacional das camadas seguintes."
    },
    {
      id: "conv2", nome: "Conv + ReLU", forma: "13×13×32",
      desc: "Uma nova camada convolucional aprende <b>32 filtros</b> sobre os mapas já reduzidos, combinando padrões simples (bordas) em características mais complexas (texturas, formas)."
    },
    {
      id: "pool2", nome: "Pooling", forma: "6×6×32",
      desc: "Outra camada de <b>pooling</b> reduz ainda mais a resolução espacial, mantendo apenas as respostas mais relevantes de cada região."
    },
    {
      id: "flatten", nome: "Flatten", forma: "1.152 valores",
      desc: "A operação <b>Flatten</b> reorganiza os mapas de características (6×6×32) em um único <b>vetor</b> de 1.152 valores, eliminando a estrutura espacial para uso pelas camadas seguintes."
    },
    {
      id: "fc", nome: "Totalmente Conectada", forma: "128 neurônios",
      desc: "A(s) <b>camada(s) totalmente conectada(s)</b> combinam todas as características extraídas para aprender relações globais relevantes para a tarefa de classificação."
    },
    {
      id: "softmax", nome: "Softmax", forma: "3 classes",
      desc: "A camada <b>Softmax</b> converte as saídas da rede em <b>probabilidades</b> que somam 1, uma para cada classe possível.",
      barras: [
        {rotulo:"Gato", valor:0.72},
        {rotulo:"Cachorro", valor:0.21},
        {rotulo:"Pássaro", valor:0.07}
      ]
    }
  ];

  function init(root){
    if(!root || root.dataset.init) return;
    root.dataset.init = "1";

    var flowEl = root.querySelector('#cap09arch_flow');
    var descEl = root.querySelector('#cap09arch_desc');
    var barsWrapEl = root.querySelector('#cap09arch_barsWrap');

    function montarFluxo(){
      cap09arch_ETAPAS.forEach(function(etapa, idx){
        var bloco = document.createElement('div');
        bloco.className = 'cap09arch_bloco';
        bloco.id = 'cap09arch_bloco_' + etapa.id;
        bloco.innerHTML = etapa.nome + '<span class="cap09arch_shape">' + etapa.forma + '</span>';
        bloco.addEventListener('click', function(){ selecionar(idx); });
        flowEl.appendChild(bloco);

        if (idx < cap09arch_ETAPAS.length - 1){
          var seta = document.createElement('div');
          seta.className = 'cap09arch_seta';
          seta.textContent = '→';
          flowEl.appendChild(seta);
        }
      });
    }

    function desenharBarras(barras){
      barsWrapEl.innerHTML = '';
      barsWrapEl.style.display = 'flex';
      var alturaMax = 100;
      barras.forEach(function(b){
        var wrap = document.createElement('div');
        wrap.className = 'cap09arch_bar_wrap';
        var bar = document.createElement('div');
        bar.className = 'cap09arch_bar';
        bar.style.height = Math.round(b.valor * alturaMax) + 'px';
        var legenda = document.createElement('div');
        legenda.textContent = b.rotulo + ' (' + (b.valor*100).toFixed(0) + '%)';
        wrap.appendChild(bar);
        wrap.appendChild(legenda);
        barsWrapEl.appendChild(wrap);
      });
    }

    function selecionar(idx){
      var etapa = cap09arch_ETAPAS[idx];
      cap09arch_ETAPAS.forEach(function(e){
        var el = root.querySelector('#cap09arch_bloco_' + e.id);
        if (el) el.classList.remove('cap09arch_sel');
      });
      var atual = root.querySelector('#cap09arch_bloco_' + etapa.id);
      if (atual) atual.classList.add('cap09arch_sel');
      descEl.innerHTML = '<b>' + etapa.nome + '</b> — forma dos dados: <code>' + etapa.forma + '</code><br>' + etapa.desc;

      if (etapa.barras){
        desenharBarras(etapa.barras);
      } else {
        barsWrapEl.style.display = 'none';
      }
    }

    montarFluxo();
    selecionar(0);
  }

  function tryInit(){
    var root = document.getElementById('cap09arch_Root');
    if(root) init(root); else setTimeout(tryInit, 200);
  }
  tryInit();
})();
</script>
''')
