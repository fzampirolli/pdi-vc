"""Configuração do ambiente (OpenCV, morph.py e, opcionalmente, testsuite.py)."""
import os, sys, subprocess, importlib, urllib.request

OPENCV_VERSION = "5.0.0.93"
BASE_URL = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/morph"


def setup(testsuite=False):
    """Instala o OpenCV correto e baixa os módulos didáticos do curso."""

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
    print(f"✅ Ambiente pronto | morph {getattr(morph, '__version__', 'local')} "
          f"| OpenCV {cv2.__version__}")

    if testsuite:
        import testsuite
        print(f"TestSuite {testsuite.__version__}")