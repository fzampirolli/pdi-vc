"""Configuração do ambiente (OpenCV, morph.py e, opcionalmente, testsuite.py)."""
import os, sys, subprocess, importlib, urllib.request

BASE_URL = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/morph"

OPENCV_PACKAGE = "opencv-contrib-python"   # antes: "opencv-python" — Haar/HOG (CascadeClassifier)
OPENCV_VERSION = "5.0.0.93"                # foram movidos para opencv_contrib no OpenCV 5.0

# Idioma das mensagens impressas por este módulo. Durante o build do livro,
# o pipeline (pipeline/quarto_builder.py) define PDI_VC_LOCALE conforme o
# locale do combo sendo renderizado (pt/en/fr/it/es); fora do pipeline
# (Colab, execução local avulsa), o padrão é "pt".
LOCALE = os.environ.get("PDI_VC_LOCALE", "pt")

_MESSAGES = {
    "pt": {
        "env_ready":         "✅ Ambiente pronto. Morph: {morph} | OpenCV: {cv2}",
        "testsuite_suffix":  " | TestSuite: {testsuite}",
        "download_fail":     "Não foi possível baixar {file}.",
        "download_fallback": "⚠️ Falha ao atualizar {file} ({error}); usando cópia local.",
        "restart_needed":    "OpenCV foi instalado corretamente, mas a versão antiga já estava "
                             "carregada em memória.\n"
                             "➜ Reinicie o kernel/runtime e execute a célula novamente.",
        "colab_restart":     "🔄 OpenCV foi atualizado, mas a versão antiga já estava carregada em memória.\n"
                             "   Desconectando o runtime automaticamente — após reconectar, execute a célula novamente.",
        "demo_header":       "── Convenções de escala por biblioteca ──",
        "demo_numpy":        "  NumPy / Pillow / OpenCV (uint8): {val} → [0, 255]",
        "demo_skimage":      "  scikit-image / PyTorch (float):  {val} → [0.0, 1.0]",
        "demo_bgr":          "  OpenCV: atenção — lê em BGR:     {val} (canais invertidos)",
    },
    "en": {
        "env_ready":         "✅ Environment ready. Morph: {morph} | OpenCV: {cv2}",
        "testsuite_suffix":  " | TestSuite: {testsuite}",
        "download_fail":     "Could not download {file}.",
        "download_fallback": "⚠️ Failed to update {file} ({error}); using local copy.",
        "restart_needed":    "OpenCV was installed correctly, but the old version was already "
                             "loaded in memory.\n"
                             "➜ Restart the kernel/runtime and run the cell again.",
        "colab_restart":     "🔄 OpenCV was updated, but the old version was already loaded in memory.\n"
                             "   Automatically disconnecting the runtime — after reconnecting, run the cell again.",
        "demo_header":       "── Scale conventions by library ──",
        "demo_numpy":        "  NumPy / Pillow / OpenCV (uint8): {val} → [0, 255]",
        "demo_skimage":      "  scikit-image / PyTorch (float):  {val} → [0.0, 1.0]",
        "demo_bgr":          "  OpenCV: watch out — reads as BGR: {val} (channels reversed)",
    },
    "fr": {
        "env_ready":         "✅ Environnement prêt. Morph : {morph} | OpenCV : {cv2}",
        "testsuite_suffix":  " | TestSuite : {testsuite}",
        "download_fail":     "Impossible de télécharger {file}.",
        "download_fallback": "⚠️ Échec de la mise à jour de {file} ({error}) ; utilisation de la copie locale.",
        "restart_needed":    "OpenCV a été installé correctement, mais l'ancienne version était déjà "
                             "chargée en mémoire.\n"
                             "➜ Redémarrez le kernel/runtime et exécutez à nouveau la cellule.",
        "colab_restart":     "🔄 OpenCV a été mis à jour, mais l'ancienne version était déjà chargée en mémoire.\n"
                             "   Déconnexion automatique du runtime — après reconnexion, exécutez à nouveau la cellule.",
        "demo_header":       "── Conventions d'échelle par bibliothèque ──",
        "demo_numpy":        "  NumPy / Pillow / OpenCV (uint8) : {val} → [0, 255]",
        "demo_skimage":      "  scikit-image / PyTorch (float) :  {val} → [0.0, 1.0]",
        "demo_bgr":          "  OpenCV : attention — lecture en BGR : {val} (canaux inversés)",
    },
    "es": {
        "env_ready":         "✅ Entorno listo. Morph: {morph} | OpenCV: {cv2}",
        "testsuite_suffix":  " | TestSuite: {testsuite}",
        "download_fail":     "No fue posible descargar {file}.",
        "download_fallback": "⚠️ Error al actualizar {file} ({error}); usando copia local.",
        "restart_needed":    "OpenCV se instaló correctamente, pero la versión anterior ya estaba "
                             "cargada en memoria.\n"
                             "➜ Reinicie el kernel/runtime y ejecute la celda nuevamente.",
        "colab_restart":     "🔄 OpenCV se actualizó, pero la versión anterior ya estaba cargada en memoria.\n"
                             "   Desconectando el runtime automáticamente — tras reconectar, ejecute la celda nuevamente.",
        "demo_header":       "── Convenciones de escala por biblioteca ──",
        "demo_numpy":        "  NumPy / Pillow / OpenCV (uint8): {val} → [0, 255]",
        "demo_skimage":      "  scikit-image / PyTorch (float):  {val} → [0.0, 1.0]",
        "demo_bgr":          "  OpenCV: atención — lee en BGR:   {val} (canales invertidos)",
    },
    "it": {
        "env_ready":         "✅ Ambiente pronto. Morph: {morph} | OpenCV: {cv2}",
        "testsuite_suffix":  " | TestSuite: {testsuite}",
        "download_fail":     "Impossibile scaricare {file}.",
        "download_fallback": "⚠️ Aggiornamento di {file} non riuscito ({error}); si usa la copia locale.",
        "restart_needed":    "OpenCV è stato installato correttamente, ma la versione precedente era già "
                             "caricata in memoria.\n"
                             "➜ Riavvia il kernel/runtime ed esegui di nuovo la cella.",
        "colab_restart":     "🔄 OpenCV è stato aggiornato, ma la versione precedente era già caricata in memoria.\n"
                             "   Disconnessione automatica del runtime — dopo la riconnessione, esegui di nuovo la cella.",
        "demo_header":       "── Convenzioni di scala per libreria ──",
        "demo_numpy":        "  NumPy / Pillow / OpenCV (uint8): {val} → [0, 255]",
        "demo_skimage":      "  scikit-image / PyTorch (float):  {val} → [0.0, 1.0]",
        "demo_bgr":          "  OpenCV: attenzione — legge in BGR: {val} (canali invertiti)",
    },
}


