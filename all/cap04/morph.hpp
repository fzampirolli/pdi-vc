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

    SE() = default;
    // De um literal de pesos: mm::SE{{SE_OUT,-1,SE_OUT},{-1,0,-1},{SE_OUT,-1,SE_OUT}}
    // (SE_OUT == NP_NONE == "fora do SE"; usado por dil1/ero1/dist1).
    SE(std::initializer_list<std::initializer_list<int>> rows) {
        h = (int)rows.size();
        w = h ? (int)rows.begin()->size() : 0;
        vals.clear(); vals.reserve((size_t)h * w);
        for (const auto& r : rows) for (int v : r) vals.push_back(v);
    }
    // De uma Image "planar" (0 = fora, != 0 = dentro) — deixa
    // mm::secross()/sebox()/sedisk() (que devolvem Image) servirem como SE
    // planar para dil0/ero0/dil/ero (que testam `bv != 0`).
    SE(const Image& m) {
        h = m.h; w = m.w;
        vals.assign((size_t)h * w, 0);
        for (size_t i = 0; i < m.data.size(); ++i) if (m.data[i]) vals[i] = 1;
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

// Alias legível para os literais mm::SE{{ ... }} (posição "fora do SE").
inline constexpr int SE_OUT = SE::NP_NONE;

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

// Leitura de PNG de estado entre células (combos cpp): preserva o nº de
// canais REAL do arquivo — um PNG grayscale volta 1-canal, ao contrário de
// mm::read, que força 3. Usada só pela injeção mecânica de state/ do
// pipeline (inject_consumer_reads); morfologia/filtragem exigem 1 canal.
inline Image _read_state(const std::string& path) {
    int w, h, ch;
    unsigned char* data = stbi_load(path.c_str(), &w, &h, &ch, 0);
    if (!data)
        throw std::runtime_error("mm::_read_state: falha ao decodificar '" + path + "'");
    Image img(h, w, ch);
    std::copy(data, data + (size_t)w * h * ch, img.data.begin());
    stbi_image_free(data);
    return img;
}

inline Image gray(const Image& img) {
    if (img.channels == 1) return img;
#ifdef MM_USE_OPENCV
    // cv::cvtColor usa ponto-fixo Q14 com arredondamento — bate bit a bit
    // com o cv2.cvtColor(COLOR_RGB2GRAY) da trilha py. Sem o macro, o loop
    // abaixo (float truncado) difere ~±1 em ~metade dos pixels.
    cv::Mat m(img.h, img.w, img.channels == 3 ? CV_8UC3 : CV_8UC4,
              const_cast<unsigned char*>(img.data.data()));
    cv::Mat o;
    cv::cvtColor(m, o, img.channels == 3 ? cv::COLOR_RGB2GRAY : cv::COLOR_RGBA2GRAY);
    Image out(img.h, img.w, 1);
    std::memcpy(out.data.data(), o.data, out.data.size());
    return out;
#else
    Image out(img.h, img.w, 1);
    for (int y = 0; y < img.h; ++y)
        for (int x = 0; x < img.w; ++x) {
            unsigned char r = img.at(y, x, 0);
            unsigned char g = img.at(y, x, 1);
            unsigned char b = img.at(y, x, 2);
            out.at(y, x) = (unsigned char)(0.299 * r + 0.587 * g + 0.114 * b);
        }
    return out;
#endif
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
            k.at<unsigned char>(i, j) =
                (b.at(i, j) == SE::NP_NONE || b.at(i, j) == 0) ? 0 : 1;
    return k;
}
#endif

// mm::dil / mm::ero — morfologia clássica (planar). Com MM_USE_OPENCV usa
// cv::dilate/erode; sem o macro, delega a dil0/ero0 (PLANAR: `bv != 0` = no
// SE), que a validação de 2026-09-05 confirmou bater com cv::dilate para SE
// planar tipo box/cross/disk. SEs de forma (SE::box/cross/disk, ou SE(Image))
// são planares e seguros aqui.
inline Image dil(const Image& f, SE Bc = SE::box(3)) {
    _require_gray(f, "dil");
#ifdef MM_USE_OPENCV
    cv::Mat out;
    cv::dilate(_to_mat(f), out, _se_kernel(Bc));
    return _from_mat(out);
#else
    return dil0(f, Bc);
#endif
}

inline Image ero(const Image& f, SE Bc = SE::box(3)) {
    _require_gray(f, "ero");
#ifdef MM_USE_OPENCV
    cv::Mat out;
    cv::erode(_to_mat(f), out, _se_kernel(Bc));
    return _from_mat(out);
#else
    return ero0(f, Bc);
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
// mm.drawImgPlt(f, scale) — réplica do drawImagePlt/_plot_grid da morph.py:
// grade em tons de cinza NORMALIZADOS (como imshow(f,'gray') do matplotlib,
// que estica [min,max]→[preto,branco]), linhas vermelhas ENTRE as células e
// rótulos de eixo (0,1,2,...) no topo e à esquerda. Sem dígitos dentro das
// células — os valores vão pro stdout via drawImg(f).
inline void drawImgPlt(const Image& f, const std::string& out_path, int scale = 40) {
    std::cout << drawImg(f);
    Image src = (f.channels == 1) ? f : gray(f);
    int cell = std::max(24, scale);
    int fp   = std::max(2, cell / 12);              // px do mini-font dos rótulos
    int LM   = 8 * fp, TM = 8 * fp;                 // margens p/ os rótulos de eixo

    int mn = 255, mx = 0;
    for (auto v : src.data) { mn = std::min(mn, (int)v); mx = std::max(mx, (int)v); }
    int rng = std::max(1, mx - mn);

    int W = LM + src.w * cell + 4, H = TM + src.h * cell + 4;
    Image canvas(H, W, 3);
    std::fill(canvas.data.begin(), canvas.data.end(), (unsigned char)255);

    for (int y = 0; y < src.h; ++y)
        for (int x = 0; x < src.w; ++x) {
            unsigned char v = (unsigned char)(((int)src.at(y, x) - mn) * 255 / rng);
            for (int dy = 0; dy < cell; ++dy)
                for (int dx = 0; dx < cell; ++dx)
                    for (int k = 0; k < 3; ++k)
                        canvas.at(TM + y * cell + dy, LM + x * cell + dx, k) = v;
        }

    auto hline = [&](int yy){ if (yy < 0 || yy >= H) return;
        for (int x = LM; x < LM + src.w * cell; ++x) { canvas.at(yy,x,0)=255; canvas.at(yy,x,1)=0; canvas.at(yy,x,2)=0; } };
    auto vline = [&](int xx){ if (xx < 0 || xx >= W) return;
        for (int y = TM; y < TM + src.h * cell; ++y) { canvas.at(y,xx,0)=255; canvas.at(y,xx,1)=0; canvas.at(y,xx,2)=0; } };
    for (int i = 1; i < src.w; ++i) vline(LM + i * cell);
    for (int j = 1; j < src.h; ++j) hline(TM + j * cell);

    // rótulos de eixo: números no topo (x) e à esquerda (y)
    for (int x = 0; x < src.w; ++x) {
        std::string s = std::to_string(x);
        int ox = LM + x * cell + (cell - (int)s.size() * 4 * fp) / 2;
        for (size_t c = 0; c < s.size(); ++c)
            _blit_int(canvas, s[c], ox + (int)c * 4 * fp, TM - 6 * fp, fp);
    }
    for (int y = 0; y < src.h; ++y) {
        std::string s = std::to_string(y);
        int oy = TM + y * cell + (cell - 5 * fp) / 2;
        for (size_t c = 0; c < s.size(); ++c)
            _blit_int(canvas, s[c], LM - 6 * fp + (int)c * 4 * fp, oy, fp);
    }
    write(canvas, out_path);
}

// ═══════════════════════════════════════════════════════════════════════════
//  cap03 — nível de intensidade, histograma e filtragem espacial
//
//  Equivalentes header-only das operações que a morph.py implementa via
//  numpy/OpenCV. Sem paridade bit-a-bit (bordas e arredondamento podem
//  diferir do cv2); critério: "compila e produz imagem plausível".
// ═══════════════════════════════════════════════════════════════════════════

// ── Kernel (máscara de convolução) ──────────────────────────────────────────
// Construção próxima de um literal numpy:
//   mm::Kernel w{{0,1,0},{1,-4,1},{0,1,0}};
struct Kernel {
    int h = 0, w = 0;
    std::vector<double> vals;

    Kernel() = default;
    Kernel(int h_, int w_, double fill = 0.0)
        : h(h_), w(w_), vals((size_t)h_ * w_, fill) {}
    Kernel(std::initializer_list<std::initializer_list<double>> rows) {
        h = (int)rows.size();
        w = h ? (int)rows.begin()->size() : 0;
        vals.reserve((size_t)h * w);
        for (const auto& r : rows) {
            if ((int)r.size() != w)
                throw std::runtime_error("mm::Kernel: linhas de tamanhos diferentes");
            for (double v : r) vals.push_back(v);
        }
    }
    double& at(int y, int x)       { return vals[(size_t)y * w + x]; }
    double  at(int y, int x) const { return vals[(size_t)y * w + x]; }
    double  sum() const { double s = 0; for (double v : vals) s += v; return s; }

    static Kernel ones(int n) { return Kernel(n, n, 1.0); }
    static Kernel mean(int n) { return Kernel(n, n, 1.0 / ((double)n * n)); }
    // Kernel Gaussiano n×n separável; sigma<=0 → fórmula do cv2.getGaussianKernel.
    static Kernel gaussian(int n, double sigma = 0.0) {
        if (sigma <= 0.0) sigma = 0.3 * ((n - 1) * 0.5 - 1) + 0.8;
        std::vector<double> k1(n);
        int c = n / 2;
        double s = 0.0;
        for (int i = 0; i < n; ++i) {
            k1[i] = std::exp(-(double)(i - c) * (i - c) / (2.0 * sigma * sigma));
            s += k1[i];
        }
        for (double& v : k1) v /= s;
        Kernel k(n, n);
        for (int y = 0; y < n; ++y)
            for (int x = 0; x < n; ++x) k.at(y, x) = k1[y] * k1[x];
        return k;
    }
};

enum class Border { REFLECT101, REPLICATE, CONSTANT, KEEP };  // CONSTANT = zero

// Índice de origem para uma coordenada fora de [0, n): espelha/replica/zera.
inline int _border_idx(int i, int n, Border b) {
    if (i >= 0 && i < n) return i;
    switch (b) {
        case Border::REPLICATE: return i < 0 ? 0 : n - 1;
        case Border::REFLECT101: {                 // fedcb|abcdefgh|gfedc
            if (n == 1) return 0;
            int period = 2 * (n - 1);
            int m = ((i % period) + period) % period;
            return m < n ? m : period - m;
        }
        default: return -1;                        // ZERO/KEEP: amostra = 0
    }
}

// Correlação 2D (NÃO gira o kernel — igual cv2.filter2D). Acumula em double.
// Border::KEEP copia o pixel original nas bordas (largura = metade do kernel).
inline std::vector<double> _correlate(const Image& img, const Kernel& k, Border b) {
    Image src = (img.channels == 1) ? img : gray(img);
    int H = src.h, W = src.w, kh = k.h, kw = k.w, ay = kh / 2, ax = kw / 2;
    std::vector<double> out((size_t)H * W, 0.0);
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            bool border = (y < ay || y >= H - ay || x < ax || x >= W - ax);
            if (b == Border::KEEP && border) {
                out[(size_t)y * W + x] = src.at(y, x);
                continue;
            }
            double acc = 0.0;
            for (int j = 0; j < kh; ++j)
                for (int i = 0; i < kw; ++i) {
                    int sy = _border_idx(y + j - ay, H, b);
                    int sx = _border_idx(x + i - ax, W, b);
                    double pv = (sy < 0 || sx < 0) ? 0.0 : (double)src.at(sy, sx);
                    acc += pv * k.at(j, i);
                }
            out[(size_t)y * W + x] = acc;
        }
    return out;
}

inline unsigned char _sat8(double v) {
    if (v <= 0.0) return 0;
    if (v >= 255.0) return 255;
    return (unsigned char)std::lround(v);
}

inline Image _from_buf(const std::vector<double>& buf, int h, int w) {
    Image out(h, w, 1);
    for (size_t i = 0; i < buf.size(); ++i) out.data[i] = _sat8(buf[i]);
    return out;
}

// ── Operações aritméticas / lógicas (saturadas em [0,255]) ─────────────────
//
// Combina f e g pixel a pixel, por canal. Se um dos operandos tem 1 canal e o
// outro tem C, o de 1 canal é replicado (broadcast) sobre os C — mesma
// semântica de máscara do cv2.bitwise_and/add. Tamanho de saída = interseção
// (min h, min w) e o maior nº de canais.
template <class Op>
inline Image _pixop(const Image& f, const Image& g, Op op) {
    int H = std::min(f.h, g.h), W = std::min(f.w, g.w);
    int C = std::max(f.channels, g.channels);
    Image o(H, W, C);
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x)
            for (int c = 0; c < C; ++c) {
                int fc = (f.channels == 1) ? 0 : c;
                int gc = (g.channels == 1) ? 0 : c;
                o.at(y, x, c) = op((int)f.at(y, x, fc), (int)g.at(y, x, gc));
            }
    return o;
}

