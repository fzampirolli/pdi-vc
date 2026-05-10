# scripts/patch_simuladores.py
import nbformat
import shutil
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path('backups') / datetime.now().strftime('%Y%m%d_%H%M%S')

for nb_path in Path('all').rglob('*.ipynb'):
    nb = nbformat.read(nb_path, as_version=4)
    modified = False

    for cell in nb.cells:
        if cell.cell_type != 'code':
            continue
        if 'HTML("""' not in cell.source and "HTML('''" not in cell.source:
            continue
        if 'QUARTO_FMT' in cell.source:  # já tem guard
            continue

        cell.source = (
            'import os\n'
            'from IPython.display import HTML, Markdown\n'
            '_fmt = os.environ.get("QUARTO_FMT", "html")\n'
            'if _fmt != "pdf":\n'
            + '\n'.join('    ' + line for line in cell.source.splitlines())
            + '\nelse:\n'
            '    display(Markdown("*Simulador interativo disponível na '
            '[versão HTML](https://fzampirolli.github.io/pdi-vc/).*"))\n'
        )
        modified = True

    if modified:
        # Backup mantendo estrutura de diretórios
        backup_path = BACKUP_DIR / nb_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nb_path, backup_path)
        print(f'  💾 Backup: {backup_path}')

        nbformat.write(nb, nb_path)
        print(f'  ✓ Patched: {nb_path}')

print(f'\nBackups em: {BACKUP_DIR}')
