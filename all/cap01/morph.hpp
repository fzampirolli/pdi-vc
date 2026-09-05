// morph.hpp — v0.4
//
// Equivalente C++ didático da morph.py. Header-only, pensado pra compilar
// com um `g++ arquivo.cpp -o arquivo` simples: o núcleo (read, gray,
// randomImage, show, write, threshold, drawImg, drawImgPlt, e as
// transformações geométricas resize/translate/rotate/shear + secross)
// não depende de OpenCV — usa stb_image/stb_image_write (vendorizadas ao
// lado, ver THIRD_PARTY_LICENSES.md) pra ler/escrever PNG/JPEG.
//
// Morfologia (dil/dil0/dil1, ero/ero0/ero1) segue a convenção de nomes da
// morph.py: sufixo 0 = didática planar, sufixo 1 = didática com pesos, sem
// sufixo = clássica. O caminho clássico usa cv::Mat SOMENTE quando compilado
// com -DMM_USE_OPENCV; sem o macro (padrão, inclusive Moodle/VPL) mm::dil()
// delega a mm::dil1() e nada de OpenCV é exigido.
//
// Cada célula `%%writefile ....cpp` é seu próprio processo isolado — por
// isso `show()` exige um `out_path` explícito (sem o contador global que a
// versão Python usa, que só faz sentido dentro de um único processo
// Jupyter). Ver Fase 2 do plano: o pipeline sempre chama show() com o
// token MM_OUT, nunca um nome inventado pelo LLM.
//
// Sem paridade numérica garantida com a implementação Python/OpenCV
// (gray/threshold usam fórmulas padrão, não bit-a-bit idênticas) — o
// critério desta v0 é "compila e produz uma imagem plausível", não
// "resultado idêntico ao Python".

#pragma once

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#include <algorithm>
#include <cctype>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <sys/wait.h>
#include <unistd.h>

// Backend OpenCV é OPT-IN: compile com `-DMM_USE_OPENCV $(pkg-config --cflags
// --libs opencv4)` para que mm::dil()/mm::ero()/SE::disk() usem cv::Mat. Sem
// o macro (padrão — `g++ arquivo.cpp -o arquivo`, inclusive no Moodle/VPL),
// mm::dil() cai em mm::dil1() e nenhuma dependência de sistema é exigida.
#ifdef MM_USE_OPENCV
#include <opencv2/opencv.hpp>
#endif

namespace mm {

struct Image {
    int h = 0, w = 0, channels = 1;   // channels: 1 = cinza, 3 = RGB
    std::vector<unsigned char> data;  // row-major, canais intercalados

    Image() = default;
    Image(int h_, int w_, int channels_ = 1)
        : h(h_), w(w_), channels(channels_),
          data((size_t)h_ * w_ * channels_, 0) {}

    unsigned char& at(int y, int x, int c = 0) {
        return data[(size_t)(y * w + x) * channels + c];
    }
    unsigned char at(int y, int x, int c = 0) const {
        return data[(size_t)(y * w + x) * channels + c];
    }
};

// ── Elemento estruturante ─────────────────────────────────────────────────
//
// Espelha o papel do numpy array em mm._viz da morph.py:
//   * ops planares  (dil0/ero0): `at(by,bx) != 0`  → posição pertence ao SE
//   * ops com pesos (dil1/ero1): valor = peso aditivo/subtrativo; `NP_NONE`
//     marca "fora do SE" (equivalente ao ±inf que a morph.py testa em ero1).
struct SE {
    static constexpr int NP_NONE = INT_MIN;

    int h = 3, w = 3;
    std::vector<int> vals = std::vector<int>(9, 0);  // padrão: 3x3 plano, peso 0

    int at(int by, int bx) const { return vals[(size_t)by * w + bx]; }