inline Image addm(const Image& f, const Image& g) {
    return _pixop(f, g, [](int a, int b) -> unsigned char { return (unsigned char)std::min(255, a + b); });
}
inline Image subm(const Image& f, const Image& g) {
    return _pixop(f, g, [](int a, int b) -> unsigned char { return (unsigned char)std::max(0, a - b); });
}
inline Image addm(const Image& f, int c) {
    Image o = f;
    for (auto& v : o.data) v = (unsigned char)std::clamp((int)v + c, 0, 255);
    return o;
}
inline Image subm(const Image& f, int c) {
    Image o = f;
    for (auto& v : o.data) v = (unsigned char)std::clamp((int)v - c, 0, 255);
    return o;
}
inline Image blend(const Image& f, const Image& g, double alpha = 0.5) {
    return _pixop(f, g, [alpha](int a, int b) -> unsigned char {
        return _sat8(alpha * a + (1.0 - alpha) * b);
    });
}
inline Image band(const Image& f, const Image& g) {
    return _pixop(f, g, [](int a, int b) -> unsigned char { return (unsigned char)(a & b); });
}
inline Image bor(const Image& f, const Image& g) {
    return _pixop(f, g, [](int a, int b) -> unsigned char { return (unsigned char)(a | b); });
}
inline Image bxor(const Image& f, const Image& g) {
    return _pixop(f, g, [](int a, int b) -> unsigned char { return (unsigned char)(a ^ b); });
}
inline Image bnot(const Image& f) {
    Image o = f;
    for (auto& v : o.data) v = (unsigned char)(~v);
    return o;
}

