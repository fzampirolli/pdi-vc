"""
Morph – Operações morfológicas para Processamento de Imagens.
Copyright 2024 Francisco de Assis Zampirolli, UFABC. License MIT.
https://github.com/fzampirolli/morph - version 1.0
https://github.com/fzampirolli/pdi-vc/blob/master/morph/morph.py - version 1.1 - compacto
Last update: May 2026
"""

__version__ = "1.1.0"

import sys, subprocess
import numpy as np
import cv2


class mm:
    """Helper class for image processing tasks."""

    IN_INTERACTIVE = (
        'google.colab' in sys.modules          # Google Colab
        or 'ipykernel' in sys.modules          # Jupyter Notebook / JupyterLab / VSCode
        or 'IPython' in sys.modules            # IPython interativo
    )

    count_Images = 0

    def __init__(self): pass

    # ── UTILITIES ────────────────────────────────────────────────────────────

    @staticmethod
    def install(packages=['matplotlib', 'numpy', 'opencv-python']):
        """Instala pacotes pip. Ex: mm.install(['scikit-image'])"""
        for p in packages:
            subprocess.check_call([sys.executable, "-m", "pip", "install", p])


    @staticmethod
    def read(file, info=False):
        """
        Lê imagem de arquivo local ou URL.
        info=False: retorna ndarray (RGB).
        info=True: retorna objeto PIL.Image (preserva EXIF).
        """
        import re, requests
        import numpy as np  # Certifique-se de que o numpy está importado se usar fora do módulo
        from PIL import Image
        from io import BytesIO

        # Trata URL do Google Drive ou comum
        if file.startswith(('http://', 'https://', 'id=')):
            m = re.search(r'id=([a-zA-Z0-9_-]+)', file) or re.search(r'/d/([a-zA-Z0-9_-]+)', file)
            url = f"https://drive.google.com/uc?export=view&id={m.group(1)}" \
                if m and ('id=' in file or 'drive.google.com' in file) else file
            
            # DEFINA UM USER-AGENT IDENTIFICÁVEL PARA O WIKIMEDIA
            headers = {
                "User-Agent": "MeuLivroQuartoBot/1.0 (contato@seu-email.com; ferramenta de fins didáticos)"
            }
            
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            source = BytesIO(r.content)
        else:
            source = file

        # Retorno condicional
        img_pil = Image.open(source)
        if info:
            return img_pil
        
        # Converte para NumPy/RGB (padrão mm)
        return np.array(img_pil.convert("RGB"))

    @staticmethod
    def color(img):
        """Converte imagem para RGB."""
        if img.ndim == 2:         return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        if img.shape[2] == 4:    return cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    @staticmethod
    def gray(img):
        """Converte imagem colorida para escala de cinza."""
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY if img.ndim==3 and img.shape[2]==4
                            else cv2.COLOR_RGB2GRAY)

    @staticmethod
    def neg(f):
        """Inverte a imagem."""
        return cv2.bitwise_not(f)

    @staticmethod
    def binary(f):
        """True se binária, False se não, None se vazia."""
        hist, _ = np.histogram(f.ravel(), 256, [0, 256])
        nz = np.count_nonzero(hist > 0)
        return True if nz == 2 else (False if nz > 2 else None)

    # ── LEITURA / CRIAÇÃO ────────────────────────────────────────────────────

    @staticmethod
    def readImg(h, w):
        """Lê imagem h×w da entrada padrão (pixels por linha separados por espaço).
        Exemplo:
          mm.readImg(3, 4)
          0 1 0 0
          1 1 1 1
          0 1 0 0"""
        m = np.zeros((h, w), dtype='uint8')
        for l in range(h):
            m[l] = [int(i) for i in input().split() if i]
        return m

    @staticmethod
    def readImg2():
        """Lê imagem de tamanho variável da entrada padrão (até linha vazia)."""
        rows = []
        while line := input():
            rows.append([int(i) for i in line.split() if i])
        return np.array(rows, dtype='uint8')

    @staticmethod
    def randomImage(h, w, maxValue=9):
        """Cria imagem aleatória h×w com valores em [0, maxValue]."""
        return np.random.randint(maxValue + 1, size=(h, w)).astype('uint8')


    @staticmethod
    def resize(img, size_or_factor, method='bilinear'):
        """Redimensiona imagem via OpenCV integrado ao mm: nearest, bilinear, bicubic."""
        interp = {'nearest': cv2.INTER_NEAREST, 'bilinear': cv2.INTER_LINEAR, 'bicubic': cv2.INTER_CUBIC}
        m = interp.get(method, cv2.INTER_LINEAR)
        
        if isinstance(size_or_factor, (int, float)):
            return cv2.resize(img, (0,0), fx=size_or_factor, fy=size_or_factor, interpolation=m)
        return cv2.resize(img, size_or_factor, interpolation=m)
    
    @staticmethod
    def rotate(img, angle, center=None, scale=1.0, interp='bilinear'):
        """Rotaciona uma imagem em torno de um ponto central."""
        import cv2
        flags = {'nearest': cv2.INTER_NEAREST,
                'bilinear': cv2.INTER_LINEAR,
                'bicubic': cv2.INTER_CUBIC}.get(interp, cv2.INTER_LINEAR)
        h, w = img.shape[:2]
        if center is None:
            center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, scale)
        return cv2.warpAffine(img, M, (w, h), flags=flags)
    
    @staticmethod
    def translate(img, tx, ty):
        import cv2
        import numpy as np
        h, w = img.shape[:2]
        M = np.float32([[1, 0, tx], [0, 1, ty]])
        return cv2.warpAffine(img, M, (w, h))
    

    @staticmethod
    def shear(img, shx=0.0, shy=0.0):
        """Aplica cisalhamento afim: shx desloca horizontalmente, shy verticalmente."""
        import cv2
        import numpy as np
        h, w = img.shape[:2]
        M = np.float32([[1, shx, 0],
                        [shy, 1, 0]])
        return cv2.warpAffine(img, M, (w, h))

    @staticmethod
    def perspective_transform(img, pts1, pts2, size=None):
        """
        Aplica transformação de perspectiva (homografia) em uma imagem.
        
        Parâmetros:
            img: imagem de entrada (numpy array)
            pts1: pontos de origem (4 pontos) no formato np.float32
            pts2: pontos de destino (4 pontos) no formato np.float32
            size: tupla (largura, altura) da imagem de saída. Se None, usa o tamanho original.
        
        Retorna:
            imagem transformada
        """
        import cv2
        import numpy as np
        
        if size is None:
            h, w = img.shape[:2]
            size = (w, h)
        
        M = cv2.getPerspectiveTransform(pts1, pts2)
        dst = cv2.warpPerspective(img, M, size)
        return dst
    
    @staticmethod
    def show(*args, title=None, titles=None, cols=3, figsize=None):
        """Exibe imagens sobrepostas (modo simples) ou em grade (modo múltiplo).
            Modo simples:   mm.show(f1, f2, title='Exemplo')
            Modo múltiplo:  mm.show([f1, f2, f3], titles=['t1','t2','t3'], cols=3)
        """
        import matplotlib.pyplot as plt
        colors = [[255,0,0],[0,255,0],[0,0,255],[255,0,255],
                [0,255,255],[255,255,0],[255,50,50],[50,255,50]]
        if isinstance(args[0], list):  # modo múltiplo
            images = args[0]
            ts = titles or (title if isinstance(title, list) else [None]*len(images))
            rows = (len(images) + cols - 1) // cols
            size = figsize or (5*cols, 5*rows)
            _, axes = plt.subplots(rows, cols, figsize=size)
            axes = axes.reshape(rows, -1)
            for i, (img, t) in enumerate(zip(images, ts)):
                r, c = divmod(i, cols)
                axes[r,c].imshow(img, cmap=None if img.ndim==3 else 'gray')
                if t: axes[r,c].set_title(t)
            [axes[*divmod(i,cols)].axis('off') for i in range(len(images), rows*cols)]
            plt.tight_layout()
        else:                          # modo simples
            f = args[0].copy()
            [f.__setitem__(args[i]>0, colors[i-1]) for i in range(1, min(len(args), len(colors)+1))]
            plt.imshow(f, "gray")
            if title: plt.title(title)
        plt.savefig(f'fig_{mm.count_Images:04d}.png') if not mm.IN_INTERACTIVE else plt.show()
        mm.count_Images += not mm.IN_INTERACTIVE


    @staticmethod
    def drawImage(f):
        """Retorna string formatada da matriz para impressão."""
        fmt = '%' + str(1 + len(str(f.max()))) + 'd ' if f.min() < 0 \
              else '%' + str(len(str(f.max()))) + 'd '
        return ''.join(
            ''.join(fmt % f[i,j] for j in range(f.shape[1])) + '\n'
            for i in range(f.shape[0])
        )

    @staticmethod
    def _plot_grid(f):
        """Configura grade e rótulos para drawImagePlt/drawImageKernel."""
        import matplotlib.pyplot as plt
        h, w = f.shape
        plt.rcParams.update({'xtick.bottom':False,'xtick.labelbottom':False,
                             'xtick.top':True,'xtick.labeltop':True})
        plt.imshow(f, 'gray')
        plt.yticks(range(h)); plt.xticks(range(w))
        plt.ylabel('y'); plt.xlabel('x')
        [plt.axvline(i+.5, 0, h, color='r') for i in range(w-1)]
        [plt.axhline(j+.5, 0, w, color='r') for j in range(h-1)]

    @staticmethod
    def drawImagePlt(f):
        """Exibe imagem com grade e rótulos via Matplotlib."""
        import matplotlib.pyplot as plt
        plt.figure(figsize=(min(f.shape),)*2)
        mm._plot_grid(f)

    @staticmethod
    def drawImageKernel(f, B, x, y):
        """Exibe imagem com kernel B centrado em (x,y) destacado em amarelo."""
        import matplotlib.pyplot as plt
        Bh, Bw = B.shape
        Bcx, Bcy = Bw//3, Bh//3
        plt.figure(figsize=(min(f.shape),)*2)
        mm._plot_grid(f)
        plt.title(f'Processando pixel (x,y)=({x},{y})')
        [plt.plot([i+x-Bcx-.5]*2, [y-Bcy-.5, Bh+y-Bcy-.5], color='y', lw=5) for i in range(Bw+1)]
        [plt.plot([x-Bcx-.5, x-Bcx+Bw-.5], [j+y-Bcy-.5]*2, color='y', lw=5) for j in range(Bh+1)]

    @staticmethod
    def lblshow(f, border=3):
        """Exibe contornos coloridos de cada componente."""
        import matplotlib.pyplot as plt
        from skimage import measure
        fig, ax = plt.subplots()
        ax.imshow(f, interpolation='nearest', cmap=plt.cm.gray)
        for c in measure.find_contours(f, 0.0):
            ax.plot(c[:,1], c[:,0], linewidth=border)
        ax.axis('image'); ax.set_xticks([]); ax.set_yticks([])
        plt.imshow(f, "gray")
        if not mm.IN_INTERACTIVE:
            plt.savefig(f'fig_{mm.count_Images:04d}.png')
            mm.count_Images += 1

    # ── OPERAÇÕES BÁSICAS ────────────────────────────────────────────────────

    @staticmethod
    def subm(f, g):   return cv2.subtract(f, g)
    @staticmethod
    def addm(f, g):   return cv2.add(f, g)
    @staticmethod
    def union(f, g):  return np.maximum(f, g)
    @staticmethod
    def intersec(f1, f2): return np.minimum(f1, f2)

    @staticmethod
    def blend(f, g, alpha=0.5):
        """Mistura ponderada: alpha*f + (1-alpha)*g, com clipping para uint8."""
        return np.clip(
            alpha * f.astype(np.float32) + (1 - alpha) * g.astype(np.float32),
            0, 255
        ).astype(np.uint8)
    
    @staticmethod
    def band(f, g):   return cv2.bitwise_and(f, g)
    @staticmethod
    def bor(f, g):    return cv2.bitwise_or(f, g)
    @staticmethod
    def bxor(f, g):   return cv2.bitwise_xor(f, g)
    @staticmethod
    def bnot(f):      return cv2.bitwise_not(f)

    @staticmethod
    def threshold(img, limiar=0):
        """Limiarização binária. limiar=0 usa Otsu."""
        flags = cv2.THRESH_BINARY + (cv2.THRESH_OTSU if limiar == 0 else 0)
        _, th = cv2.threshold(img, limiar, 255, flags)
        return th

    # ── HISTOGRAMA / EQUALIZAÇÃO ─────────────────────────────────────────────

    @staticmethod
    def hist(img):
        """Histograma da imagem."""
        H = np.zeros(int(img.max()) + 1, dtype=int)
        for v in img.flatten(): H[v] += 1
        return H

    @staticmethod
    def histPlus(img):
        """Histograma e dicionário de pixels por cor."""
        H = np.zeros(int(img.max()) + 1, dtype=int)
        vet = {}
        for i, cor in enumerate(img.flatten()):
            H[cor] += 1
            vet.setdefault(str(cor), []).append(i)
        return H, vet

    @staticmethod
    def equalizacao(image):
        """Equalização pelo valor máximo."""
        h = mm.hist(image)
        prob = h / h.sum()
        soma = np.cumsum(prob) * image.max()
        soma = np.round(soma)
        l, c = image.shape
        out = np.vectorize(lambda v: soma[v])(image)
        return out.astype('int')

    # ── ELEMENTOS ESTRUTURANTES ───────────────────────────────────────────────

    @staticmethod
    def sesum(b, n=0):
        """Soma de Minkowski nB."""
        def _s(nb, b):
            h, w = b.shape
            nbh, nbw = nb.shape
            H = nbh+h-1 if h%2 else nbh+h
            W = nbw+w-1 if w%2 else nbw+w
            r = np.zeros((H, W), dtype='uint8')
            r[h//3:-(h//3), w//3:-(w//3)] = nb
            return cv2.dilate(r, b).astype('uint8')
        B = b.copy()
        for _ in range(n): B = _s(B, b)
        return B

    @staticmethod
    def sebox(n=0):   return mm.sesum(np.ones((3,3), dtype='uint8'), n)
    @staticmethod
    def secross(n=0):
        B = np.ones((3,3), dtype='uint8')
        B[0,0]=B[0,2]=B[2,0]=B[2,2]=0
        return mm.sesum(B, n)
    @staticmethod
    def sedisk(n=3):  return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n,n))

    # ── VIZINHANÇA (helper interno) ───────────────────────────────────────────

    @staticmethod
    def _viz(f, B, y, x):
        """Gera (vy, vx, b_val) para cada vizinho válido de (y,x)."""
        H, W = f.shape
        Bh, Bw = B.shape
        for by in range(Bh):
            for bx in range(Bw):
                vy = int(y + by - Bh/2 + 0.5)
                vx = int(x + bx - Bw/2 + 0.5)
                if 0 <= vy < H and 0 <= vx < W:
                    yield vy, vx, B[by, bx]

    # ── EROSÃO / DILATAÇÃO ───────────────────────────────────────────────────

    @staticmethod
    def ero(f, Bc=np.zeros((3,3),dtype='uint8')):
        """Erosão (OpenCV ou com pesos)."""
        try:    return cv2.erode(f, Bc)
        except: return mm.ero1(f, Bc)

    @staticmethod
    def dil(f, Bc=np.zeros((3,3),dtype='uint8')):
        """Dilatação (OpenCV ou com pesos)."""
        try:    return cv2.dilate(f, Bc)
        except: return mm.dil1(f, Bc)

    @staticmethod
    def ero0(f, Bc=np.zeros((3,3),dtype='uint8')):
        """Erosão sem pesos."""
        g = f.copy()
        for y in range(f.shape[0]):
            for x in range(f.shape[1]):
                for vy,vx,bv in mm._viz(f,Bc,y,x):
                    if bv and g[y,x] > f[vy,vx]: g[y,x] = f[vy,vx]
        return g

    @staticmethod
    def dil0(f, Bc=np.zeros((3,3),dtype='uint8')):
        """Dilatação sem pesos."""
        g = f.copy()
        for y in range(f.shape[0]):
            for x in range(f.shape[1]):
                for vy,vx,bv in mm._viz(f,Bc,y,x):
                    if bv and g[y,x] < f[vy,vx]: g[y,x] = f[vy,vx]
        return g

    @staticmethod
    def ero1(f, b=np.zeros((3,3),dtype='uint8')):
        """Erosão com pesos: mínimo de f[viz]-b."""
        g = f.copy()
        for y in range(f.shape[0]):
            for x in range(f.shape[1]):
                for vy,vx,bv in mm._viz(f,b,y,x):
                    if g[y,x] > f[vy,vx]-bv: g[y,x] = f[vy,vx]-bv
        return g

    @staticmethod
    def dil1(f, b=np.zeros((3,3),dtype='uint8')):
        """Dilatação com pesos: máximo de f[viz]+b."""
        g = f.copy()
        for y in range(f.shape[0]):
            for x in range(f.shape[1]):
                for vy,vx,bv in mm._viz(f,b,y,x):
                    if g[y,x] < f[vy,vx]+bv: g[y,x] = f[vy,vx]+bv
        return g

    # ── OPERADORES MORFOLÓGICOS ──────────────────────────────────────────────

    @staticmethod
    def gradm(f, b=np.zeros((3,3),dtype='uint8')):
        """Gradiente morfológico: dil(f,b) - ero(f,b)."""
        return mm.subm(mm.dil(f,b), mm.ero(f,b))

    @staticmethod
    def open(f, b=np.zeros((3,3),dtype='uint8')):
        return cv2.morphologyEx(f, cv2.MORPH_OPEN, b)

    @staticmethod
    def close(f, b=np.zeros((3,3),dtype='uint8')):
        return cv2.morphologyEx(f, cv2.MORPH_CLOSE, b)

    @staticmethod
    def openth(f, b=np.zeros((3,3),dtype='uint8')):
        return mm.subm(f, cv2.morphologyEx(f, cv2.MORPH_OPEN, b))

    @staticmethod
    def openth1(f, b=np.zeros((3,3),dtype='uint8')):
        return mm.subm(f, mm.dil1(mm.ero1(f,b), b))

    @staticmethod
    def closeth(f, b=np.zeros((3,3),dtype='uint8')):
        return mm.subm(cv2.morphologyEx(f, cv2.MORPH_CLOSE, b), f)

    @staticmethod
    def closerecth(f, b=np.zeros((3,3),dtype='uint8')):  # alias
        return mm.closeth(f, b)

    @staticmethod
    def asf(f, filter='OC', b=np.zeros((3,3),dtype='uint8'), n=1):
        """Filtro sequencial alternado. filter: 'OC','CO','OCO','COC'."""
        seqs = {'OC':[cv2.MORPH_OPEN,cv2.MORPH_CLOSE],
                'CO':[cv2.MORPH_CLOSE,cv2.MORPH_OPEN],
                'OCO':[cv2.MORPH_OPEN,cv2.MORPH_CLOSE,cv2.MORPH_OPEN],
                'COC':[cv2.MORPH_CLOSE,cv2.MORPH_OPEN,cv2.MORPH_CLOSE]}
        y = f.copy()
        for i in range(n):
            bi = mm.sesum(b, i)
            for op in seqs.get(filter.upper(), []):
                y = cv2.morphologyEx(y, op, bi)
        return y

    # ── RECONSTRUÇÃO ─────────────────────────────────────────────────────────

    @staticmethod
    def cero(f, g, b=np.zeros((3,3),dtype='uint8'), n=1):
        """Erosão condicional de g com máximo f, n vezes."""
        y = np.maximum(f, g)
        for _ in range(n): y = np.maximum(cv2.erode(y,b), g)
        return y

    @staticmethod
    def cdil(f, g, b=np.zeros((3,3),dtype='uint8'), n=1):
        """Dilatação condicional de g com mínimo f, n vezes."""
        y = np.minimum(f, g)
        for _ in range(n): y = np.minimum(cv2.dilate(y,b), g)
        return y

    @staticmethod
    def infrec(f, g, b=np.zeros((3,3),dtype='uint8')):
        """Inf-reconstrução: dilata g ∧ f até convergir."""
        y, y1 = np.minimum(f,g), np.zeros_like(f)
        while not np.array_equal(y, y1):
            y1 = y; y = np.minimum(cv2.dilate(y,b), g)
        return y

    @staticmethod
    def suprec(f, g, b=np.zeros((3,3),dtype='uint8')):
        """Sup-reconstrução: erode g ∨ f até convergir."""
        y, y1 = np.maximum(f,g), np.ones_like(f)*255
        while not np.array_equal(y, y1):
            y1 = y; y = np.maximum(cv2.erode(y,b), g)
        return y

    @staticmethod
    def closerec(f, b=np.zeros((3,3),dtype='uint8'), bc=np.zeros((3,3),dtype='uint8')):
        return mm.suprec(f, mm.dil(f,b), bc)

    @staticmethod
    def areaopen(f, a):
        """Remove componentes com área ≤ a."""
        def _ao(f, a):
            y = np.zeros(f.shape, dtype=int)
            if mm.binary(f):
                n, lbl = cv2.connectedComponents(f)
                for i in range(1, n):
                    area = np.sum(lbl==i)
                    if area > a: y[lbl==i] = area
            else:
                hist, _ = np.histogram(f.ravel(), 256, [0,256])
                for cor, h in enumerate(hist):
                    if h and cor:
                        _, fc = cv2.threshold(f, cor, 255, cv2.THRESH_BINARY)
                        fo = _ao(fc, a)
                        if fo.max()==0: break
                        y += fo
            return y
        return _ao(f, a)

    # ── REGIÕES / RÓTULOS ─────────────────────────────────────────────────────

    @staticmethod
    def regmax(f, b=np.ones((3,3),dtype='uint8')):
        k = 255 if f.max()<=255 else 65535
        return mm.union(mm.threshold(mm.subm(f, mm.infrec(mm.subm(f,1),f,b)),0),
                        mm.threshold(f,k))

    @staticmethod
    def regmin(f, b=np.ones((3,3),dtype='uint8')):
        return mm.union(mm.threshold(mm.subm(mm.suprec(mm.addm(f,1),f,b),f),1),
                        mm.threshold(f,0))

    @staticmethod
    def label(f):
        _, lbl = cv2.connectedComponents(f); return lbl

    @staticmethod
    def label0(f, b=np.ones((3,3),dtype='uint8')):
        """Rotulagem por flood-fill com pilha."""
        h, w = f.shape
        g = np.zeros(f.shape, dtype=int)
        cor = 1
        for x in range(h):
            for y in range(w):
                if f[x,y] and not g[x,y]:
                    pilha = [[x,y]]
                    while pilha:
                        i,j = pilha.pop(); g[i,j] = cor
                        for vy,vx,bv in mm._viz(f,b,i,j):
                            if bv and f[vy,vx] and not g[vy,vx]:
                                pilha.append([vy,vx])
                    cor += 1
        return g

    # ── WATERSHED ────────────────────────────────────────────────────────────

    @staticmethod
    def water0(f, b=np.zeros((3,3),dtype='uint8'), op='region'):
        f = mm.label0(f, b); g = f.copy()
        while g.min()==0:
            for x in range(f.shape[0]):
                for y in range(f.shape[1]):
                    for vy,vx,_ in mm._viz(f,b,x,y):
                        if g[x,y]==0 and g[x,y]<f[vy,vx]: g[x,y]=f[vy,vx]
            f = g.copy()
        return g if op=='region' else mm.gradm(g, mm.secross())

    @staticmethod
    def waterB(f, m, b=np.zeros((3,3),dtype='uint8'), op='region'):
        m = mm.label0(m, b); h,w = m.shape; queue=[]
        for x in range(h):
            for y in range(w):
                if m[x,y]:
                    for vy,vx,_ in mm._viz(f,b,x,y):
                        if not m[vy,vx]:
                            queue.append([abs(int(f[x,y])-int(f[vy,vx])),x,y])
        while queue:
            _,x,y = queue.pop(0); cor = m[x,y]
            for vy,vx,_ in mm._viz(f,b,x,y):
                if not m[vy,vx]:
                    m[vy,vx]=cor
                    queue.append([abs(int(f[x,y])-int(f[vy,vx])),vy,vx])
        return m if op=='region' else mm.gradm(m, mm.secross())

    @staticmethod
    def watershed(f, mark, op='region'):
        mark = mark*255 if mark.max()==1 else mark
        if len(f):
            _, markers = cv2.connectedComponents(mark)
            w = cv2.watershed(f, markers)
            if op=='line': f[markers==-1]=[255,0,0]; return f
            return w
        from scipy import ndimage as ndi
        from skimage.segmentation import watershed
        fones = np.ones_like(mark)*255
        w = watershed(fones, ndi.label(mark)[0], mask=fones)
        if op=='line':
            return np.array((w-cv2.erode(w.astype('uint16'),mm.sebox()))>0,dtype='uint16')
        return w

    # ── DISTÂNCIA / ESQUELETO ─────────────────────────────────────────────────

    @staticmethod
    def dist(f):
        y = cv2.distanceTransform(f, cv2.DIST_L2, 5)
        return y.astype('uint8') if y.max()<=255 else y.astype('uint16')

    @staticmethod
    def dist1(f, b):
        g = f.copy()
        while True:
            f=g.copy(); g=mm.ero1(g,b)
            if np.array_equal(f,g): break
        return g

    @staticmethod
    def gdist(f, g, b=np.ones((3,3),dtype='uint8')):
        h,w = f.shape; M=h*w
        fneg=(M-f*M).astype('uint16'); gneg=(1-g).astype('uint16')
        y,c = gneg,0
        while c<2000:
            c+=1; y0=y
            y = np.logical_xor(gneg,fneg)*(y+mm.cero(gneg,fneg,b,c))
            if np.array_equal(y0,y): break
        return y

    @staticmethod
    def thin(f):
        from skimage.morphology import skeletonize
        return np.array(skeletonize(f), dtype='uint8')

    @staticmethod
    def skel(f): return cv2.ximgproc.thinning(f)

    def skelm(f, b=np.zeros((3,3),dtype='uint8')):
        img=f.copy(); skel=np.zeros(f.shape); n=0
        while img.max():
            nb=mm.sesum(b,n); ero=mm.ero1(img,nb)
            skel=np.maximum(skel, ero-mm.dil1(mm.ero1(ero,b),b)); n+=1
        return skel

    def esqueleto(f, b):
        """Esqueleto alternativo (lista3 2022.1)."""
        img=f.copy(); skel=np.zeros(f.shape); n=0
        while img.max():
            abertura=mm.dil1(mm.ero1(img,b),b)
            skel=np.logical_or(skel,np.logical_and(img,np.logical_not(abertura))).astype(int)
            img=mm.ero1(img,mm.sesum(b,n)); n+=1
        return skel

    # ── OUTRAS OPERAÇÕES ──────────────────────────────────────────────────────

    @staticmethod
    def frame(f, border=5):
        g=np.ones_like(f)*255; g[border:-border,border:-border]=0; return g

    def edgeoff(f, b=np.ones((3,3),dtype='uint8')):
        return mm.subm(f, mm.infrec(mm.frame(f),f,b))

    @staticmethod
    def clohole(f, b=np.ones((3,3),dtype='uint8')):
        return mm.neg(mm.infrec(mm.frame(f),mm.neg(f),b))

    def hmin(f, h, b=np.ones((3,3),dtype='uint8')):
        return mm.suprec(f, mm.addm(f,h), b)

    @staticmethod
    def toggle(f, f1, f2, op='gray'):
        mask = np.logical_and(mm.subm(f,f1)<=f, f<=mm.subm(f2,f))
        if op=='gray':
            t=mask.astype('uint8')*255
            return mm.union(mm.intersec(mm.neg(t),f1), mm.intersec(t,f2))
        return mask

    @staticmethod
    def correlacao0(f, kernel, bias):
        Bh,Bw = kernel.shape
        if Bh==Bw:
            H,W = f.shape[0]-Bh+1, f.shape[1]-Bw+1
            return np.array([[np.sum(f[i:i+Bh,j:j+Bw]*kernel)+bias
                              for j in range(W)] for i in range(H)]).astype(np.uint8)

    # ── BLOB / ANÁLISE DE COMPONENTES ────────────────────────────────────────

    @staticmethod
    def blob(f, op='area', border=1, precision=0.01, show='True'):
        """Topologia de componentes conexos.
        op: 'area','textLabel','textPer','textArea','box','rect',
            'circle','ellipse','convex','poly','line'"""
        if not mm.binary(f): return None
        measures = []
        color_img = cv2.cvtColor(f, cv2.COLOR_GRAY2RGB)
        cont, _ = cv2.findContours(f.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        if op == 'area':
            color_img = np.zeros_like(f, dtype='uint32')
            n, lbl = cv2.connectedComponents(f)
            for i in range(1, n):
                area = np.sum(lbl==i); measures.append(area); color_img[lbl==i]=area

        elif op in ('textLabel','textPer','textArea'):
            for k,c in enumerate(cont):
                x,y,w,h = cv2.boundingRect(c)
                val = (k+1) if op=='textLabel' else \
                      int(cv2.arcLength(c,True)) if op=='textPer' else int(cv2.contourArea(c))
                measures.append(val)
                cv2.putText(color_img,str(val),(x+w//3,y+h//3),
                            cv2.FONT_HERSHEY_SIMPLEX,0.2,(255,0,0),border,cv2.LINE_AA)

        else:
            for c in cont:
                if op=='box':
                    box=np.int0(cv2.boxPoints(cv2.minAreaRect(c)))
                    measures.append(box); cv2.drawContours(color_img,[box],0,(255,0,0),border)
                elif op=='rect':
                    r=cv2.boundingRect(c); measures.append(list(r))
                    cv2.rectangle(color_img,r[:2],(r[0]+r[2],r[1]+r[3]),(0,255,0),border)
                elif op=='circle':
                    (cx,cy),rad=cv2.minEnclosingCircle(c)
                    center,rad=(int(cx),int(cy)),int(rad); measures.append([center,rad])
                    cv2.circle(color_img,center,rad,(0,255,0),border)
                elif op=='ellipse':
                    e=cv2.fitEllipse(c); measures.append(e)
                    cv2.ellipse(color_img,e,(0,255,0),border)
                elif op=='convex':
                    hull=cv2.convexHull(c); measures.append(hull)
                    cv2.drawContours(color_img,[hull],0,(255,0,0),border)
                elif op=='poly':
                    approx=cv2.approxPolyDP(c,precision*cv2.arcLength(c,True),True)
                    measures.append(approx); cv2.drawContours(color_img,[approx],0,(255,0,0),border)
                elif op=='line':
                    e=cv2.fitEllipse(c); cv2.ellipse(color_img,e,(255,0,0),border)
                    cols=f.shape[1]; vx,vy,x,y=cv2.fitLine(c,cv2.DIST_L2,0,0.01,0.01)
                    lefty=int((-x*vy/vx)+y); righty=int(((cols-x)*vy/vx)+y)
                    measures.append([vx,vy,x,y])
                    cv2.line(color_img,(cols-1,righty),(0,lefty),(0,255,0),border)

        if show: mm.show(color_img); return color_img
        return measures

    @staticmethod
    def blobAll(f, border=1, precision=0.01, show='False'):
        """Todas as medidas topológicas por componente."""
        ops=['textLabel','textArea','textPer','box','rect','circle','ellipse','convex','poly','line']
        n, labels = cv2.connectedComponents(f)
        result = {k: [] for k in ops}
        for i in range(n):
            aux=np.zeros_like(labels,dtype='uint8'); aux[labels==i]=255
            for op in ops: result[op].append(mm.blob(aux,op,1,0.01,False)[0])
        return result

    @staticmethod
    def verifyBoundBox(object, center, matrix, width, height):
        """Verifica se centro do objeto está dentro do bounding box do gabarito."""
        correct = 0
        for v in matrix[matrix[:,0]==object]:
            p1=v[1:][:2]*[width,height]//1; p2=v[1:][2:]*[width,height]//1
            if (p1<np.array(center)).all() and (np.array(center)<p2).all(): correct+=1
        return correct