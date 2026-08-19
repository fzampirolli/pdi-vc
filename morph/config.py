"""Configuração do ambiente (OpenCV, morph.py e, opcionalmente, testsuite.py)."""
import os, sys, subprocess, importlib, urllib.request

BASE_URL = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/morph"

OPENCV_PACKAGE = "opencv-contrib-python"   # antes: "opencv-python" — Haar/HOG (CascadeClassifier)
OPENCV_VERSION = "5.0.0.93"                # foram movidos para opencv_contrib no OpenCV 5.0


def _opencv_ok():
    """Verifica se o cv2 já carregado em memória é a versão/variante correta."""
    try:
        import cv2
        return (
            cv2.__version__ == "5.0.0"
            and hasattr(cv2, "CascadeClassifier")
            and cv2.CascadeClassifier is not None
        )
    except (ImportError, AssertionError, AttributeError):
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


def _restart_colab_if_possible():
    """No Colab, reinicia o runtime automaticamente. Fora do Colab, apenas avisa."""
    try:
        from google.colab import runtime  # só existe no Colab
        print(
            "🔄 OpenCV foi atualizado, mas a versão antiga já estava carregada em memória.\n"
            "   Reiniciando o runtime automaticamente — após reiniciar, execute a célula novamente."
        )
        runtime.unassign()
    except ImportError:
        raise RuntimeError(
            "OpenCV com suporte a CascadeClassifier foi instalado, mas a sessão "
            "ainda está usando a versão antiga carregada em memória.\n"
            "➜ Reinicie o kernel/runtime manualmente e execute a célula novamente."
        )


def setup(testsuite=False, demo=False):
    # 1. OpenCV: garante versão e variante corretas
    if not _opencv_ok():
        _install_opencv()
        if not _opencv_ok():
            # Extensões C não podem ser "recarregadas a quente" no mesmo processo.
            # É necessário reiniciar o runtime/kernel para que o novo binário seja usado.
            _restart_colab_if_possible()
            return  # nunca alcançado localmente (RuntimeError interrompe antes)

    import cv2  # já garantido correto neste ponto

    # 2. Módulos didáticos (baixa só se ainda não existirem)
    files = ["morph.py"] + (["testsuite.py"] if testsuite else [])
    for f in files:
        if not os.path.exists(f):
            try:
                urllib.request.urlretrieve(f"{BASE_URL}/{f}", f)
            except Exception as e:
                if not os.path.exists(f):
                    raise RuntimeError(f"Não foi possível baixar {f}.") from e
                print(f"⚠️ Falha ao atualizar {f} ({e}); usando cópia local.")

    import morph
    status = f"✅ Ambiente pronto. Morph: {getattr(morph, '__version__', 'local')} | OpenCV: {cv2.__version__}"

    if testsuite:
        import testsuite
        status += f" | TestSuite: {testsuite.__version__}"

    print(status)

    if demo:
        import numpy as np
        img = np.array([[[200, 100, 50]]], dtype=np.uint8)
        print("\n── Convenções de escala por biblioteca ──")
        print(f"  NumPy / Pillow / OpenCV (uint8): {img[0,0]} → [0, 255]")
        print(f"  scikit-image / PyTorch (float):  {img[0,0] / 255.0} → [0.0, 1.0]")
        print(f"  OpenCV: atenção — lê em BGR:     {img[0,0,::-1]} (canais invertidos)")