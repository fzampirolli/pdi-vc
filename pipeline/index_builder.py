"""
pipeline/index_builder.py
=========================
Gera página principal minimalista com links para cada versão.
O index.html fica em gen/book/index.html (junto com as versões geradas).
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import List, Dict

from .config import LANGUAGES, LOCALES

DIR_GEN = Path('gen')
DIR_BOOK = DIR_GEN / 'book'


class IndexBuilder:
    """Constrói página principal com links para os índices de cada versão."""
    
    def __init__(self, project_root: Path = Path('.')):
        self.root = project_root.resolve()
        self.gen_dir = self.root / DIR_GEN
        self.book_dir = self.root / DIR_BOOK
        # ALTERADO: index agora fica dentro de book/
        self.index_path = self.book_dir / 'index.html'
    
    def scan_versions(self) -> List[Dict]:
        """Escaneia gen/book/ e retorna informações de cada versão."""
        versions = []
        
        if not self.book_dir.exists():
            return versions
        
        for combo_dir in sorted(self.book_dir.iterdir()):
            if not combo_dir.is_dir():
                continue
            
            # Pular o próprio index.html se existir
            if combo_dir.name == 'index.html':
                continue
            
            # Parse combo key: 'py.pt', 'cpp.en', etc.
            parts = combo_dir.name.split('.')
            if len(parts) != 2:
                continue
            
            lang_key, locale_key = parts
            
            # Get metadata from config
            lang_info = LANGUAGES.get(lang_key)
            locale_info = LOCALES.get(locale_key)
            
            if not lang_info or not locale_info:
                continue
            
            # Verifica se existe index.html
            index_file = combo_dir / 'index.html'
            has_index = index_file.exists()
            
            # Verifica se existe PDF completo
            pdf_file = combo_dir / f'{combo_dir.name}.pdf'
            has_pdf = pdf_file.exists()
            
            # ALTERADO: caminhos relativos a partir de book/
            index_relative = f"{combo_dir.name}/index.html"
            pdf_relative = f"{combo_dir.name}/{combo_dir.name}.pdf" if has_pdf else None
            
            versions.append({
                'key': combo_dir.name,
                'lang_key': lang_key,
                'lang_label': lang_info.label,
                'locale_key': locale_key,
                'locale_label': locale_info.label,
                'quarto_lang': locale_info.quarto_lang,
                'index_path': index_file,
                'index_relative': index_relative,
                'pdf_relative': pdf_relative,
                'has_index': has_index,
                'has_pdf': has_pdf,
                'last_modified': datetime.fromtimestamp(
                    combo_dir.stat().st_mtime
                )
            })
        
        return versions
    
    def generate_html(self, versions: List[Dict]) -> str:
        """Gera o HTML principal minimalista."""
        
        # Agrupa por linguagem
        by_lang = {}
        for v in versions:
            lang = v['lang_key']
            if lang not in by_lang:
                by_lang[lang] = []
            by_lang[lang].append(v)
        
        html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDI+VC — Livro Interativo</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 3rem;
        }}
        
        .header h1 {{
            font-size: 3rem;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        
        .header p {{
            font-size: 1.2rem;
            opacity: 0.95;
        }}
        
        .info-bar {{
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 2rem;
            color: white;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .info-item {{
            background: rgba(0,0,0,0.2);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
        }}
        
        .language-section {{
            background: white;
            border-radius: 12px;
            margin-bottom: 2rem;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .language-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 1.5rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .language-header:hover {{
            opacity: 0.95;
        }}
        
        .language-header h2 {{
            font-size: 1.5rem;
        }}
        
        .toggle-icon {{
            font-size: 1.5rem;
            transition: transform 0.3s;
        }}
        
        .language-header.collapsed .toggle-icon {{
            transform: rotate(-90deg);
        }}
        
        .versions-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
            padding: 1.5rem;
        }}
        
        .version-card {{
            background: #f8f9fa;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.3s, box-shadow 0.3s;
            border: 1px solid #e0e0e0;
            text-decoration: none;
            color: inherit;
            display: block;
        }}
        
        .version-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }}
        
        .version-header {{
            background: #4a5568;
            color: white;
            padding: 1.5rem;
            text-align: center;
        }}
        
        .version-header h3 {{
            font-size: 1.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .version-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.3);
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.8rem;
        }}
        
        .version-footer {{
            padding: 1rem;
            text-align: center;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            justify-content: center;
            gap: 1rem;
        }}
        
        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            font-size: 0.85rem;
            color: #4a5568;
        }}
        
        .badge-pdf {{
            color: #e53e3e;
        }}
        
        .footer {{
            text-align: center;
            color: white;
            margin-top: 3rem;
            padding: 1rem;
            border-top: 1px solid rgba(255,255,255,0.3);
        }}
        
        .footer a {{
            color: white;
            text-decoration: underline;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}
            
            .versions-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
    <script>
        function toggleSection(element) {{
            const header = element;
            const content = header.nextElementSibling;
            header.classList.toggle('collapsed');
            content.style.display = content.style.display === 'none' ? 'grid' : 'none';
        }}
        
        function expandAll() {{
            const sections = document.querySelectorAll('.versions-grid');
            const headers = document.querySelectorAll('.language-header');
            sections.forEach(section => section.style.display = 'grid');
            headers.forEach(header => header.classList.remove('collapsed'));
        }}
        
        function collapseAll() {{
            const sections = document.querySelectorAll('.versions-grid');
            const headers = document.querySelectorAll('.language-header');
            sections.forEach(section => section.style.display = 'none');
            headers.forEach(header => header.classList.add('collapsed'));
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📖 Processamento Digital de Imagens</h1>
            <h1 style="font-size: 2rem;">e Visão Computacional</h1>
            <p>Múltiplas linguagens e formatos para aprendizado acessível</p>
        </div>
        
        <div class="info-bar">
            <div class="info-item">📚 {len(versions)} versões disponíveis</div>
            <div class="info-item">💻 {len(set(v['lang_key'] for v in versions))} linguagens</div>
            <div class="info-item">🌐 {len(set(v['locale_key'] for v in versions))} idiomas</div>
            <div class="info-item">🕒 Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
            <div class="info-item">
                <button onclick="expandAll()" style="margin-right: 0.5rem; padding: 0.3rem 0.8rem;">📖 Expandir tudo</button>
                <button onclick="collapseAll()" style="padding: 0.3rem 0.8rem;">📕 Recolher tudo</button>
            </div>
        </div>
'''
        
        # Gera seções por linguagem
        for lang_key, versions_list in sorted(by_lang.items()):
            lang_label = versions_list[0]['lang_label']
            
            # Ícone para a linguagem
            lang_icons = {
                'py': '🐍',
                'cpp': '⚙️',
                'java': '☕',
                'c': '🔧',
                'rust': '🦀',
                'go': '🏃'
            }
            icon = lang_icons.get(lang_key, '💻')
            
            html += f'''
        <div class="language-section">
            <div class="language-header" onclick="toggleSection(this)">
                <h2>{icon} {lang_label}</h2>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="versions-grid" style="display: grid;">
'''
            
            for version in versions_list:
                # Link para o index.html da versão (relativo a partir de book/)
                index_link = version['index_relative'] if version['has_index'] else '#'
                
                html += f'''
                <a href="{index_link}" class="version-card" {"style='opacity:0.6; cursor:not-allowed;'" if not version['has_index'] else ""}>
                    <div class="version-header">
                        <h3>🌐 {version['locale_label']}</h3>
                        <div class="version-badge">{version['quarto_lang'].upper()}</div>
                    </div>
                    <div class="version-footer">
                        <span class="badge">📖 Acessar livro completo</span>
'''
                
                if version['has_pdf']:
                    pdf_link = version['pdf_relative']
                    html += f'''
                        <span class="badge badge-pdf">📄 PDF disponível</span>
                    </div>
                </a>
                <div style="text-align: center; margin-top: -0.5rem; margin-bottom: 0.5rem;">
                    <a href="{pdf_link}" style="font-size: 0.85rem; color: #e53e3e; text-decoration: none;">⬇️ Baixar PDF completo</a>
                </div>
'''
                else:
                    html += '''
                    </div>
                </a>
'''
            
            html += '''
            </div>
        </div>
'''
        
        html += f'''
        <div class="footer">
            <p>© {datetime.now().year} Francisco de Assis Zampirolli — UFABC</p>
            <p>Gerado automaticamente pelo pipeline PDI+VC | <a href="#" style="color: white;">Sobre</a> | <a href="#" style="color: white;">Documentação</a></p>
        </div>
    </div>
    
    <script>
        // Expande a primeira seção por padrão
        const firstGrid = document.querySelector('.versions-grid');
        if (firstGrid) firstGrid.style.display = 'grid';
    </script>
</body>
</html>
'''
        
        return html
    
    def build(self) -> Path:
        """Constrói a página index.html principal dentro de gen/book/."""
        # Garante que o diretório gen/book/ existe
        self.book_dir.mkdir(parents=True, exist_ok=True)
        
        versions = self.scan_versions()
        
        if not versions:
            print('⚠️ Nenhuma versão encontrada em gen/book/')
            print('   Execute o pipeline primeiro: make build LANGS=py,cpp LOCALES=pt,en')
            return self.index_path
        
        html_content = self.generate_html(versions)
        self.index_path.write_text(html_content, encoding='utf-8')
        
        print(f'✅ Página principal gerada: {self.index_path}')
        print(f'   📊 {len(versions)} versões encontradas')
        print(f'\n🌐 Abrir no navegador: file://{self.index_path.absolute()}')
        
        return self.index_path


# Para execução direta
if __name__ == '__main__':
    builder = IndexBuilder()
    builder.build()