    // np.flip nos dois eixos — dilatação usa o SE refletido (dil0/dil1).
    SE reflected() const {
        SE s; s.h = h; s.w = w; s.vals.resize(vals.size());
        for (int by = 0; by < h; ++by)
            for (int bx = 0; bx < w; ++bx)
                s.vals[(size_t)by * w + bx] = vals[(size_t)(h - 1 - by) * w + (w - 1 - bx)];
        return s;
    }

    static SE box(int n = 3) {           // np.ones((n,n)) — default de dil0/ero0
        SE s; s.h = s.w = n; s.vals.assign((size_t)n * n, 1); return s;
    }
    static SE zeros(int n = 3) {         // np.zeros((n,n)) — default de dil1/ero1/dil/ero
        SE s; s.h = s.w = n; s.vals.assign((size_t)n * n, 0); return s;
    }
    static SE cross(int n = 3) {
        SE s; s.h = s.w = n; s.vals.assign((size_t)n * n, 0);
        int c = n / 2;
        for (int i = 0; i < n; ++i) { s.vals[(size_t)i * n + c] = 1; s.vals[(size_t)c * n + i] = 1; }
        return s;
    }
    static SE disk(int n = 3);           // elipse — definição depende de MM_USE_OPENCV
};

// ── download sem shell (execlp direto, sem risco de injeção via URL) ───────
inline bool _download(const std::string& url, const std::string& out_path) {
    for (const char* tool : {"curl", "wget"}) {
        pid_t pid = fork();
        if (pid == 0) {
            if (std::string(tool) == "curl") {
                execlp("curl", "curl", "-sL", "-o", out_path.c_str(), url.c_str(), (char*)nullptr);
            } else {
                execlp("wget", "wget", "-q", "-O", out_path.c_str(), url.c_str(), (char*)nullptr);
            }
            _exit(127);  // exec falhou (ferramenta ausente)
        } else if (pid > 0) {
            int status = 0;
            waitpid(pid, &status, 0);
            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
                std::ifstream check(out_path, std::ios::binary);
                if (check.good() && check.peek() != std::ifstream::traits_type::eof())
                    return true;
            }
        }
    }
    return false;
}

// stb_image não decodifica PGM/PPM em ASCII (P2/P3) — só as variantes
// binárias (P5/P6). Os .pgm deste livro são ASCII (cabeçalho "P2"), então
// esse fallback manual é necessário, não cosmético.
inline int _pnm_next_int(std::istream& f) {
    for (;;) {
        int c = f.peek();
        if (c == '#') { std::string line; std::getline(f, line); continue; }
        if (c != EOF && std::isspace(c)) { f.get(); continue; }
        break;
    }
    int v = 0;
    f >> v;
    return v;
}

inline bool _try_read_ascii_pgm(const std::string& path, Image& out) {
    std::ifstream f(path);
    if (!f.good()) return false;
    std::string magic;
    f >> magic;
    if (magic != "P2") return false;
    int w = _pnm_next_int(f);
    int h = _pnm_next_int(f);
    int maxval = _pnm_next_int(f);
    if (w <= 0 || h <= 0 || maxval <= 0) return false;
    out = Image(h, w, 1);  // PGM é grayscale por definição
    for (auto& v : out.data)
        v = (unsigned char)std::min(255, _pnm_next_int(f) * 255 / maxval);
    return true;
}

inline Image read(const std::string& path_or_url, bool grayscale = false) {
    std::string local_path = path_or_url;
    bool is_url = path_or_url.rfind("http://", 0) == 0 ||
                  path_or_url.rfind("https://", 0) == 0;
    if (is_url) {
        local_path = "_mm_download_tmp.img";
        if (!_download(path_or_url, local_path))
            throw std::runtime_error("mm::read: falha ao baixar '" + path_or_url + "'");
    }

    int w, h, ch;
    int desired = grayscale ? 1 : 3;
    unsigned char* data = stbi_load(local_path.c_str(), &w, &h, &ch, desired);
    if (!data) {
        Image fallback;
        if (_try_read_ascii_pgm(local_path, fallback)) return fallback;
        throw std::runtime_error("mm::read: falha ao decodificar '" + path_or_url + "'");
    }

    Image img(h, w, desired);
    std::copy(data, data + (size_t)w * h * desired, img.data.begin());
    stbi_image_free(data);
    return img;
}

