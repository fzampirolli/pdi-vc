# sua solução
def calcular_metricas(verdades, confiancas, t):
    vp = fn = fp = vn = 0
    for v, c in zip(verdades, confiancas):
        pred = 1 if c >= t else 0
        if v == 1 and pred == 1: vp += 1
        elif v == 1 and pred == 0: fn += 1
        elif v == 0 and pred == 1: fp += 1
        else: vn += 1

    acc = (vp + vn) / len(verdades)
    prec = vp / (vp + fp) if (vp + fp) > 0 else 0.0
    sens = vp / (vp + fn) if (vp + fn) > 0 else 0.0
    f1 = (2 * prec * sens) / (prec + sens) if (prec + sens) > 0 else 0.0

    return vp, fn, fp, vn, acc, prec, sens, f1

n = int(input())

dados = []
for _ in range(n):
    v, c = input().split()
    dados.append((int(v), float(c)))

verdades = [d[0] for d in dados]
confiancas = [d[1] for d in dados]

limiares = [0.00, 0.09, 0.21, 0.31, 0.39, 0.52, 0.60, 0.71, 0.81, 0.89, 1.00]

# Métricas para o limiar 0.85
vp85, fn85, fp85, vn85, acc85, p85, s85, f185 = calcular_metricas(verdades, confiancas, 0.85)

print("# MÉTRICAS PARA O LIMIAR 0.85 #")
print(f"Matriz de Confusão:\nVP = {vp85}, FN = {fn85}\nFP = {fp85}, VN = {vn85}")
print(f"\nMétricas de Avaliação:\nAcurácia: {acc85:.2f}\nPrecisão: {p85:.2f}\nSensibilidade: {s85:.2f}\nF1-Score: {f185:.2f}")

# Métricas para todos os limiares
m = len(limiares)
raw_p = [0.0] * m
sens = [0.0] * m

for i in range(m):
    _, _, _, _, _, p, s, _ = calcular_metricas(verdades, confiancas, limiares[i])
    # Invertendo a ordem (limiar 1.0 -> índice 0 da curva P-S por causa da sensibilidade crescente)
    raw_p[m-1-i] = p
    sens[m-1-i] = s

prec_mono = raw_p.copy()
for i in range(m-2, -1, -1):
    if prec_mono[i] < prec_mono[i+1]:
        prec_mono[i] = prec_mono[i+1]

map_val = 0.0
for i in range(1, m):
    base = sens[i] - sens[i-1]
    altura_media = (prec_mono[i-1] + prec_mono[i]) / 2.0
    map_val += altura_media * base

print(f"\n# MÉTRICAS PARA TODOS OS LIMIARES\n")
print(f"Precisões: {', '.join([f'{x:.2f}' for x in raw_p])}")
print(f"Precisões mon.: {', '.join([f'{x:.2f}' for x in prec_mono])}")
print(f"Sensibilidades: {', '.join([f'{x:.2f}' for x in sens])}")
print(f"mAP: {map_val:.2f}")