// mm.circle0 — círculo didático (teste r² pixel a pixel, sem cv2).
// thickness < 0 = preenchido; > 0 = só o anel dessa espessura.
inline Image circle0(const Image& img, int cx, int cy, int radius,
                     unsigned char color, int thickness = -1) {
    Image out = img;
    int r = radius;
    int y0 = std::max(0, cy - r - 1), y1 = std::min(img.h, cy + r + 2);
    int x0 = std::max(0, cx - r - 1), x1 = std::min(img.w, cx + r + 2);
    for (int y = y0; y < y1; ++y)
        for (int x = x0; x < x1; ++x) {
            int d2 = (x - cx) * (x - cx) + (y - cy) * (y - cy);
            bool hit;
            if (thickness < 0) hit = d2 <= r * r;
            else { int ri = std::max(0, r - thickness); hit = (ri * ri <= d2 && d2 <= r * r); }
            if (hit)
                for (int c = 0; c < out.channels; ++c) out.at(y, x, c) = color;
        }
    return out;
}
// mm.circle — entrada "clássica" (no lado Python chama cv2.circle); header-only,
// delega a circle0 (mesmo padrão de dil()→dil1()).
inline Image circle(const Image& img, int cx, int cy, int radius,
                    unsigned char color, int thickness = -1) {
    return circle0(img, cx, cy, radius, color, thickness);
}

// mm.pad0 / mm.pad — preenchimento de borda de largura b.
// mode: CONSTANT (zero), REPLICATE, REFLECT101.
inline Image pad0(const Image& img, int b, Border mode = Border::CONSTANT) {
    int H = img.h, W = img.w, C = img.channels;
    Image out(H + 2 * b, W + 2 * b, C);
    for (int y = 0; y < out.h; ++y)
        for (int x = 0; x < out.w; ++x) {
            int sy = _border_idx(y - b, H, mode);
            int sx = _border_idx(x - b, W, mode);
            for (int c = 0; c < C; ++c)
                out.at(y, x, c) = (sy < 0 || sx < 0) ? 0 : img.at(sy, sx, c);
        }
    return out;
}
inline Image pad(const Image& img, int b, Border mode = Border::CONSTANT) {
    return pad0(img, b, mode);
}

// ── Histograma / equalização ──────────────────────────────────────────────
// mm.hist(img, B=8) — vetor de 2^B posições (256 por padrão).
inline std::vector<int> hist(const Image& img, int B = 8) {
    Image src = (img.channels == 1) ? img : gray(img);
    std::vector<int> H((size_t)1 << B, 0);
    int L = (int)H.size();
    for (auto v : src.data)
        if ((int)v < L) H[v]++;
    return H;
}

// mm.equalize — LUT pela CDF: s_k = round((L-1) * CDF(r_k)).
inline Image equalize(const Image& img, int B = 8) {
    Image src = (img.channels == 1) ? img : gray(img);
    std::vector<int> h = hist(src, B);
    int Lmax = 1 << B;
    double total = (double)src.data.size();
    std::vector<unsigned char> lut(h.size());
    double cum = 0.0;
    for (size_t i = 0; i < h.size(); ++i) {
        cum += h[i] / total;
        lut[i] = (unsigned char)std::lround(cum * (Lmax - 1));
    }
    Image out(src.h, src.w, 1);
    for (size_t i = 0; i < src.data.size(); ++i) out.data[i] = lut[src.data[i]];
    return out;
}