inline Image gray(const Image& img) {
    if (img.channels == 1) return img;
    Image out(img.h, img.w, 1);
    for (int y = 0; y < img.h; ++y)
        for (int x = 0; x < img.w; ++x) {
            unsigned char r = img.at(y, x, 0);
            unsigned char g = img.at(y, x, 1);
            unsigned char b = img.at(y, x, 2);
            out.at(y, x) = (unsigned char)(0.299 * r + 0.587 * g + 0.114 * b);
        }
    return out;
}

inline Image randomImage(int h, int w, int maxValue = 9) {
    Image img(h, w, 1);
    static std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<int> dist(0, maxValue);
    for (auto& v : img.data) v = (unsigned char)dist(rng);
    return img;
}

inline void write(const Image& img, const std::string& path) {
    stbi_write_png(path.c_str(), img.w, img.h, img.channels,
                    img.data.data(), img.w * img.channels);
}

// Otsu: limiar que maximiza a variância entre classes sobre o histograma
// 256-bin. Exposto à parte pra quem precisa do T em si (títulos, logs) —
// mm::threshold(img) sem limiar usa exatamente este valor.
inline int otsu(const Image& img) {
    Image src = (img.channels == 1) ? img : gray(img);
    int hist[256] = {0};
    for (auto v : src.data) hist[v]++;
    int total = (int)src.data.size();
    double sum = 0;
    for (int i = 0; i < 256; ++i) sum += i * hist[i];
    double sumB = 0;
    int wB = 0;
    double maxVar = 0;
    int T = 0;
    for (int t = 0; t < 256; ++t) {
        wB += hist[t];
        if (wB == 0) continue;
        int wF = total - wB;
        if (wF == 0) break;
        sumB += t * hist[t];
        double mB = sumB / wB;
        double mF = (sum - sumB) / wF;
        double varBetween = (double)wB * wF * (mB - mF) * (mB - mF);
        if (varBetween > maxVar) {
            maxVar = varBetween;
            T = t;
        }
    }
    return T;
}

inline Image threshold(const Image& img, std::optional<int> limiar = std::nullopt) {
    Image src = (img.channels == 1) ? img : gray(img);
    int T = limiar.has_value() ? *limiar : otsu(src);
    Image out(src.h, src.w, 1);
    for (size_t i = 0; i < src.data.size(); ++i)
        out.data[i] = (src.data[i] > T) ? 255 : 0;
    return out;
}

// ── EROSÃO / DILATAÇÃO ───────────────────────────────────────────────────
//
// Convenção idêntica à morph.py:
//   mm::dil     encapsula a clássica (cv::dilate quando MM_USE_OPENCV;
//               senão delega a dil1 — mesmo papel do `except` no Python)
//   mm::dil0    didática, kernel PLANAR, seguindo a teoria (reflete o SE,
//               máximo de f sobre as posições marcadas)
//   mm::dil1    didática, kernel NÃO-PLANAR, máximo de f[viz] + peso
// (ero/ero0/ero1: análogo com mínimo; erosão não reflete o SE.)
// Operam sobre imagem em tons de cinza (channels == 1).

inline void _require_gray(const Image& f, const char* fn) {
    if (f.channels != 1)
        throw std::runtime_error(std::string("mm::") + fn +
            ": espera imagem em tons de cinza (channels==1); use mm::gray() antes");
}

// Réplica de mm._viz: offset centrado, truncando p/ zero como o int() do
// Python (casts para int fazem o mesmo). Chama cb(vy, vx, peso) por vizinho
// válido (dentro dos limites).
template <class F>
inline void _viz(const Image& f, const SE& B, int y, int x, F&& cb) {
    double oh = -B.h / 2.0 + 0.5;
    double ow = -B.w / 2.0 + 0.5;
    for (int by = 0; by < B.h; ++by)
        for (int bx = 0; bx < B.w; ++bx) {
            int vy = (int)(y + by + oh);
            int vx = (int)(x + bx + ow);
            if (vy >= 0 && vy < f.h && vx >= 0 && vx < f.w)
                cb(vy, vx, B.at(by, bx));
        }
}

