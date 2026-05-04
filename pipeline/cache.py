"""
pipeline/cache.py
=================
Cache de traduções em disco (JSON).

Garante que o mesmo bloco de texto ou código não seja retraduzido
desnecessariamente entre execuções.  A chave de cache é um hash SHA-256
do conteúdo original + parâmetros de tradução.

Localização padrão: .cache/translations.json
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CACHE_FILE = Path('.cache') / 'translations.json'


class TranslationCache:
    def __init__(self, path: Path = DEFAULT_CACHE_FILE):
        self.path = path
        self._data: dict[str, str] = {}
        self._dirty = False
        self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self):
        if self._dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            self._dirty = False

    # ── Operações ─────────────────────────────────────────────────────────────

    @staticmethod
    def _key(source: str, kind: str, src_lang: str, tgt_lang: str) -> str:
        """Chave determinística: hash(conteúdo + parâmetros)."""
        raw = f'{kind}|{src_lang}→{tgt_lang}|{source}'
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, source: str, kind: str, src_lang: str, tgt_lang: str) -> Optional[str]:
        return self._data.get(self._key(source, kind, src_lang, tgt_lang))

    def set(self, source: str, kind: str, src_lang: str, tgt_lang: str, result: str):
        k = self._key(source, kind, src_lang, tgt_lang)
        if self._data.get(k) != result:
            self._data[k] = result
            self._dirty = True

    def stats(self) -> dict:
        return {'entries': len(self._data), 'path': str(self.path)}
