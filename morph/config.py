import os
import sys
import importlib
import importlib.metadata
import subprocess
import urllib.request

OPENCV_VERSION = "5.0.0.93"
BASE_URL = (
    "https://raw.githubusercontent.com/fzampirolli/pdi-vc/"
    "master/morph"
)


def _install_opencv():
    """Garante OpenCV 5.0.0."""
    try:
        version = importlib.metadata.version("opencv-python")
    except importlib.metadata.PackageNotFoundError:
        version = None

    if version != OPENCV_VERSION:
        subprocess.run(
            [
                sys.executable, "-m", "pip", "install", "-q",
                "--upgrade", f"opencv-python=={OPENCV_VERSION}",
            ],
            check=True,
        )

    import cv2

    if cv2.__version__ != "5.0.0":
        raise RuntimeError(
            f"OpenCV 5.0.0 obrigatório: {cv2.__version__}"
        )

    return cv2


def _download(files):
    """Baixa arquivos do diretório morph do GitHub."""
    for filename in files:
        if not os.path.exists(filename):
            urllib.request.urlretrieve(
                f"{BASE_URL}/{filename}", filename
            )


def setup(testsuite=False):
    """Configura o ambiente do notebook."""
    cv2 = _install_opencv()

    files = ["morph.py"]
    if testsuite:
        files.append("testsuite.py")
    _download(files)

    import morph
    importlib.reload(morph)
    from morph import mm

    result = {
        "cv2": cv2,
        "morph": morph,
        "mm": mm,
    }

    if testsuite:
        import testsuite
        importlib.reload(testsuite)
        from testsuite import TestSuite
        result["testsuite"] = testsuite
        result["TestSuite"] = TestSuite

    print(
        f"✅ Ambiente pronto. "
        f"Morph: {getattr(morph, '__version__', 'local_file')} | "
        f"OpenCV: {cv2.__version__}"
    )

    if testsuite:
        print(f"TestSuite: {testsuite.__version__}")

    return result