// mm.clahe — CLAHE (equalização adaptativa com limite de contraste).
// Reimplementa cv2.createCLAHE(clipLimit, {tiles,tiles}).apply(img) fielmente
// ao algoritmo do OpenCV (imgproc/src/clahe.cpp), para imagem 8 bits 1 canal:
//   1. se W/H não divisível por `tiles`, estende com REFLECT_101 até divisível
//      (LUTs no estendido; interpolação no tamanho original — como o OpenCV);
//   2. por bloco: histograma → clip em `clipLimit·área/256` (mín. 1) e
//      redistribuição uniforme da massa cortada (+ resíduo em passo fixo);
//   3. LUT do bloco pela CDF, escala (256-1)/área;
//   4. por pixel: interpolação bilinear entre as 4 LUTs de bloco vizinhas,
//      com o mesmo mapeamento de coordenadas do OpenCV (x/tw − 0.5, floor,
//      pesos antes do clamp dos índices de bloco).
// Sem MM_USE_OPENCV NÃO é bit-idêntico ao cv2 (arredondamento interno e ordem
// de redistribuição do resíduo diferem), mas fica dentro de ±1 na esmagadora
// maioria dos pixels e o T* de Otsu resultante coincide. COM MM_USE_OPENCV
// delega a cv::createCLAHE → idêntico à trilha py.
inline Image clahe(const Image& img, double clipLimit = 2.0, int tiles = 8) {
    Image src = (img.channels == 1) ? img : gray(img);
#ifdef MM_USE_OPENCV
    cv::Mat m(src.h, src.w, CV_8UC1, src.data.data()), out;
    cv::createCLAHE(clipLimit, cv::Size(std::max(tiles, 1), std::max(tiles, 1)))->apply(m, out);
    Image r(src.h, src.w, 1);
    std::memcpy(r.data.data(), out.data, r.data.size());
    return r;
#else
    const int H = src.h, W = src.w;
    const int tilesX = std::max(tiles, 1), tilesY = std::max(tiles, 1);

    const int EW = (W % tilesX) ? W + (tilesX - W % tilesX) : W;
    const int EH = (H % tilesY) ? H + (tilesY - H % tilesY) : H;
    std::vector<unsigned char> ext((size_t)EW * EH);
    for (int y = 0; y < EH; ++y) {
        int sy = _border_idx(y, H, Border::REFLECT101);
        for (int x = 0; x < EW; ++x)
            ext[(size_t)y * EW + x] =
                src.data[(size_t)sy * W + _border_idx(x, W, Border::REFLECT101)];
    }

    const int tw = EW / tilesX, th = EH / tilesY;
    const int area = tw * th;
    const float lutScale = 255.0f / (float)area;
    int clip = 0;
    if (clipLimit > 0.0) {
        clip = (int)(clipLimit * area / 256.0);
        if (clip < 1) clip = 1;
    }

    // LUTs: tilesY*tilesX planos de 256 entradas
    std::vector<unsigned char> lut((size_t)tilesX * tilesY * 256);
    int hb[256];
    for (int ty = 0; ty < tilesY; ++ty)
        for (int tx = 0; tx < tilesX; ++tx) {
            std::fill(hb, hb + 256, 0);
            for (int j = 0; j < th; ++j) {
                const unsigned char* row = &ext[(size_t)(ty * th + j) * EW + tx * tw];
                for (int i = 0; i < tw; ++i) ++hb[row[i]];
            }
            if (clip > 0) {
                int clipped = 0;
                for (int i = 0; i < 256; ++i)
                    if (hb[i] > clip) { clipped += hb[i] - clip; hb[i] = clip; }
                const int batch = clipped / 256;
                int residual = clipped - batch * 256;
                for (int i = 0; i < 256; ++i) hb[i] += batch;
                if (residual != 0) {
                    int step = std::max(256 / residual, 1);
                    for (int i = 0; i < 256 && residual > 0; i += step, --residual)
                        ++hb[i];
                }
            }
            unsigned char* plane = &lut[((size_t)ty * tilesX + tx) * 256];
            int sum = 0;
            for (int i = 0; i < 256; ++i) {
                sum += hb[i];
                long v = (long)std::nearbyintf(sum * lutScale);
                plane[i] = (unsigned char)(v < 0 ? 0 : (v > 255 ? 255 : v));
            }
        }

    Image out(H, W, 1);
    for (int y = 0; y < H; ++y) {
        float tyf = y * (1.0f / th) - 0.5f;
        int ty1 = (int)std::floor(tyf), ty2 = ty1 + 1;
        float ya = tyf - ty1, ya1 = 1.0f - ya;
        ty1 = std::max(ty1, 0);
        ty2 = std::min(ty2, tilesY - 1);
        for (int x = 0; x < W; ++x) {
            float txf = x * (1.0f / tw) - 0.5f;
            int tx1 = (int)std::floor(txf), tx2 = tx1 + 1;
            float xa = txf - tx1, xa1 = 1.0f - xa;
            tx1 = std::max(tx1, 0);
            tx2 = std::min(tx2, tilesX - 1);
            const int v = src.data[(size_t)y * W + x];
            const float p11 = lut[((size_t)ty1 * tilesX + tx1) * 256 + v];
            const float p12 = lut[((size_t)ty1 * tilesX + tx2) * 256 + v];
            const float p21 = lut[((size_t)ty2 * tilesX + tx1) * 256 + v];
            const float p22 = lut[((size_t)ty2 * tilesX + tx2) * 256 + v];
            float res = (p11 * xa1 + p12 * xa) * ya1 + (p21 * xa1 + p22 * xa) * ya;
            long r = (long)std::nearbyintf(res);
            out.data[(size_t)y * W + x] = (unsigned char)(r < 0 ? 0 : (r > 255 ? 255 : r));
        }
    }
    return out;
#endif
}

// mm.histImg — renderiza o histograma 256-bin como PNG de barras (para mm::show).
inline Image histImg(const Image& img, int cr = 70, int cg = 130, int cb = 180) {
    std::vector<int> H = hist(img, 8);
    int maxc = 1;
    for (int c : H) maxc = std::max(maxc, c);
    const int BW = 2, PH = 200, PAD = 10;
    int W = 256 * BW + 2 * PAD, Hgt = PH + 2 * PAD;
    Image cv(Hgt, W, 3);
    std::fill(cv.data.begin(), cv.data.end(), (unsigned char)255);
    for (int b = 0; b < 256; ++b) {
        int barh = (int)std::lround((double)H[b] / maxc * PH);
        for (int yy = 0; yy < barh; ++yy)
            for (int xx = 0; xx < BW; ++xx) {
                int px = PAD + b * BW + xx;
                int py = PAD + PH - 1 - yy;
                cv.at(py, px, 0) = (unsigned char)cr;
                cv.at(py, px, 1) = (unsigned char)cg;
                cv.at(py, px, 2) = (unsigned char)cb;
            }
    }
    return cv;
}

// ── Filtragem espacial ────────────────────────────────────────────────────
// mm.conv  — correlação vetorizada (borda REFLECT_101, como cv2.filter2D).
// mm.conv0 — correlação didática: bordas mantidas com o valor original.
inline Image conv(const Image& f, const Kernel& w, Border border = Border::REFLECT101) {
    Image src = (f.channels == 1) ? f : gray(f);
    return _from_buf(_correlate(src, w, border), src.h, src.w);
}
inline Image conv0(const Image& f, const Kernel& w, Border border = Border::KEEP) {
    Image src = (f.channels == 1) ? f : gray(f);
    return _from_buf(_correlate(src, w, border), src.h, src.w);
}
inline Image blur(const Image& f, int N = 3) { return conv(f, Kernel::mean(N)); }
inline Image gaussian(const Image& f, int N = 3, double sigma = 0.0) {
    return conv(f, Kernel::gaussian(N, sigma));
}

inline Kernel _lap_default() { return Kernel{{0, 1, 0}, {1, -4, 1}, {0, 1, 0}}; }

// mm.laplacian — realce: g = clip(f - conv(f, B)).
inline Image laplacian(const Image& f, const Kernel& B = _lap_default()) {
    Image src = (f.channels == 1) ? f : gray(f);
    auto lap = _correlate(src, B, Border::REFLECT101);
    std::vector<double> out(lap.size());
    for (size_t i = 0; i < lap.size(); ++i) out[i] = (double)src.data[i] - lap[i];
    return _from_buf(out, src.h, src.w);
}
// mm.laplacian_viz — |lap| normalizado para [0,255].
inline Image laplacian_viz(const Image& f, const Kernel& B = _lap_default()) {
    Image src = (f.channels == 1) ? f : gray(f);
    auto lap = _correlate(src, B, Border::REFLECT101);
    double mx = 1e-9;
    for (double v : lap) mx = std::max(mx, std::fabs(v));
    std::vector<double> out(lap.size());
    for (size_t i = 0; i < lap.size(); ++i) out[i] = std::fabs(lap[i]) / mx * 255.0;
    return _from_buf(out, src.h, src.w);
}

