"""
pipeline/cache.py
=================
Cache de traduções em disco (JSON).

Garante que o mesmo bloco de texto ou código não seja retraduzido
desnecessariamente entre execuções.  A chave de cache é um hash SHA-256
do conteúdo original + parâmetros de tradução.

Localização padrão: .cache/translations.json

O arquivo é **estado semi-autoritativo do projeto** (traduções de LLM já
pagas + correções manuais promovidas via `dev.py --promote-edits`), por
isso as salvaguardas:

- **Escrita atômica** — `save()` grava num `.tmp` no mesmo diretório e
  `os.replace()` por cima; interrupção nunca deixa o JSON truncado.
- **Backup datado com rotação** — `backup()` copia pra
  `.cache/backups/translations.<timestamp>.json` (mantém os N mais
  recentes) antes de uma escrita arriscada.
- **Falha explícita em corrupção** — `_load()` NÃO cai em cache vazio
  silenciosamente: põe o arquivo inválido em quarentena
  (`translations.json.corrupt-<timestamp>`) e levanta `CacheCorruptError`.
- **Proveniência das correções manuais** — `set_raw(..., meta=...)`
  registra combo/capítulo/célula/data/trecho-fonte num bloco `__meta__`;
  `dev.py --audit-cache` usa isso pra avisar quando a fonte de uma
  correção manual mudou (entrada órfã) em vez de descartá-la calada.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_CACHE_FILE = Path('.cache') / 'translations.json'

# Chave reservada dentro do JSON pro bloco de proveniência das correções
# manuais. Nunca colide com uma chave de tradução (essas têm 32 hex).
META_KEY = '__meta__'


class CacheCorruptError(RuntimeError):
    """O cache em disco existe mas não pôde ser lido/decodificado.

    Levantada em vez de seguir com cache vazio: um cache vazio silencioso
    faz o próximo build retraduzir tudo (custo de API) e, no `save()`
    seguinte, sobrescrever o arquivo bom com `{}`. O arquivo original é
    preservado em quarentena antes de levantar.
    """


class TranslationCache:
    def __init__(self, path: Path = DEFAULT_CACHE_FILE, *, strict: bool = True):
        self.path = Path(path)
        self.strict = strict
        self._data: dict[str, str] = {}
        self._meta: dict[str, dict] = {}
        self._dirty = False
        self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self):
        if not self.path.exists():
            return
        try:
            text = self.path.read_text(encoding='utf-8')
        except OSError as e:
            if not self.strict:
                return
            raise CacheCorruptError(
                f'não consegui ler {self.path}: {e}. '
                f'Restaure de git ou de .cache/backups/.'
            ) from e
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise json.JSONDecodeError('raiz não é um objeto', text, 0)
        except json.JSONDecodeError as e:
            if not self.strict:
                self._data = {}
                return
            quarantine = self._quarantine()
            raise CacheCorruptError(
                f'{self.path} está corrompido (JSON inválido: {e}). '
                f'Bytes originais preservados em {quarantine}. '
                f'Restaure com  git checkout -- {self.path}  '
                f'ou copie o backup mais recente de .cache/backups/.'
            ) from e

        self._meta = data.pop(META_KEY, {}) or {}
        self._data = data

    def _quarantine(self) -> Path:
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        dst = self.path.with_name(f'{self.path.name}.corrupt-{ts}')
        self.path.rename(dst)
        return dst

    def _serialize(self) -> str:
        payload = dict(self._data)
        if self._meta:
            payload[META_KEY] = self._meta
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    def save(self):
        if self._dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Escrita atômica: grava num arquivo temporário no mesmo diretório
            # e renomeia por cima (os.replace é atômico em POSIX e Windows).
            # Uma interrupção durante a escrita nunca deixa o cache truncado.
            tmp = self.path.with_name(self.path.name + '.tmp')
            tmp.write_text(self._serialize(), encoding='utf-8')
            os.replace(tmp, self.path)
            self._dirty = False

    def backup(self, keep: int = 10) -> Optional[Path]:
        """Copia o cache atual pra `.cache/backups/translations.<timestamp>.json`
        antes de uma escrita arriscada (p.ex. a promoção de edições manuais).
        Mantém só os `keep` backups mais recentes. Devolve o caminho do
        backup, ou None se ainda não há cache em disco.

        Git continua sendo o histórico real; estes `.bak` são rede de
        curtíssimo prazo pra desfazer uma promoção ruim na hora.
        """
        if not self.path.exists():
            return None
        bdir = self.path.parent / 'backups'
        bdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        dst = bdir / f'{self.path.stem}.{ts}{self.path.suffix}'
        n = 1
        while dst.exists():  # duas promoções no mesmo segundo
            dst = bdir / f'{self.path.stem}.{ts}-{n}{self.path.suffix}'
            n += 1
        shutil.copy2(self.path, dst)
        stale = sorted(bdir.glob(f'{self.path.stem}.*{self.path.suffix}'))[:-keep]
        for f in stale:
            f.unlink()
        return dst

    # ── Operações ─────────────────────────────────────────────────────────────

    @staticmethod
    def key_for(source: str, kind: str, src_lang: str, tgt_lang: str) -> str:
        """Chave determinística: hash(conteúdo + parâmetros)."""
        raw = f'{kind}|{src_lang}→{tgt_lang}|{source}'
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, source: str, kind: str, src_lang: str, tgt_lang: str) -> Optional[str]:
        return self._data.get(self.key_for(source, kind, src_lang, tgt_lang))

    def set(self, source: str, kind: str, src_lang: str, tgt_lang: str, result: str):
        k = self.key_for(source, kind, src_lang, tgt_lang)
        if self._data.get(k) != result:
            self._data[k] = result
            self._dirty = True

    # ── Acesso direto por chave (usado pela promoção de edições manuais) ──────

    def get_raw(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set_raw(self, key: str, value: str, meta: Optional[dict] = None) -> bool:
        """Grava `value` na chave `key` já calculada. Retorna True se mudou
        algo. Se `meta` for dado, registra a proveniência da correção
        manual no bloco `__meta__` (com carimbo de data), pra que
        `--audit-cache` consiga avisar quando essa entrada ficar órfã.
        """
        changed = False
        if self._data.get(key) != value:
            self._data[key] = value
            changed = True
        if meta is not None:
            record = {**meta, 'promoted_at': datetime.now().isoformat(timespec='seconds')}
            if self._meta.get(key) != record:
                self._meta[key] = record
                changed = True
        if changed:
            self._dirty = True
        return changed

    # ── Introspecção / manutenção (usado por --audit-cache) ──────────────────

    def keys(self) -> set[str]:
        """Todas as chaves de tradução (sem o bloco __meta__)."""
        return set(self._data)

    def meta_for(self, key: str) -> Optional[dict]:
        return self._meta.get(key)

    def is_manual(self, key: str) -> bool:
        return self._meta.get(key, {}).get('kind') == 'manual'

    def drop(self, keys) -> int:
        """Remove entradas (e sua proveniência). Devolve quantas saíram."""
        n = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                self._meta.pop(k, None)
                n += 1
                self._dirty = True
        return n

    def stats(self) -> dict:
        return {'entries': len(self._data),
                'manual': sum(1 for k in self._meta if self.is_manual(k)),
                'path': str(self.path)}