def _msg(key, **kwargs):
    table = _MESSAGES.get(LOCALE, _MESSAGES["pt"])
    template = table.get(key, _MESSAGES["pt"][key])
    return template.format(**kwargs)


def _opencv_ok():
    """Verifica o pacote sem carregar cv2 prematuramente."""
    from importlib.metadata import version, PackageNotFoundError

    # Se cv2 já foi carregado, somente ele pode validar a versão em memória.
    if "cv2" in sys.modules:
        try:
            import cv2
            return (
                cv2.__version__ == "5.0.0"
                and hasattr(cv2, "CascadeClassifier")
            )
        except (ImportError, AttributeError):
            return False

    # Se cv2 ainda não foi carregado, verifica apenas a versão instalada.
    try:
        return version(OPENCV_PACKAGE) == OPENCV_VERSION
    except PackageNotFoundError:
        return False



def _install_opencv():
    """Remove instalações conflitantes e instala a versão/variante correta."""
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "-q",
         "opencv-python", "opencv-python-headless",
         "opencv-contrib-python", "opencv-contrib-python-headless"]
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q",
         f"{OPENCV_PACKAGE}=={OPENCV_VERSION}"],
        check=True,
    )
    # Limpa o cache de módulos do lado Python (não desfaz o binário .so já carregado)
    for mod in list(sys.modules):
        if mod == "cv2" or mod.startswith("cv2."):
            del sys.modules[mod]


def _halt_for_restart():
    """
    Extensões C (.so) não podem ser recarregadas a quente no mesmo processo.
    É necessário reiniciar o runtime/kernel para usar o novo binário.

    No Colab, tenta desconectar automaticamente a VM. Em qualquer caso,
    interrompe a execução da célula IMEDIATAMENTE via exceção — chamar
    runtime.unassign() sozinho não basta, pois a desconexão é assíncrona
    e o código seguinte da célula continuaria rodando (e falhando) antes
    da VM ser efetivamente reiniciada.
    """
    msg = _msg("restart_needed")
    try:
        from google.colab import runtime
        print(_msg("colab_restart"))
        try:
            runtime.unassign()
        except Exception:
            pass  # segue para o raise abaixo de qualquer forma
    except ImportError:
        pass  # não é Colab; segue direto para o raise

    raise RuntimeError(msg)


def setup(testsuite=False, demo=False, cpp=False):
    # 1. OpenCV: garante versão e variante corretas
    if not _opencv_ok():
        _install_opencv()
        if not _opencv_ok():
            _halt_for_restart()  # sempre levanta exceção — nunca retorna

    import cv2  # já garantido correto neste ponto

    # 2. Módulos didáticos (baixa só se ainda não existirem)
    files = ["morph.py"] + (["testsuite.py"] if testsuite else [])
    for f in files:
        if not os.path.exists(f):
            try:
                urllib.request.urlretrieve(f"{BASE_URL}/{f}", f)
            except Exception as e:
                if not os.path.exists(f):
                    raise RuntimeError(_msg("download_fail", file=f)) from e
                print(_msg("download_fallback", file=f, error=e))

    # 2b. Headers C++ (morph.hpp + stb vendorizadas) — só se algum EP/célula
    #     do combo cpp precisar compilar com `#include "morph.hpp"`.
    if cpp:
        for f in ["morph.hpp", "stb_image.h", "stb_image_write.h"]:
            if not os.path.exists(f):
                try:
                    urllib.request.urlretrieve(f"{BASE_URL}/cpp/{f}", f)
                except Exception as e:
                    if not os.path.exists(f):
                        raise RuntimeError(_msg("download_fail", file=f)) from e
                    print(_msg("download_fallback", file=f, error=e))

    import morph
    status = _msg("env_ready", morph=getattr(morph, '__version__', 'local'), cv2=cv2.__version__)

    if testsuite:
        import testsuite
        status += _msg("testsuite_suffix", testsuite=testsuite.__version__)

    print(status)

    if demo:
        import numpy as np
        img = np.array([[[200, 100, 50]]], dtype=np.uint8)
        print(f"\n{_msg('demo_header')}")
        print(_msg("demo_numpy", val=img[0, 0]))
        print(_msg("demo_skimage", val=img[0, 0] / 255.0))
        print(_msg("demo_bgr", val=img[0, 0, ::-1]))
