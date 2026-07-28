from PIL import Image
im = Image.open("all/cap01/imagens/fig-01-sim-limiarizacao.png")
w, h = im.size
dpi = im.info.get('dpi', (96, 96))
print(f"pixels: {w}x{h}  dpi: {dpi}  proporção h/w: {h/w:.2f}")
print(im.size, im.info.get('dpi'))