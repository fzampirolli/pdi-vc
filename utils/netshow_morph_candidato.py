import numpy as np


def netshow(model, x, track_types=None, cmap_conv="Blues", cmap_fc="Greens",
            ncols=4, dpi=170, figsize=None, titulo=None, subtitulo=None):
    """
    Executa um forward pass em `model` (nn.Module do PyTorch) e exibe,
    lado a lado e com estilo didático, o fluxo de ativações por camada
    — genérico para QUALQUER rede, sem precisar conhecer nomes específicos
    de camadas.

    Por padrão rastreia Conv2d, Linear e camadas de pooling (MaxPool2d/
    AvgPool2d); outros tipos podem ser adicionados via `track_types`.
    Cada painel é colorido pelo TIPO da camada (não pelo nome), então a
    função funciona igual para uma CNNDigitos, uma MLP ou qualquer outra
    arquitetura:
        entrada -> bege | Conv2d -> azul | Pool -> cinza
        Linear -> verde | saída -> vermelho

    Parâmetros:
        model       : nn.Module já instanciado
        x           : tensor de entrada (formato aceito por model.forward)
        track_types : tupla de tipos de camada a capturar (opcional;
                      padrão = Conv2d, Linear, MaxPool2d, AvgPool2d)
        cmap_conv   : colormap para mapas de ativação espaciais (conv/pool)
        cmap_fc     : colormap para vetores de camadas densas
        ncols       : nº de colunas no mosaico de cada camada espacial
        titulo      : título geral da figura (opcional)
        subtitulo   : subtítulo/legenda (opcional)

    Retorna:
        dict com as ativações capturadas, por nome de camada.
    """
    import torch
    import torch.nn as nn
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    track_types = track_types or (nn.Conv2d, nn.Linear, nn.MaxPool2d, nn.AvgPool2d)

    PALETA = {
        "entrada": dict(bg="#F1EAD7", edge="#C9B98A"),
        "Conv2d":  dict(bg="#EAF2FA", edge="#2F6F9F"),
        "MaxPool2d": dict(bg="#FAFAF7", edge="#C9C2AE"),
        "AvgPool2d": dict(bg="#FAFAF7", edge="#C9C2AE"),
        "Linear":  dict(bg="#EAF7EE", edge="#4E9A66"),
        "saida":   dict(bg="#FCE8E6", edge="#C1443A"),
    }

    # -------- captura das ativações via hooks --------
    # Usa lista (não dict) porque um mesmo módulo (ex.: self.pool) pode
    # ser reutilizado várias vezes no forward — cada chamada vira um
    # estágio próprio na visualização, na ordem real de execução.
    estagios_capturados, hooks = [], []

    def _hook(nome, tipo):
        def fn(_mod, _inp, out):
            estagios_capturados.append((nome, tipo, out.detach()))
        return fn

    for nome, modulo in model.named_modules():
        if isinstance(modulo, track_types):
            hooks.append(modulo.register_forward_hook(_hook(nome, type(modulo).__name__)))

    was_training = model.training
    model.eval()
    with torch.no_grad():
        saida = model(x)
    for h in hooks:
        h.remove()
    model.train(was_training)

    # -------- monta lista ordenada de estágios (com nomes únicos) --------
    contagem = {}
    estagios = [("entrada", x, "entrada")]
    for i, (nome, tipo, tensor) in enumerate(estagios_capturados):
        contagem[nome] = contagem.get(nome, 0) + 1
        rotulo = nome if contagem[nome] == 1 else f"{nome} #{contagem[nome]}"
        eh_ultima = (i == len(estagios_capturados) - 1)
        estagios.append((rotulo, tensor, "saida" if eh_ultima else tipo))
    ativacoes = {rotulo: tensor for rotulo, tensor, _ in estagios[1:]}

    n = len(estagios)
    fig = plt.figure(figsize=figsize or (2.7 * n, 3.4), dpi=dpi, facecolor="#FAFBFC")
    gs = fig.add_gridspec(1, n, wspace=0.55, left=0.02, right=0.985, top=0.72, bottom=0.08)
    axes = []

    for col, (nome, tensor, tipo) in enumerate(estagios):
        cor = PALETA.get(tipo, PALETA["Linear"])
        ax = fig.add_subplot(gs[0, col])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])
        arr = tensor.detach().cpu().numpy()[0]
        dim_txt = "×".join(str(d) for d in tensor.shape[1:]) or "1"
        ax.set_title(f"{nome}\n" + r"$\mathtt{" + dim_txt.replace("×", r"\times") + "}$",
                     fontsize=10.5, fontweight="bold", color="#1a2a3a", pad=14)

        if arr.ndim == 3:  # (C,H,W) -> mosaico de canais
            c, h, w = arr.shape
            rows = int(np.ceil(c / ncols))
            gap = 0.05
            cell_w = (1 - gap * (ncols + 1)) / ncols
            cell_h = (1 - gap * (rows + 1)) / rows
            vmin, vmax = arr.min(), arr.max()
            cmap = cmap_conv
            for i in range(c):
                r, cc = divmod(i, ncols)
                x0 = gap + cc * (cell_w + gap)
                y0 = 1 - gap - (r + 1) * cell_h - r * gap
                sub = ax.inset_axes([x0, y0, cell_w, cell_h])
                sub.imshow(arr[i], cmap=cmap, vmin=vmin, vmax=vmax)
                sub.set_xticks([]); sub.set_yticks([])
                for s in sub.spines.values():
                    s.set_edgecolor("#ffffff"); s.set_linewidth(0.6)
        elif tipo == "saida":  # última camada -> gráfico de barras
            vals = arr.ravel()
            sub = ax.inset_axes([0.05, 0.05, 0.90, 0.85])
            pred = int(np.argmax(vals))
            cores = [cor["edge"] if i == pred else "#E7B7B2" for i in range(len(vals))]
            sub.bar(range(len(vals)), vals, color=cores, edgecolor=cor["edge"], linewidth=0.6)
            sub.set_xticks(range(len(vals))); sub.set_xticklabels(range(len(vals)), fontsize=7)
            sub.set_yticks([])
            for s in ["top", "right", "left"]:
                sub.spines[s].set_visible(False)
            sub.axhline(0, color=cor["edge"], linewidth=0.5)
        elif arr.ndim == 1:  # vetor denso -> faixa 2D
            side_cols = min(8, len(arr))
            rows = int(np.ceil(len(arr) / side_cols))
            pad = np.full(rows * side_cols, np.nan)
            pad[:len(arr)] = arr
            sub = ax.inset_axes([0.10, 0.15, 0.80, 0.70])
            sub.imshow(pad.reshape(rows, side_cols), cmap=cmap_fc, aspect="auto")
            sub.set_xticks([]); sub.set_yticks([])
            for s in sub.spines.values():
                s.set_edgecolor(cor["edge"]); s.set_linewidth(1.2)
        else:  # entrada 2D (imagem)
            sub = ax.inset_axes([0.15, 0.05, 0.70, 0.90])
            sub.imshow(arr.squeeze(), cmap="gray_r")
            sub.set_xticks([]); sub.set_yticks([])
            for s in sub.spines.values():
                s.set_edgecolor(cor["edge"]); s.set_linewidth(1.5)

        axes.append(ax)

    # -------- setas entre estágios --------
    fig.canvas.draw()
    for a, b in zip(axes[:-1], axes[1:]):
        pa, pb = a.get_position(), b.get_position()
        y = (pa.y0 + pa.y1) / 2 + 0.02
        fig.patches.append(FancyArrowPatch(
            (pa.x1 + 0.003, y), (pb.x0 - 0.003, y),
            transform=fig.transFigure, arrowstyle="-|>", mutation_scale=14,
            linewidth=1.4, color="#8ba9c4", shrinkA=0, shrinkB=0, zorder=10))

    if titulo:
        fig.suptitle(titulo, fontsize=14.5, fontweight="bold", color="#1a2a3a", y=0.97)
    if subtitulo:
        fig.text(0.5, 0.90, subtitulo, ha="center", fontsize=10.5,
                  color="#4a5a6a", style="italic")

    plt.show()
    return ativacoes