inline Image dil0(const Image& f, SE Bc = SE::box(3)) {
    _require_gray(f, "dil0");
    SE B = Bc.reflected();
    Image g(f.h, f.w, 1);
    for (int y = 0; y < f.h; ++y)
        for (int x = 0; x < f.w; ++x) {
            int mx = 0;
            _viz(f, B, y, x, [&](int vy, int vx, int bv) {
                if (bv != 0 && (int)f.at(vy, vx) > mx) mx = f.at(vy, vx);
            });
            g.at(y, x) = (unsigned char)mx;
        }
    return g;
}

inline Image dil1(const Image& f, SE b = SE::zeros(3)) {
    _require_gray(f, "dil1");
    SE B = b.reflected();
    Image g(f.h, f.w, 1);
    for (int y = 0; y < f.h; ++y)
        for (int x = 0; x < f.w; ++x) {
            int mx = 0;
            _viz(f, B, y, x, [&](int vy, int vx, int bv) {
                if (bv == SE::NP_NONE) return;
                int val = (int)f.at(vy, vx) + bv;
                if (val > mx) mx = std::min(255, val);
            });
            g.at(y, x) = (unsigned char)mx;
        }
    return g;
}

inline Image ero0(const Image& f, SE Bc = SE::box(3)) {
    _require_gray(f, "ero0");
    Image g(f.h, f.w, 1);
    for (int y = 0; y < f.h; ++y)
        for (int x = 0; x < f.w; ++x) {
            int mn = 255;
            _viz(f, Bc, y, x, [&](int vy, int vx, int bv) {
                if (bv != 0 && (int)f.at(vy, vx) < mn) mn = f.at(vy, vx);
            });
            g.at(y, x) = (unsigned char)mn;
        }
    return g;
}

inline Image ero1(const Image& f, SE b = SE::zeros(3)) {
    _require_gray(f, "ero1");
    Image g(f.h, f.w, 1);
    for (int y = 0; y < f.h; ++y)
        for (int x = 0; x < f.w; ++x) {
            int mn = 255;
            _viz(f, b, y, x, [&](int vy, int vx, int bv) {
                if (bv == SE::NP_NONE) return;
                int val = (int)f.at(vy, vx) - bv;
                if (val < mn) mn = std::max(0, val);
            });
            g.at(y, x) = (unsigned char)mn;
        }
    return g;
}

#ifdef MM_USE_OPENCV
inline cv::Mat _to_mat(const Image& f) {
    return cv::Mat(f.h, f.w, CV_8UC1,
                    const_cast<unsigned char*>(f.data.data())).clone();
}
inline Image _from_mat(const cv::Mat& m) {
    Image out(m.rows, m.cols, 1);
    for (int y = 0; y < m.rows; ++y)
        std::memcpy(&out.at(y, 0), m.ptr(y), (size_t)m.cols);
    return out;
}
// cv::dilate/erode contam elementos > 0 do kernel; "fora do SE" (NP_NONE)
// vira 0, qualquer outro peso vira 1 (o backend clássico é planar).
inline cv::Mat _se_kernel(const SE& b) {
    cv::Mat k(b.h, b.w, CV_8UC1);
    for (int i = 0; i < b.h; ++i)
        for (int j = 0; j < b.w; ++j)
            k.at<unsigned char>(i, j) = (b.at(i, j) == SE::NP_NONE) ? 0 : 1;
    return k;
}
#endif

inline Image dil(const Image& f, SE Bc = SE::zeros(3)) {
    _require_gray(f, "dil");
#ifdef MM_USE_OPENCV
    cv::Mat out;
    cv::dilate(_to_mat(f), out, _se_kernel(Bc));
    return _from_mat(out);
#else
    return dil1(f, Bc);
#endif
}

