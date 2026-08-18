"""Configuração do ambiente (OpenCV, morph.py e, opcionalmente, testsuite.py)."""
import os, sys, subprocess, importlib, urllib.request

OPENCV_VERSION = "5.0.0.93"
BASE_URL = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/morph"


def setup(testsuite=False, demo=False):
    """Instala o OpenCV correto e baixa os módulos didáticos do curso.

    Parâmetros
    ----------
    testsuite : bool
        Se True, também baixa e importa testsuite.py.
    demo : bool
        Se True, imprime um exemplo das convenções de escala de pixel
        (uint8 x float, RGB x BGR) usadas pelas bibliotecas do curso.
    """

    # 1. OpenCV na versão exigida
    try:
        import cv2
        assert cv2.__version__ == "5.0.0"
    except (ImportError, AssertionError):
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                         f"opencv-python=={OPENCV_VERSION}"], check=True)
        import cv2

    # 2. Módulos didáticos (baixa só se ainda não existirem)
    files = ["morph.py"] + (["testsuite.py"] if testsuite else [])
    for f in files:
        if not os.path.exists(f):
            urllib.request.urlretrieve(f"{BASE_URL}/{f}", f)

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