// Magnitude do gradiente com kernels Bx/By; bordas ficam 0 (igual sobel0).
inline Image _gradmag(const Image& f, const Kernel& Bx, const Kernel& By) {
    Image src = (f.channels == 1) ? f : gray(f);
    int H = src.h, W = src.w;
    Image out(H, W, 1);
    for (int y = 1; y < H - 1; ++y)
        for (int x = 1; x < W - 1; ++x) {
            double gx = 0.0, gy = 0.0;
            for (int j = -1; j <= 1; ++j)
                for (int i = -1; i <= 1; ++i) {
                    double p = src.at(y + j, x + i);
                    gx += p * Bx.at(j + 1, i + 1);
                    gy += p * By.at(j + 1, i + 1);
                }
            out.at(y, x) = _sat8(std::sqrt(gx * gx + gy * gy));
        }
    return out;
}
inline Image sobel(const Image& f,
                   const Kernel& Bx = Kernel{{-1, 0, 1}, {-2, 0, 2}, {-1, 0, 1}},
                   const Kernel& By = Kernel{{-1, -2, -1}, {0, 0, 0}, {1, 2, 1}}) {
    return _gradmag(f, Bx, By);
}
inline Image prewitt(const Image& f,
                     const Kernel& Bx = Kernel{{-1, 0, 1}, {-1, 0, 1}, {-1, 0, 1}},
                     const Kernel& By = Kernel{{-1, -1, -1}, {0, 0, 0}, {1, 1, 1}}) {
    return _gradmag(f, Bx, By);
}

// mm.usm — Unsharp Masking: g = clip(round(f + k*(f - blur(f)))).
inline Image usm(const Image& f, double k = 1.0, const Kernel& w = Kernel::mean(3)) {
    Image src = (f.channels == 1) ? f : gray(f);
    auto fbar = _correlate(src, w, Border::REFLECT101);
    std::vector<double> out(fbar.size());
    for (size_t i = 0; i < fbar.size(); ++i)
        out[i] = (double)src.data[i] + k * ((double)src.data[i] - fbar[i]);
    return _from_buf(out, src.h, src.w);
}

// mm.canny — porta do canny0 didático: suavização Gaussiana → gradiente de
// Sobel → supressão de não-máximos (4 direções) → histerese por conexão
// 8-vizinhos (forte propaga pelos fracos).
inline Image canny(const Image& f, int t_low = 50, int t_high = 150,
                   int ksize = 5, double sigma = 0.0) {
    Image src = (f.channels == 1) ? f : gray(f);
    int H = src.h, W = src.w;
    long N = (long)H * W;

    auto sbuf = _correlate(src, Kernel::gaussian(ksize, sigma), Border::REFLECT101);
    Image s(H, W, 1);
    for (long i = 0; i < N; ++i) s.data[i] = _sat8(sbuf[i]);

    Kernel Bx{{-1, 0, 1}, {-2, 0, 2}, {-1, 0, 1}};
    Kernel By{{-1, -2, -1}, {0, 0, 0}, {1, 2, 1}};
    auto gx = _correlate(s, Bx, Border::REFLECT101);
    auto gy = _correlate(s, By, Border::REFLECT101);

    std::vector<double> mag(N), ang(N);
    for (long i = 0; i < N; ++i) {
        mag[i] = std::sqrt(gx[i] * gx[i] + gy[i] * gy[i]);
        double a = std::atan2(gy[i], gx[i]) * 180.0 / 3.14159265358979323846;
        a = std::fmod(a, 180.0);
        if (a < 0) a += 180.0;
        ang[i] = a;
    }

    std::vector<double> nms(N, 0.0);
    auto M = [&](int y, int x) { return mag[(long)y * W + x]; };
    for (int y = 1; y < H - 1; ++y)
        for (int x = 1; x < W - 1; ++x) {
            double a = ang[(long)y * W + x], n1, n2;
            if (a < 22.5 || a >= 157.5) { n1 = M(y, x - 1);     n2 = M(y, x + 1); }
            else if (a < 67.5)          { n1 = M(y - 1, x + 1); n2 = M(y + 1, x - 1); }
            else if (a < 112.5)         { n1 = M(y - 1, x);     n2 = M(y + 1, x); }
            else                        { n1 = M(y - 1, x - 1); n2 = M(y + 1, x + 1); }
            double c = M(y, x);
            if (c >= n1 && c >= n2) nms[(long)y * W + x] = c;
        }

    std::vector<unsigned char> out(N, 0);
    std::vector<long> stack;
    for (long i = 0; i < N; ++i)
        if (nms[i] >= t_high) { out[i] = 255; stack.push_back(i); }
    while (!stack.empty()) {
        long p = stack.back();
        stack.pop_back();
        int py = (int)(p / W), px = (int)(p % W);
        for (int dy = -1; dy <= 1; ++dy)
            for (int dx = -1; dx <= 1; ++dx) {
                int ny = py + dy, nx = px + dx;
                if (ny < 0 || ny >= H || nx < 0 || nx >= W) continue;
                long q = (long)ny * W + nx;
                if (!out[q] && nms[q] >= t_low) { out[q] = 255; stack.push_back(q); }
            }
    }
    Image res(H, W, 1);
    res.data.assign(out.begin(), out.end());
    return res;
}

// mm.median(f, ksize=3) — filtro da mediana (janela ksize×ksize, borda copiada).
inline Image median(const Image& f, int ksize = 3) {
    Image src = (f.channels == 1) ? f : gray(f);
    int H = src.h, W = src.w, r = ksize / 2;
    Image out = src;
    std::vector<unsigned char> win;
    win.reserve((size_t)ksize * ksize);
    for (int y = r; y < H - r; ++y)
        for (int x = r; x < W - r; ++x) {
            win.clear();
            for (int j = -r; j <= r; ++j)
                for (int i = -r; i <= r; ++i) win.push_back(src.at(y + j, x + i));
            std::nth_element(win.begin(), win.begin() + win.size() / 2, win.end());
            out.at(y, x) = win[win.size() / 2];
        }
    return out;
}

// mm.drawImg(kernel) — mesma grade textual do drawImg(Image), mas para os
// coeficientes (double) de um mm::Kernel. Inteiros saem sem casa decimal.
inline std::string drawImg(const Kernel& k) {
    bool all_int = true;
    for (double v : k.vals)
        if (v != std::floor(v)) { all_int = false; break; }
    std::ostringstream oss;
    for (int y = 0; y < k.h; ++y) {
        for (int x = 0; x < k.w; ++x) {
            if (all_int) oss << std::setw(4) << (long)std::llround(k.at(y, x));
            else         oss << std::setw(9) << std::fixed << std::setprecision(4) << k.at(y, x);
            oss << ' ';
        }
        oss << '\n';
    }
    return oss.str();
}