inline Image ero(const Image& f, SE Bc = SE::zeros(3)) {
    _require_gray(f, "ero");
#ifdef MM_USE_OPENCV
    cv::Mat out;
    cv::erode(_to_mat(f), out, _se_kernel(Bc));
    return _from_mat(out);
#else
    return ero1(f, Bc);
#endif
}

#ifdef MM_USE_OPENCV
inline SE SE::disk(int n) {
    cv::Mat e = cv::getStructuringElement(cv::MORPH_ELLIPSE, cv::Size(n, n));
    SE s; s.h = n; s.w = n; s.vals.resize((size_t)n * n);
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j)
            s.vals[(size_t)i * n + j] = e.at<unsigned char>(i, j) ? 1 : 0;
    return s;
}
#else
// Réplica do algoritmo de cv::getStructuringElement(MORPH_ELLIPSE, (n,n))
// (varredura por linha da elipse) para que os dois backends produzam o mesmo
// SE — ex.: disk(3) é o "+" (cruz), não a caixa 3x3.
inline SE SE::disk(int n) {
    SE s; s.h = s.w = n; s.vals.assign((size_t)n * n, 0);
    int r = n / 2, c = n / 2;
    double inv_r2 = r ? 1.0 / ((double)r * r) : 0.0;
    for (int i = 0; i < n; ++i) {
        int dy = i - r;
        if (std::abs(dy) > r) continue;
        int dx = (int)(c * std::sqrt(((double)r * r - (double)dy * dy) * inv_r2) + 0.5);
        int j1 = std::max(c - dx, 0);
        int j2 = std::min(c + dx + 1, n);
        for (int j = j1; j < j2; ++j) s.vals[(size_t)i * n + j] = 1;
    }
    return s;
}
#endif

inline std::string drawImg(const Image& img) {
    unsigned char mx = 0, mn = 255;
    for (auto v : img.data) {
        mx = std::max(mx, v);
        mn = std::min(mn, v);
    }
    size_t width = std::max(std::to_string((int)mx).size(),
                             std::to_string((int)mn).size());
    std::ostringstream oss;
    for (int y = 0; y < img.h; ++y) {
        for (int x = 0; x < img.w; ++x)
            oss << std::setw((int)width) << (int)img.at(y, x) << ' ';
        oss << '\n';
    }
    return oss.str();
}

// Uma imagem: escreve out_path; título (se houver) vai pro stdout — não tem
// como desenhar texto na imagem sem uma biblioteca de fontes, então a
// legenda aparece na saída de texto da célula, não dentro do PNG.
inline void show(const Image& img, const std::string& out_path,
                  const std::string& title = "") {
    if (!title.empty()) std::cout << title << std::endl;
    write(img, out_path);
}

// Várias imagens: compõe um grid simples (sem título embutido no PNG, mesma
// limitação acima — títulos vão pro stdout, numerados).
inline void show(const std::vector<Image>& imgs, const std::string& out_path,
                  const std::vector<std::string>& titles = {}, int cols = 3) {
    int n = (int)imgs.size();
    for (int i = 0; i < n; ++i) {
        std::string t = (i < (int)titles.size()) ? titles[i]
                                                   : ("Imagem " + std::to_string(i + 1));
        std::cout << "[" << (i + 1) << "] " << t << std::endl;
    }
    if (n == 0) return;

    cols = std::max(1, cols);
    int rows = (n + cols - 1) / cols;

    int cellW = 0, cellH = 0;
    for (auto& im : imgs) {
        cellW = std::max(cellW, im.w);
        cellH = std::max(cellH, im.h);
    }
    const int gap = 4;
    int canvasW = cols * cellW + (cols + 1) * gap;
    int canvasH = rows * cellH + (rows + 1) * gap;

    Image canvas(canvasH, canvasW, 3);
    std::fill(canvas.data.begin(), canvas.data.end(), (unsigned char)255);

    for (int i = 0; i < n; ++i) {
        int r = i / cols, c = i % cols;
        int offY = gap + r * (cellH + gap);
        int offX = gap + c * (cellW + gap);
        const Image& im = imgs[i];
        for (int y = 0; y < im.h; ++y)
            for (int x = 0; x < im.w; ++x)
                for (int ch = 0; ch < 3; ++ch) {
                    unsigned char v = (im.channels == 1)
                                           ? im.at(y, x, 0)
                                           : im.at(y, x, std::min(ch, im.channels - 1));
                    canvas.at(offY + y, offX + x, ch) = v;
                }
    }
    write(canvas, out_path);
}