# ---------------------------------------------------------------
# Teste com a CNNDigitos do capítulo — reproduz a fig-09
# ---------------------------------------------------------------
if __name__ == "__main__":
    import torch
    import torch.nn as nn
    from sklearn.datasets import load_digits

    class CNNDigitos(nn.Module):
        def __init__(self, n_classes=10):
            super().__init__()
            self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
            self.conv2 = nn.Conv2d(8, 16, 3, padding=1)
            self.pool = nn.MaxPool2d(2, 2)
            self.fc1 = nn.Linear(16 * 2 * 2, 32)
            self.fc2 = nn.Linear(32, n_classes)
            self.relu = nn.ReLU()

        def forward(self, x):
            x = self.pool(self.relu(self.conv1(x)))
            x = self.pool(self.relu(self.conv2(x)))
            x = x.view(x.size(0), -1)
            x = self.relu(self.fc1(x))
            return self.fc2(x)

    torch.manual_seed(7)
    digits = load_digits()
    idx = np.where(digits.target == 3)[0][0]
    img = digits.images[idx] / 16.0
    x = torch.tensor(img, dtype=torch.float32).view(1, 1, 8, 8)

    modelo = CNNDigitos()
    acts = netshow(
        modelo, x,
        titulo="Fluxo de transformações dimensionais dos tensors ao longo da arquitetura CNNDigitos",
        subtitulo=f"Exemplo real do dataset load_digits (classe verdadeira: {digits.target[idx]})",
    )
    print("Camadas capturadas:", list(acts.keys()))
