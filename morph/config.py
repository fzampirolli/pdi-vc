"""Configuração do ambiente (OpenCV, morph.py e, opcionalmente, testsuite.py)."""
import os, sys, subprocess, importlib, urllib.request

BASE_URL = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/morph"

OPENCV_PACKAGE = "opencv-contrib-python"   # antes: "opencv-python" — Haar/HOG (CascadeClassifier)
OPENCV_VERSION = "5.0.0.93"                # foram movidos para opencv_contrib no OpenCV 5.0

def setup(testsuite=False, demo=False):
    try:
        import cv2
        assert cv2.__version__ == "5.0.0" and hasattr(cv2, "CascadeClassifier") \
               and cv2.CascadeClassifier is not None
    except (ImportError, AssertionError, AttributeError):
        # remove qualquer instalação conflitante antes de instalar a versão com contrib
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q",
                         "opencv-python", "opencv-python-headless",
                         "opencv-contrib-python", "opencv-contrib-python-headless"])
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                         f"{OPENCV_PACKAGE}=={OPENCV_VERSION}"], check=True)
        for mod in list(sys.modules):
            if mod == "cv2" or mod.startswith("cv2."):
                del sys.modules[mod]
        import cv2
        if cv2.__version__ != "5.0.0" or getattr(cv2, "CascadeClassifier", None) is None:
            raise RuntimeError(
                "OpenCV com suporte a CascadeClassifier instalado, mas a sessão "
                "ainda está usando a versão antiga carregada em memória.\n"
                "➜ Reinicie o kernel/runtime e execute a célula novamente."
            )

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