// ── Transformações geométricas ───────────────────────────────────────────
//
// Equivalentes header-only de mm.resize/translate/rotate/shear da morph.py
// (que na versão Python são wrappers finos de cv2.resize/cv2.warpAffine).
// Sem OpenCV: o mapeamento inverso é feito à mão, com amostragem nearest ou
// bilinear e preenchimento de borda com 0 (mesma convenção BORDER_CONSTANT
// do cv2). Critério v0: resultado plausível, não bit-a-bit idêntico.

enum class Interp { NEAREST, BILINEAR };

inline Interp _interp_from(const std::string& s) {
    return (s == "nearest") ? Interp::NEAREST : Interp::BILINEAR;
}

// Amostra src em coordenada contínua (sx, sy); fora dos limites → 0.
inline unsigned char _sample(const Image& src, double sx, double sy, int c, Interp mode) {
    if (mode == Interp::NEAREST) {
        int ix = (int)std::lround(sx), iy = (int)std::lround(sy);
        if (ix < 0 || ix >= src.w || iy < 0 || iy >= src.h) return 0;
        return src.at(iy, ix, c);
    }
    int x0 = (int)std::floor(sx), y0 = (int)std::floor(sy);
    double fx = sx - x0, fy = sy - y0;
    auto px = [&](int yy, int xx) -> double {
        if (xx < 0 || xx >= src.w || yy < 0 || yy >= src.h) return 0.0;
        return src.at(yy, xx, c);
    };
    double top = px(y0, x0) * (1 - fx) + px(y0, x0 + 1) * fx;
    double bot = px(y0 + 1, x0) * (1 - fx) + px(y0 + 1, x0 + 1) * fx;
    double v = top * (1 - fy) + bot * fy;
    return (unsigned char)std::lround(std::min(255.0, std::max(0.0, v)));
}

// warpAffine estilo cv2 (sem WARP_INVERSE_MAP): M é o mapa DIRETO src→dst,
// invertido aqui pra varrer o destino. M = {a,b,c, d,e,f}.
inline Image _warp_affine(const Image& src, const double M[6],
                          int out_w, int out_h, Interp mode) {
    double a = M[0], b = M[1], c = M[2], d = M[3], e = M[4], f = M[5];
    double det = a * e - b * d;
    if (std::abs(det) < 1e-12) throw std::runtime_error("warp_affine: matriz singular");
    double ia =  e / det, ib = -b / det;
    double id = -d / det, ie =  a / det;
    double ic  = -(ia * c + ib * f);
    double if_ = -(id * c + ie * f);

    Image out(out_h, out_w, src.channels);
    for (int y = 0; y < out_h; ++y)
        for (int x = 0; x < out_w; ++x) {
            double sx = ia * x + ib * y + ic;
            double sy = id * x + ie * y + if_;
            for (int ch = 0; ch < src.channels; ++ch)
                out.at(y, x, ch) = _sample(src, sx, sy, ch, mode);
        }
    return out;
}

