"""Configuração do ambiente (OpenCV, morph.py e, opcionalmente, testsuite.py)."""
import os, sys, subprocess, importlib, urllib.request

OPENCV_VERSION = "5.0.0.93"
BASE_URL = "https://raw.githubusercontent.com/fzampirolli/pdi-vc/master/morph"

def setup(testsuite=False, demo=False):
    """Instala o OpenCV correto e baixa os módulos didáticos do curso."""

    # 1. OpenCV na versão exigida
    try:
        import cv2
    except ImportError:
        cv2 = None

    if cv2 is None or cv2.__version__ != "5.0.0":
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                         f"opencv-python=={OPENCV_VERSION}"], check=True)

        # tenta recarregar em memória (funciona quando o cv2 ainda não
        # tinha sido importado nesta sessão; para troca de versão de um
        # binário já carregado, normalmente não é suficiente)
        for mod in list(sys.modules):
            if mod == "cv2" or mod.startswith("cv2."):
                del sys.modules[mod]
        import cv2

        if cv2.__version__ != "5.0.0":
            raise RuntimeError(
                f"OpenCV instalado (5.0.0), mas a sessão ainda está usando "
                f"a versão {cv2.__version__} carregada em memória.\n"
                f"➜ Reinicie o kernel/runtime (Ambiente de execução > Reiniciar sessão "
                f"no Colab, ou Kernel > Restart no Jupyter) e rode a célula novamente."
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