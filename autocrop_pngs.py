"""
Script standalone para remover bordas brancas de todos os PNGs
gerados em all/*/imagens/*.png — rode DEPOIS do pipeline principal.

Uso:
    python autocrop_pngs.py
    python autocrop_pngs.py --dry-run     # só mostra o que mudaria, sem salvar
    python autocrop_pngs.py --root outra_pasta
"""
import argparse
from pathlib import Path
from PIL import Image, ImageChops


def autocrop_white_borders(img_path: Path, bg_tolerance: int = 8, dry_run: bool = False) -> bool:
    try:
        img = Image.open(img_path).convert('RGB')
    except Exception as e:
        print(f'  ⚠ Não foi possível abrir {img_path.name}: {e}')
        return False

    bg = Image.new('RGB', img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg)
    diff = diff.point(lambda p: 255 if p > bg_tolerance else 0)
    bbox = diff.getbbox()

    if bbox is None:
        return False

    if bbox == (0, 0, img.width, img.height):
        return False  # já está no tamanho do conteúdo, nada a fazer

    if dry_run:
        print(f'  [dry-run] {img_path.name}: {img.size} -> bbox {bbox}')
        return True

    cropped = img.crop(bbox)
    cropped.save(img_path)
    print(f'  ✂ {img_path.name}: {img.size} -> {cropped.size}')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=str, default='all')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    root = Path(args.root)
    pngs = list(root.glob('cap*/imagens/*.png'))
    print(f'Encontrados {len(pngs)} PNGs em {root}/cap*/imagens/')

    changed = 0
    for png_path in pngs:
        if autocrop_white_borders(png_path, dry_run=args.dry_run):
            changed += 1

    print(f'\nTotal alterado: {changed}/{len(pngs)}')


if __name__ == '__main__':
    main()