inline Image _resize_to(const Image& src, int out_w, int out_h, Interp mode) {
    out_w = std::max(1, out_w); out_h = std::max(1, out_h);
    double sxr = (double)src.w / out_w, syr = (double)src.h / out_h;
    Image out(out_h, out_w, src.channels);
    for (int y = 0; y < out_h; ++y)
        for (int x = 0; x < out_w; ++x) {
            double sx = (x + 0.5) * sxr - 0.5;
            double sy = (y + 0.5) * syr - 0.5;
            for (int ch = 0; ch < src.channels; ++ch)
                out.at(y, x, ch) = _sample(src, sx, sy, ch, mode);
        }
    return out;
}

// mm.resize(img, fator) — escala uniforme.
inline Image resize(const Image& src, double factor, const std::string& method = "bilinear") {
    return _resize_to(src, (int)std::round(src.w * factor),
                      (int)std::round(src.h * factor), _interp_from(method));
}

// mm.resize(img, (w, h)) — tamanho alvo explícito.
inline Image resize(const Image& src, int out_w, int out_h,
                    const std::string& method = "bilinear") {
    return _resize_to(src, out_w, out_h, _interp_from(method));
}

inline Image translate(const Image& src, double tx, double ty) {
    double M[6] = {1, 0, tx, 0, 1, ty};
    return _warp_affine(src, M, src.w, src.h, Interp::BILINEAR);
}

inline Image shear(const Image& src, double shx = 0.0, double shy = 0.0,
                   const std::string& method = "bilinear") {
    double M[6] = {1, shx, 0, shy, 1, 0};
    return _warp_affine(src, M, src.w, src.h, _interp_from(method));
}

// mm.rotate(img, angle) — graus, sentido anti-horário, em torno do centro
// (w/2, h/2) com divisão inteira; mesma matriz de cv2.getRotationMatrix2D.
inline Image rotate(const Image& src, double angle_deg, double scale = 1.0,
                    const std::string& interp = "bilinear") {
    double cx = src.w / 2, cy = src.h / 2;   // int / int — casa com morph.py (w//2)
    double rad = angle_deg * 3.14159265358979323846 / 180.0;
    double alpha = scale * std::cos(rad), beta = scale * std::sin(rad);
    double M[6] = {
        alpha, beta,  (1 - alpha) * cx - beta * cy,
        -beta, alpha, beta * cx + (1 - alpha) * cy
    };
    return _warp_affine(src, M, src.w, src.h, _interp_from(interp));
}

// Recorte retangular [y0:y1, x0:x1] — equivalente ao fatiamento numpy
// img[y0:y1, x0:x1]. Índices são clampados aos limites da imagem.
inline Image crop(const Image& src, int y0, int y1, int x0, int x1) {
    y0 = std::max(0, std::min(y0, src.h)); y1 = std::max(y0, std::min(y1, src.h));
    x0 = std::max(0, std::min(x0, src.w)); x1 = std::max(x0, std::min(x1, src.w));
    Image out(y1 - y0, x1 - x0, src.channels);
    for (int y = 0; y < out.h; ++y)
        for (int x = 0; x < out.w; ++x)
            for (int ch = 0; ch < src.channels; ++ch)
                out.at(y, x, ch) = src.at(y0 + y, x0 + x, ch);
    return out;
}

// mm.subsample(img, f) — subamostragem por passo f (numpy img[::f, ::f]).
inline Image subsample(const Image& src, int f) {
    f = std::max(1, f);
    Image out((src.h + f - 1) / f, (src.w + f - 1) / f, src.channels);
    for (int y = 0; y < out.h; ++y)
        for (int x = 0; x < out.w; ++x)
            for (int ch = 0; ch < src.channels; ++ch)
                out.at(y, x, ch) = src.at(y * f, x * f, ch);
    return out;
}

// mm.secross() — elemento estruturante em cruz 3x3 (vizinhança-4) como
// matriz 0/1. Retorna Image (não SE): no livro é usada só pra visualização
// com drawImgPlt, igual à morph.py.
inline Image secross(int = 0) {
    Image s(3, 3, 1);
    const int cross[9] = {0,1,0, 1,1,1, 0,1,0};
    for (int i = 0; i < 9; ++i) s.data[i] = (unsigned char)cross[i];
    return s;
}