// mm.drawImgKernel(f, B, x, y) — grade ampliada (drawImgPlt) + qual janela do
// kernel está sendo processada, no stdout.
inline void drawImgKernel(const Image& f, const Kernel& B, int cx, int cy,
                          const std::string& out_path, int scale = 40) {
    std::cout << "Processando pixel (x,y)=(" << cx << "," << cy << ")"
              << "  |  janela do kernel " << B.h << "x" << B.w << std::endl;
    drawImgPlt(f, out_path, scale);
}

// ═══════════════════════════════════════════════════════════════════════════
//  cap04 — morfologia matemática (composições, reconstrução geodésica,
//  distância, rotulagem, watershed). Tudo sobre imagem 1-canal.
//  dil/ero/dil0/ero0/dil1/ero1 + struct SE já definidos acima.
// ═══════════════════════════════════════════════════════════════════════════

// ── Elementos estruturantes com os nomes da morph.py (devolvem Image, que
//    vira SE planar por conversão implícita — mm.secross já existe acima) ──
inline Image sebox(int n = 0) {                 // Minkowski: lado 3 + 2n
    int s = 3 + 2 * std::max(0, n);
    Image m(s, s, 1);
    std::fill(m.data.begin(), m.data.end(), (unsigned char)1);
    return m;
}
inline Image sedisk(int n = 3) {                // elipse, como SE::disk / cv2
    SE s = SE::disk(n);
    Image m(s.h, s.w, 1);
    for (int i = 0; i < s.h * s.w; ++i) m.data[i] = (unsigned char)(s.vals[i] ? 1 : 0);
    return m;
}

// ── Operações básicas ────────────────────────────────────────────────────
inline Image neg(const Image& f) {
    Image o = f;
    for (auto& v : o.data) v = (unsigned char)(255 - v);
    return o;
}
inline Image open(const Image& f, SE b = SE::box(3))  { return dil(ero(f, b), b); }
inline Image close(const Image& f, SE b = SE::box(3)) { return ero(dil(f, b), b); }
inline Image gradm(const Image& f, SE b = SE::box(3))    { return subm(dil(f, b), ero(f, b)); }
inline Image tophat(const Image& f, SE b = SE::box(3))   { return subm(f, open(f, b)); }
inline Image blackhat(const Image& f, SE b = SE::box(3)) { return subm(close(f, b), f); }

// ── Filtro sequencial alternado ─────────────────────────────────────────
// seq: "OC" | "CO" | "OCO" | "COC"; n passes com SE crescente (Minkowski).
inline SE _se_grow(SE b, int times) {
    if (times <= 0) return b;
    // "dentro do SE" = peso não é NP_NONE (fora) NEM 0 (planar-fora). Antes
    // testava só `!= NP_NONE`, o que incluía os 0s do SE planar (sedisk/
    // secross vêm de Image → vals ∈ {0,1}) e inflava a semente pra uma caixa
    // cheia — divergia da soma de Minkowski da trilha py (mm.sesum).
    Image m(b.h, b.w, 1);
    for (int i = 0; i < b.h * b.w; ++i) {
        int v = b.at(i / b.w, i % b.w);
        m.data[i] = (unsigned char)(v != SE::NP_NONE && v != 0);
    }
    for (int t = 0; t < times; ++t) {
        int ph = b.h / 2, pw = b.w / 2;
        Image p(m.h + 2 * ph, m.w + 2 * pw, 1);
        for (int y = 0; y < m.h; ++y)
            for (int x = 0; x < m.w; ++x) p.at(y + ph, x + pw) = m.at(y, x);
        m = dil0(p, b);
    }
    return SE(m);
}
inline Image asf(const Image& f, const std::string& seq = "OC", SE b = SE::box(3), int n = 1) {
    Image y = (f.channels == 1) ? f : gray(f);
    for (int i = 0; i < n; ++i) {
        SE bi = _se_grow(b, i);
        for (char op : seq)
            if (op == 'O' || op == 'o') y = open(y, bi);
            else if (op == 'C' || op == 'c') y = close(y, bi);
    }
    return y;
}