// Mini-fonte 3x5 (dígitos 0-9 e '-') pra rotular células em drawImgPlt —
// morph.hpp não linka nenhuma lib de fontes.
inline void _blit_int(Image& canvas, char ch, int ox, int oy, int px) {
    static const char* F[] = {
        "111101101101111", "010110010010111", "111001111100111",
        "111001111001111", "101101111001001", "111100111001111",
        "111100111101111", "111001010010010", "111101111101111",
        "111101111001111", "000000111000000"
    };
    int gi;
    if (ch >= '0' && ch <= '9') gi = ch - '0';
    else if (ch == '-')         gi = 10;
    else                        return;
    const char* g = F[gi];
    for (int r = 0; r < 5; ++r)
        for (int cc = 0; cc < 3; ++cc)
            if (g[r * 3 + cc] == '1')
                for (int dy = 0; dy < px; ++dy)
                    for (int dx = 0; dx < px; ++dx) {
                        int yy = oy + r * px + dy, xx = ox + cc * px + dx;
                        if (yy < 0 || yy >= canvas.h || xx < 0 || xx >= canvas.w) continue;
                        for (int k = 0; k < canvas.channels; ++k) canvas.at(yy, xx, k) = 0;
                    }
}

// mm.drawImgPlt(f, scale) — grade textual no stdout + PNG com a matriz
// ampliada, linhas de grade vermelhas e o valor de cada célula rotulado.
inline void drawImgPlt(const Image& f, const std::string& out_path, int scale = 40) {
    std::cout << drawImg(f);
    int cell = std::max(24, scale);
    int pad  = cell / 2;
    int W = f.w * cell + 2 * pad, H = f.h * cell + 2 * pad;
    Image canvas(H, W, 3);
    std::fill(canvas.data.begin(), canvas.data.end(), (unsigned char)255);

    for (int y = 0; y < f.h; ++y)
        for (int x = 0; x < f.w; ++x) {
            unsigned char v = f.at(y, x);
            for (int dy = 0; dy < cell; ++dy)
                for (int dx = 0; dx < cell; ++dx)
                    for (int k = 0; k < 3; ++k)
                        canvas.at(pad + y * cell + dy, pad + x * cell + dx, k) = v;
        }

    auto hline = [&](int yy){ for (int x = 0; x < W; ++x){ canvas.at(yy,x,0)=255; canvas.at(yy,x,1)=0; canvas.at(yy,x,2)=0; } };
    auto vline = [&](int xx){ for (int y = 0; y < H; ++y){ canvas.at(y,xx,0)=255; canvas.at(y,xx,1)=0; canvas.at(y,xx,2)=0; } };
    for (int i = 0; i <= f.w; ++i) vline(std::min(W - 1, pad + i * cell));
    for (int j = 0; j <= f.h; ++j) hline(std::min(H - 1, pad + j * cell));

    int px = std::max(1, cell / 10);
    for (int y = 0; y < f.h; ++y)
        for (int x = 0; x < f.w; ++x) {
            std::string s = std::to_string((int)f.at(y, x));
            int tw = (int)s.size() * 4 * px, th = 5 * px;
            int ox = pad + x * cell + (cell - tw) / 2;
            int oy = pad + y * cell + (cell - th) / 2;
            for (int by = -1; by <= th; ++by)
                for (int bx = -1; bx <= tw; ++bx) {
                    int yy = oy + by, xx = ox + bx;
                    if (yy < 0 || yy >= H || xx < 0 || xx >= W) continue;
                    canvas.at(yy, xx, 0) = canvas.at(yy, xx, 1) = canvas.at(yy, xx, 2) = 255;
                }
            for (size_t ci = 0; ci < s.size(); ++ci)
                _blit_int(canvas, s[ci], ox + (int)ci * 4 * px, oy, px);
        }
    write(canvas, out_path);
}

}  // namespace mm