// ── Reconstrução geodésica ─────────────────────────────────────────────
// cdil/cero: dilatação/erosão geodésica de f condicionada por g, n vezes.
inline Image cdil(const Image& f, const Image& g, SE b = SE::box(3), int n = 1) {
    Image y = f;
    for (int i = 0; i < n; ++i) {
        Image d = dil(y, b);
        for (size_t k = 0; k < y.data.size() && k < g.data.size(); ++k)
            d.data[k] = std::min(d.data[k], g.data[k]);
        y = d;
    }
    return y;
}
inline Image cero(const Image& f, const Image& g, SE b = SE::box(3), int n = 1) {
    Image y = f;
    for (int i = 0; i < n; ++i) {
        Image e = ero(y, b);
        for (size_t k = 0; k < y.data.size() && k < g.data.size(); ++k)
            e.data[k] = std::max(e.data[k], g.data[k]);
        y = e;
    }
    return y;
}
// Reconstrução geodésica RÁPIDA (Vincent 1993, algoritmo híbrido: varredura
// raster + anti-raster + fila FIFO), 8-conexo. O(H·W) em vez do laço
// "dilata a imagem toda até convergir" (que é O(diâmetro·H·W) — 10 s numa
// imagem full-res). Usado quando o SE é uma caixa pequena (≤ 3×3), que é o
// único caso em cap04 (infrec/suprec/clohole/edgeoff usam SE::box(3)).
inline Image _recdil8(Image y, const Image& g) {          // reconstrução por dilatação
    const int H = y.h, W = y.w;
    auto Y = y.data.data(); auto G = g.data.data();
    for (int r = 0; r < H; ++r)
        for (int c = 0; c < W; ++c) {
            size_t p = (size_t)r * W + c;
            unsigned char m = Y[p];
            if (r > 0) {
                if (c > 0)     m = std::max(m, Y[p - W - 1]);
                m = std::max(m, Y[p - W]);
                if (c < W - 1) m = std::max(m, Y[p - W + 1]);
            }
            if (c > 0)         m = std::max(m, Y[p - 1]);
            Y[p] = std::min(m, G[p]);
        }
    std::vector<size_t> q; q.reserve((size_t)H * W / 4);
    for (int r = H - 1; r >= 0; --r)
        for (int c = W - 1; c >= 0; --c) {
            size_t p = (size_t)r * W + c;
            unsigned char m = Y[p];
            if (r < H - 1) {
                if (c < W - 1) m = std::max(m, Y[p + W + 1]);
                m = std::max(m, Y[p + W]);
                if (c > 0)     m = std::max(m, Y[p + W - 1]);
            }
            if (c < W - 1)     m = std::max(m, Y[p + 1]);
            Y[p] = std::min(m, G[p]);
            bool push = false;
            auto chk = [&](size_t nb){ if (Y[nb] < Y[p] && Y[nb] < G[nb]) push = true; };
            if (r < H - 1) {
                if (c < W - 1) chk(p + W + 1);
                chk(p + W);
                if (c > 0)     chk(p + W - 1);
            }
            if (c < W - 1)     chk(p + 1);
            if (push) q.push_back(p);
        }
    for (size_t qi = 0; qi < q.size(); ++qi) {
        size_t p = q[qi];
        int r = (int)(p / W), c = (int)(p % W);
        auto prop = [&](size_t nb){
            if (Y[nb] < Y[p] && G[nb] != Y[nb]) { Y[nb] = std::min(Y[p], G[nb]); q.push_back(nb); }
        };
        if (r > 0)     { if (c > 0) prop(p - W - 1); prop(p - W); if (c < W - 1) prop(p - W + 1); }
        if (c > 0)     prop(p - 1);
        if (c < W - 1) prop(p + 1);
        if (r < H - 1) { if (c > 0) prop(p + W - 1); prop(p + W); if (c < W - 1) prop(p + W + 1); }
    }
    return y;
}
inline Image _recero8(Image y, const Image& g) {          // reconstrução por erosão (dual)
    const int H = y.h, W = y.w;
    auto Y = y.data.data(); auto G = g.data.data();
    for (int r = 0; r < H; ++r)
        for (int c = 0; c < W; ++c) {
            size_t p = (size_t)r * W + c;
            unsigned char m = Y[p];
            if (r > 0) {
                if (c > 0)     m = std::min(m, Y[p - W - 1]);
                m = std::min(m, Y[p - W]);
                if (c < W - 1) m = std::min(m, Y[p - W + 1]);
            }
            if (c > 0)         m = std::min(m, Y[p - 1]);
            Y[p] = std::max(m, G[p]);
        }
    std::vector<size_t> q; q.reserve((size_t)H * W / 4);
    for (int r = H - 1; r >= 0; --r)
        for (int c = W - 1; c >= 0; --c) {
            size_t p = (size_t)r * W + c;
            unsigned char m = Y[p];
            if (r < H - 1) {
                if (c < W - 1) m = std::min(m, Y[p + W + 1]);
                m = std::min(m, Y[p + W]);
                if (c > 0)     m = std::min(m, Y[p + W - 1]);
            }
            if (c < W - 1)     m = std::min(m, Y[p + 1]);
            Y[p] = std::max(m, G[p]);
            bool push = false;
            auto chk = [&](size_t nb){ if (Y[nb] > Y[p] && Y[nb] > G[nb]) push = true; };
            if (r < H - 1) {
                if (c < W - 1) chk(p + W + 1);
                chk(p + W);
                if (c > 0)     chk(p + W - 1);
            }
            if (c < W - 1)     chk(p + 1);
            if (push) q.push_back(p);
        }
    for (size_t qi = 0; qi < q.size(); ++qi) {
        size_t p = q[qi];
        int r = (int)(p / W), c = (int)(p % W);
        auto prop = [&](size_t nb){
            if (Y[nb] > Y[p] && G[nb] != Y[nb]) { Y[nb] = std::max(Y[p], G[nb]); q.push_back(nb); }
        };
        if (r > 0)     { if (c > 0) prop(p - W - 1); prop(p - W); if (c < W - 1) prop(p - W + 1); }
        if (c > 0)     prop(p - 1);
        if (c < W - 1) prop(p + 1);
        if (r < H - 1) { if (c > 0) prop(p + W - 1); prop(p + W); if (c < W - 1) prop(p + W + 1); }
    }
    return y;
}
inline bool _is_small_box(const SE& b) {
    if (b.h > 3 || b.w > 3) return false;
    for (int v : b.vals) if (v != 1) return false;
    return true;
}
// infrec: dilata o marcador (f ∧ g) sob a máscara g até convergir.
inline Image infrec(const Image& f, const Image& g, SE b = SE::box(3)) {
    Image y = f;
    for (size_t k = 0; k < y.data.size() && k < g.data.size(); ++k)
        y.data[k] = std::min(y.data[k], g.data[k]);
    if (_is_small_box(b))
        return _recdil8(std::move(y), g);
    while (true) {
        Image prev = y;
        Image d = dil(y, b);
        for (size_t k = 0; k < d.data.size() && k < g.data.size(); ++k)
            d.data[k] = std::min(d.data[k], g.data[k]);
        y = d;
        if (y.data == prev.data) break;
    }
    return y;
}
// suprec: erode o marcador (f ∨ g) sobre a máscara g até convergir.
inline Image suprec(const Image& f, const Image& g, SE b = SE::box(3)) {
    Image y = f;
    for (size_t k = 0; k < y.data.size() && k < g.data.size(); ++k)
        y.data[k] = std::max(y.data[k], g.data[k]);
    if (_is_small_box(b))
        return _recero8(std::move(y), g);
    while (true) {
        Image prev = y;
        Image e = ero(y, b);
        for (size_t k = 0; k < e.data.size() && k < g.data.size(); ++k)
            e.data[k] = std::max(e.data[k], g.data[k]);
        y = e;
        if (y.data == prev.data) break;
    }
    return y;
}

inline Image frame(const Image& f, int border = 5) {
    Image g(f.h, f.w, 1);
    std::fill(g.data.begin(), g.data.end(), (unsigned char)255);
    for (int y = border; y < f.h - border; ++y)
        for (int x = border; x < f.w - border; ++x) g.at(y, x) = 0;
    return g;
}
// edgeoff: remove objetos que tocam a borda (reconstrução a partir da moldura).
inline Image edgeoff(const Image& f, SE b = SE::box(3), int border = 1) {
    Image fr = frame(f, border);
    Image marcador(f.h, f.w, 1);
    for (size_t k = 0; k < f.data.size(); ++k) marcador.data[k] = (unsigned char)(fr.data[k] & f.data[k]);
    return subm(f, infrec(marcador, f, b));
}
// clohole: preenche buracos (reconstrução do complemento a partir da moldura).
inline Image clohole(const Image& f, SE b = SE::box(3)) {
    Image fr = frame(f, 1), nf = neg(f);
    Image marcador(f.h, f.w, 1);
    for (size_t k = 0; k < f.data.size(); ++k) marcador.data[k] = (unsigned char)(fr.data[k] & nf.data[k]);
    return neg(infrec(marcador, nf, b));
}

// ── Rotulagem por flood-fill (rótulos 1..255; satura em 255) ────────────
inline Image label0(const Image& f, SE b = SE::box(3)) {
    Image src = (f.channels == 1) ? f : gray(f);
    int H = src.h, W = src.w;
    Image g(H, W, 1);
    int cor = 0;
    std::vector<int> stack;
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x)
            if (src.at(y, x) && !g.at(y, x)) {
                if (cor < 255) ++cor;
                g.at(y, x) = (unsigned char)cor;
                stack.clear(); stack.push_back(y * W + x);
                while (!stack.empty()) {
                    int p = stack.back(); stack.pop_back();
                    int py = p / W, px = p % W;
                    _viz(src, b, py, px, [&](int vy, int vx, int bv) {
                        if (bv != SE::NP_NONE && bv != 0 && src.at(vy, vx) && !g.at(vy, vx)) {
                            g.at(vy, vx) = (unsigned char)cor;
                            stack.push_back(vy * W + vx);
                        }
                    });
                }
            }
    return g;
}

// ── Transformada de distância ──────────────────────────────────────────
// dist: L2 aproximada (chamfer 2 passes, pesos 1 / √2). Satura em 255.
inline Image dist(const Image& f) {
    Image src = (f.channels == 1) ? f : gray(f);
    int H = src.h, W = src.w;
    const double INF = 1e12, a = 1.0, d = std::sqrt(2.0);
    std::vector<double> m((size_t)H * W);
    for (int i = 0; i < H * W; ++i) m[i] = src.data[i] ? INF : 0.0;
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
            double& v = m[(size_t)y * W + x];
            if (v == 0.0) continue;
            if (y > 0)             v = std::min(v, m[(size_t)(y - 1) * W + x] + a);
            if (x > 0)             v = std::min(v, m[(size_t)y * W + x - 1] + a);
            if (y > 0 && x > 0)    v = std::min(v, m[(size_t)(y - 1) * W + x - 1] + d);
            if (y > 0 && x < W - 1)v = std::min(v, m[(size_t)(y - 1) * W + x + 1] + d);
        }
    for (int y = H - 1; y >= 0; --y)
        for (int x = W - 1; x >= 0; --x) {
            double& v = m[(size_t)y * W + x];
            if (v == 0.0) continue;
            if (y < H - 1)             v = std::min(v, m[(size_t)(y + 1) * W + x] + a);
            if (x < W - 1)             v = std::min(v, m[(size_t)y * W + x + 1] + a);
            if (y < H - 1 && x < W - 1)v = std::min(v, m[(size_t)(y + 1) * W + x + 1] + d);
            if (y < H - 1 && x > 0)    v = std::min(v, m[(size_t)(y + 1) * W + x - 1] + d);
        }
    Image out(H, W, 1);
    for (int i = 0; i < H * W; ++i) out.data[i] = (unsigned char)std::min(255.0, std::round(m[i]));
    return out;
}
// dist1: distância por erosões sucessivas com SE de pesos (b passado pelo usuário).
inline Image dist1(const Image& f, SE b) {
    Image g = (f.channels == 1) ? f : gray(f);
    while (true) {
        Image prev = g;
        g = ero1(g, b);
        if (g.data == prev.data) break;
    }
    return g;
}
// gdist: distância geodésica (nº de passos) do marcador dentro da máscara f.
inline Image gdist(const Image& f, const Image& marker, SE b = SE::box(3)) {
    Image mask = (f.channels == 1) ? f : gray(f);
    int H = mask.h, W = mask.w;
    const int INF = 1 << 29;
    std::vector<int> dd((size_t)H * W, INF);
    std::vector<int> q;
    for (int i = 0; i < H * W && i < (int)marker.data.size(); ++i)
        if (marker.data[i] && mask.data[i]) { dd[i] = 0; q.push_back(i); }
    size_t head = 0;
    while (head < q.size()) {
        int p = q[head++], py = p / W, px = p % W, dp = dd[p];
        _viz(mask, b, py, px, [&](int vy, int vx, int bv) {
            if (bv == SE::NP_NONE || bv == 0) return;
            int qi = vy * W + vx;
            if (mask.data[qi] && dd[qi] == INF) { dd[qi] = dp + 1; q.push_back(qi); }
        });
    }
    Image out(H, W, 1);
    for (int i = 0; i < H * W; ++i) out.data[i] = (dd[i] == INF) ? 0 : (unsigned char)std::min(255, dd[i]);
    return out;
}

// ── Watershed ──────────────────────────────────────────────────────────
// f = marcadores (binário/rotulado); mask (opcional) limita a expansão;
// op = "region" (imagem rotulada) ou outra coisa → "line" (gradm das regiões).
inline Image watershed0(const Image& f, Image mask = Image(),
                        const std::string& op = "region", SE b = SE::box(3)) {
    Image lab = label0(f, b);
    Image g = lab;
    int H = lab.h, W = lab.w;
    bool hm = (mask.h == H && mask.w == W);
    auto inzone = [&](int y, int x) { return !hm || mask.at(y, x); };
    for (int iter = 0; iter < H * W; ++iter) {
        Image snap = g;
        bool mudou = false;
        for (int y = 0; y < H; ++y)
            for (int x = 0; x < W; ++x) {
                if (g.at(y, x) != 0 || !inzone(y, x)) continue;
                int best = 0;
                _viz(snap, b, y, x, [&](int vy, int vx, int bv) {
                    if (bv != SE::NP_NONE && bv != 0 && (int)snap.at(vy, vx) > best) best = snap.at(vy, vx);
                });
                if (best > 0) { g.at(y, x) = (unsigned char)best; mudou = true; }
            }
        if (!mudou) break;
        bool anyzero = false;
        for (int y = 0; y < H && !anyzero; ++y)
            for (int x = 0; x < W; ++x)
                if (!g.at(y, x) && inzone(y, x)) { anyzero = true; break; }
        if (!anyzero) break;
    }
    if (op == "region") return g;
    Image ln = gradm(g, SE::cross(3));   // fronteiras entre rótulos
    for (auto& v : ln.data) v = v ? 255 : 0;
    return ln;
}
inline Image watershedB(const Image& f, Image mask = Image(),
                        const std::string& op = "region", SE b = SE::box(3)) {
    Image m = label0(f, b);
    int H = m.h, W = m.w;
    bool hm = (mask.h == H && mask.w == W);
    auto inzone = [&](int y, int x) { return !hm || mask.at(y, x); };
    std::vector<int> q;
    for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x)
            if (m.at(y, x) > 0) {
                bool front = false;
                _viz(m, b, y, x, [&](int vy, int vx, int bv) {
                    if (bv != SE::NP_NONE && bv != 0 && m.at(vy, vx) == 0 && inzone(vy, vx)) front = true;
                });
                if (front) q.push_back(y * W + x);
            }
    size_t head = 0;
    while (head < q.size()) {
        int p = q[head++], py = p / W, px = p % W;
        unsigned char cor = m.at(py, px);
        _viz(m, b, py, px, [&](int vy, int vx, int bv) {
            if (bv == SE::NP_NONE || bv == 0) return;
            if (m.at(vy, vx) == 0 && inzone(vy, vx)) { m.at(vy, vx) = cor; q.push_back(vy * W + vx); }
        });
    }
    if (op == "region") return m;
    Image ln = gradm(m, SE::cross(3));   // fronteiras entre rótulos
    for (auto& v : ln.data) v = v ? 255 : 0;
    return ln;
}
// mm::watershed — na trilha cpp, equivale ao watershedB (flooding por BFS).
inline Image watershed(const Image& f, Image mask = Image(),
                       const std::string& op = "region", SE b = SE::box(3)) {
    return watershedB(f, mask, op, b);
}

}  // namespace mm
