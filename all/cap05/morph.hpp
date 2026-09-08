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
#include <array>
#include <cctype>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
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
    // De um buffer já pronto (row-major, canais intercalados). Conveniência
    // para o código traduzido que monta a Image a partir de um cv::Mat 8-bit.
    Image(int h_, int w_, int channels_, std::vector<unsigned char> data_)
        : h(h_), w(w_), channels(channels_), data(std::move(data_)) {
        data.resize((size_t)h_ * w_ * channels_, 0);
    }

    unsigned char& at(int y, int x, int c = 0) {
        return data[(size_t)(y * w + x) * channels + c];
    }
    unsigned char at(int y, int x, int c = 0) const {
        return data[(size_t)(y * w + x) * channels + c];
    }

#ifdef MM_USE_OPENCV
    // Interoperabilidade cv::Mat (só nos capítulos OpenCV, cap05-08): as
    // células traduzidas trabalham em cv::Mat (float, DFT/DCT), mas mm::write/
    // mm::show/estado entre células são em mm::Image (8-bit). Estes dois
    // pontes fecham o vão. Float / não-8-bit vira 8-bit por normalização
    // min-max (mesmo que cv2.normalize(...,NORM_MINMAX) da trilha py).
    Image(const cv::Mat& m) {
        cv::Mat u;
        if (m.depth() == CV_8U) u = m;
        else cv::normalize(m, u, 0, 255, cv::NORM_MINMAX, CV_8U);
        h = u.rows; w = u.cols; channels = u.channels();
        data.assign((size_t)h * w * channels, 0);
        if (u.isContinuous()) std::memcpy(data.data(), u.data, data.size());
        else for (int y = 0; y < h; ++y)
            std::memcpy(data.data() + (size_t)y * w * channels,
                        u.ptr(y), (size_t)w * channels);
    }
    operator cv::Mat() const {
        cv::Mat m(h, w, CV_8UC(channels));
        std::memcpy(m.data, data.data(), data.size());
        return m.clone();
    }
#endif
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
    // Garante o diretório-pai (ex.: "tmp/...") — células sem leitura de estado
    // não têm "tmp/" pré-criado, e o stbi_write_png falharia em silêncio.
    std::error_code _ec;
    auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty()) std::filesystem::create_directories(parent, _ec);
    stbi_write_png(path.c_str(), img.w, img.h, img.channels,
                    img.data.data(), img.w * img.channels);
}

#ifdef MM_USE_OPENCV
// Overload cv::Mat (capítulos OpenCV): normaliza float→8-bit e grava via a
// rota de sempre. Sem isto, `mm::write(<cv::Mat>, ...)` não compila
// (a injeção de painéis/estado emite `mm::write(var, ...)` cru).
inline void write(const cv::Mat& m, const std::string& path) {
    write(Image(m), path);
}
#endif

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

// Escala mantendo a proporção. Fica aqui só como declaração porque o corpo
// (e o enum Interp) vêm mais abaixo, junto com resize/_resize_to.
inline Image _resize_fit(const Image& src, int out_w, int out_h, bool smooth);

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
//
// Cada célula é um quadrado de lado CELL e cada imagem é reescalada para
// caber nela mantendo a proporção, centralizada sobre fundo branco — igual
// ao imshow do matplotlib nos subplots da mm.show em Python. Sem isso, uma
// matriz didática 5x5 sairia com 5 px ao lado de um histograma de ~500 px
// (era a origem das "imagens minúsculas" no C++ vs. Python).
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

    const int CELL = 512;   // lado da célula quadrada, em px (≈ 5in @ ~100dpi)
    const int gap = 8;

    int canvasW = cols * CELL + (cols + 1) * gap;
    int canvasH = rows * CELL + (rows + 1) * gap;
    Image canvas(canvasH, canvasW, 3);
    std::fill(canvas.data.begin(), canvas.data.end(), (unsigned char)255);

    for (int i = 0; i < n; ++i) {
        // Imagem 1-canal: estica [min,max]→[0,255] antes de exibir, como o
        // Normalize automático do imshow(array 2D) no matplotlib — sem isso
        // uma matriz didática 3-bit (valores 0..7) sairia quase toda preta.
        // RGB (3 canais) passa direto, igual ao matplotlib com MxNx3.
        Image norm = imgs[i];
        if (norm.channels == 1 && !norm.data.empty()) {
            unsigned char lo = 255, hi = 0;
            for (unsigned char v : norm.data) { lo = std::min(lo, v); hi = std::max(hi, v); }
            if (hi > lo) {
                double sc = 255.0 / (hi - lo);
                for (unsigned char& v : norm.data)
                    v = (unsigned char)std::lround((v - lo) * sc);
            }
        }
        const Image& im = norm;
        double s = std::min((double)CELL / std::max(1, im.w),
                            (double)CELL / std::max(1, im.h));
        int nw = std::max(1, (int)std::lround(im.w * s));
        int nh = std::max(1, (int)std::lround(im.h * s));
        // Downscale de foto → bilinear; upscale de matriz didática → nearest
        // (mantém os "pixelões" nítidos, como o imshow de um array pequeno).
        bool smooth = (im.w >= 64 && im.h >= 64) && s < 1.0;
        Image scaled = (nw == im.w && nh == im.h) ? im
                                                  : _resize_fit(im, nw, nh, smooth);

        int r = i / cols, c = i % cols;
        int cellY = gap + r * (CELL + gap);
        int cellX = gap + c * (CELL + gap);
        int offY = cellY + (CELL - nh) / 2;
        int offX = cellX + (CELL - nw) / 2;
        for (int y = 0; y < nh; ++y)
            for (int x = 0; x < nw; ++x)
                for (int ch = 0; ch < 3; ++ch) {
                    unsigned char v = (scaled.channels == 1)
                        ? scaled.at(y, x, 0)
                        : scaled.at(y, x, std::min(ch, scaled.channels - 1));
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

// Declarada lá em cima (antes de mm::show): escala p/ (out_w,out_h) usando
// bilinear quando smooth, nearest caso contrário.
inline Image _resize_fit(const Image& src, int out_w, int out_h, bool smooth) {
    return _resize_to(src, out_w, out_h, smooth ? Interp::BILINEAR : Interp::NEAREST);
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

// ── Perspectiva (homografia) ─────────────────────────────────────────────
//
// Réplica header-only de cv2.getPerspectiveTransform + cv2.warpPerspective
// (o que a mm.perspective_transform da morph.py chama). getPerspectiveTransform
// monta e resolve o sistema linear 8x8 das 4 correspondências de pontos;
// warpPerspective varre o destino e amostra a origem pelo mapa projetivo
// inverso. Fora dos limites → 0 (BORDER_CONSTANT do cv2). Critério v0:
// resultado plausível, não bit-a-bit idêntico ao OpenCV.

using Homography = std::array<double, 9>;   // linha-maior h0..h8, com h8 = 1

// Ax = b in-place por eliminação de Gauss com pivô parcial (n <= 8). A é
// n×n linha-maior; a solução volta em b.
inline void _solve_lin(double* A, double* b, int n) {
    for (int col = 0; col < n; ++col) {
        int piv = col;
        for (int r = col + 1; r < n; ++r)
            if (std::fabs(A[r * n + col]) > std::fabs(A[piv * n + col])) piv = r;
        if (piv != col) {
            for (int k = 0; k < n; ++k) std::swap(A[col * n + k], A[piv * n + k]);
            std::swap(b[col], b[piv]);
        }
        double d = A[col * n + col];
        if (std::fabs(d) < 1e-12)
            throw std::runtime_error("getPerspectiveTransform: pontos degenerados/colineares");
        for (int r = 0; r < n; ++r) {
            if (r == col) continue;
            double f = A[r * n + col] / d;
            for (int k = col; k < n; ++k) A[r * n + k] -= f * A[col * n + k];
            b[r] -= f * b[col];
        }
    }
    for (int i = 0; i < n; ++i) b[i] /= A[i * n + i];
}

// M mapeia src → dst (mesma ordem de cv2.getPerspectiveTransform(pts_src, pts_dst)):
//   X = (h0·x + h1·y + h2) / (h6·x + h7·y + 1)
//   Y = (h3·x + h4·y + h5) / (h6·x + h7·y + 1)
inline Homography getPerspectiveTransform(const double s[4][2], const double d[4][2]) {
    double A[64] = {0}, b[8];
    for (int i = 0; i < 4; ++i) {
        double x = s[i][0], y = s[i][1], X = d[i][0], Y = d[i][1];
        double* r0 = A + (2 * i) * 8;
        double* r1 = A + (2 * i + 1) * 8;
        r0[0] = x; r0[1] = y; r0[2] = 1; r0[6] = -x * X; r0[7] = -y * X; b[2 * i]     = X;
        r1[3] = x; r1[4] = y; r1[5] = 1; r1[6] = -x * Y; r1[7] = -y * Y; b[2 * i + 1] = Y;
    }
    _solve_lin(A, b, 8);
    return {b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], 1.0};
}

inline Homography _invert3x3(const Homography& m) {
    double a = m[0], b = m[1], c = m[2], d = m[3], e = m[4],
           f = m[5], g = m[6], h = m[7], i = m[8];
    double det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);
    if (std::fabs(det) < 1e-12)
        throw std::runtime_error("warpPerspective: homografia singular");
    double s = 1.0 / det;
    return {
        (e * i - f * h) * s, (c * h - b * i) * s, (b * f - c * e) * s,
        (f * g - d * i) * s, (a * i - c * g) * s, (c * d - a * f) * s,
        (d * h - e * g) * s, (b * g - a * h) * s, (a * e - b * d) * s
    };
}

// warpPerspective estilo cv2 (sem WARP_INVERSE_MAP): M é src→dst, invertida
// aqui para varrer o destino de tamanho out_w × out_h.
inline Image warpPerspective(const Image& src, const Homography& M,
                             int out_w, int out_h, Interp mode = Interp::BILINEAR) {
    out_w = std::max(1, out_w); out_h = std::max(1, out_h);
    Homography Mi = _invert3x3(M);
    Image out(out_h, out_w, src.channels);
    for (int y = 0; y < out_h; ++y)
        for (int x = 0; x < out_w; ++x) {
            double den = Mi[6] * x + Mi[7] * y + Mi[8];
            if (std::fabs(den) < 1e-12) den = (den < 0 ? -1e-12 : 1e-12);
            double sx = (Mi[0] * x + Mi[1] * y + Mi[2]) / den;
            double sy = (Mi[3] * x + Mi[4] * y + Mi[5]) / den;
            for (int ch = 0; ch < src.channels; ++ch)
                out.at(y, x, ch) = _sample(src, sx, sy, ch, mode);
        }
    return out;
}

// mm.perspective_transform(img, pts1, pts2, size) — homografia de pts1→pts2.
// out_w/out_h <= 0 usa o tamanho de src (equivale a size=None no Python).
inline Image perspective_transform(const Image& src,
                                   const double pts1[4][2], const double pts2[4][2],
                                   int out_w = -1, int out_h = -1,
                                   const std::string& method = "bilinear") {
    return warpPerspective(src, getPerspectiveTransform(pts1, pts2),
                           out_w <= 0 ? src.w : out_w,
                           out_h <= 0 ? src.h : out_h, _interp_from(method));
}

// Mesma coisa aceitando std::vector<std::array<double,2>> (4 pontos por lado) —
// forma mais natural para o código gerado das células.
inline Image perspective_transform(const Image& src,
                                   const std::vector<std::array<double, 2>>& pts1,
                                   const std::vector<std::array<double, 2>>& pts2,
                                   int out_w = -1, int out_h = -1,
                                   const std::string& method = "bilinear") {
    if (pts1.size() != 4 || pts2.size() != 4)
        throw std::runtime_error("perspective_transform: exige 4 pontos em cada lado");
    double a[4][2], b[4][2];
    for (int i = 0; i < 4; ++i) {
        a[i][0] = pts1[i][0]; a[i][1] = pts1[i][1];
        b[i][0] = pts2[i][0]; b[i][1] = pts2[i][1];
    }
    return perspective_transform(src, a, b, out_w, out_h, method);
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
// dist: L2 aproximada (chamfer 2 passes, pesos 1 / √2). Quando a distância
// máxima passa de 255, ESCALA linearmente para [0,255] em vez de saturar —
// o mm.dist do Python promove para uint16 nesse caso, e saturar em 255
// achatava o pico e o vale juntos, grudando objetos vizinhos no
// `dist > frac*dist.max()` (marcadores do watershed). O corte é
// scale-invariant, então o resultado do limiar casa com o Python.
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
    double mx = 0.0;
    for (int i = 0; i < H * W; ++i) if (m[i] < INF * 0.5) mx = std::max(mx, m[i]);
    Image out(H, W, 1);
    if (mx <= 255.0) {                       // cabe em uint8 — cru (igual ao Python)
        for (int i = 0; i < H * W; ++i)
            out.data[i] = (unsigned char)std::min(255.0, std::round(m[i]));
    } else {                                 // Python promoveria a uint16; aqui escala
        double s = 255.0 / mx;
        for (int i = 0; i < H * W; ++i)
            out.data[i] = (unsigned char)std::lround((m[i] < INF * 0.5 ? m[i] : mx) * s);
    }
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

// ── Transformada Wavelet Discreta 2D (DWT) ───────────────────────────────────
//
// Equivalente didático de pywt.dwt2/wavedec2/waverec2/threshold para os
// capítulos OpenCV (não há wavelet no cv::). Só Haar, db4, sym4, bior2.2 —
// suficiente para as figuras do cap05. Borda 'symmetric' (half-sample) e
// coeficientes idênticos aos do PyWavelets; casa numericamente com pywt e
// tem reconstrução perfeita (verificado). Opera em cv::Mat CV_64F, 1 canal.
#ifdef MM_USE_OPENCV

// Coeficientes de decomposição/reconstrução (low/high), na convenção pywt.
inline void _wave_filters(const std::string& name,
                          std::vector<double>& dl, std::vector<double>& dh,
                          std::vector<double>& rl, std::vector<double>& rh) {
    const double s = 0.7071067811865476;      // 1/sqrt(2)
    if (name == "haar" || name == "db1") {
        dl = {s, s};        dh = {-s, s};
        rl = {s, s};        rh = {s, -s};
    } else if (name == "db4") {
        dl = {-0.01059740178506903, 0.0328830116668852, 0.03084138183556076,
              -0.18703481171909309, -0.02798376941685985, 0.6308807679298589,
              0.7148465705529157, 0.2303778133088965};
        dh = {-0.2303778133088965, 0.7148465705529157, -0.6308807679298589,
              -0.02798376941685985, 0.18703481171909309, 0.03084138183556076,
              -0.0328830116668852, -0.01059740178506903};
        rl = {0.2303778133088965, 0.7148465705529157, 0.6308807679298589,
              -0.02798376941685985, -0.18703481171909309, 0.03084138183556076,
              0.0328830116668852, -0.01059740178506903};
        rh = {-0.01059740178506903, -0.0328830116668852, 0.03084138183556076,
              0.18703481171909309, -0.02798376941685985, -0.6308807679298589,
              0.7148465705529157, -0.2303778133088965};
    } else if (name == "sym4") {
        dl = {-0.07576571478927333, -0.02963552764599851, 0.49761866763201545,
              0.8037387518059161, 0.29785779560527736, -0.09921954357684722,
              -0.01260396726203783, 0.0322231006040427};
        dh = {-0.0322231006040427, -0.01260396726203783, 0.09921954357684722,
              0.29785779560527736, -0.8037387518059161, 0.49761866763201545,
              0.02963552764599851, -0.07576571478927333};
        rl = {0.0322231006040427, -0.01260396726203783, -0.09921954357684722,
              0.29785779560527736, 0.8037387518059161, 0.49761866763201545,
              -0.02963552764599851, -0.07576571478927333};
        rh = {-0.07576571478927333, 0.02963552764599851, 0.49761866763201545,
              -0.8037387518059161, 0.29785779560527736, 0.09921954357684722,
              -0.01260396726203783, -0.0322231006040427};
    } else if (name == "bior2.2") {
        dl = {0.0, -0.1767766952966369, 0.3535533905932738, 1.0606601717798212,
              0.3535533905932738, -0.1767766952966369};
        dh = {0.0, 0.3535533905932738, -0.7071067811865476, 0.3535533905932738,
              0.0, 0.0};
        rl = {0.0, 0.3535533905932738, 0.7071067811865476, 0.3535533905932738,
              0.0, 0.0};
        rh = {0.0, 0.1767766952966369, 0.3535533905932738, -1.0606601717798212,
              0.3535533905932738, 0.1767766952966369};
    } else {
        throw std::runtime_error("mm::dwt2: wavelet nao suportada: " + name +
                                 " (use haar/db4/sym4/bior2.2)");
    }
}

// índice half-sample symmetric ('symmetric' do pywt): ...2 1 | 1 2 3 | 3 2 1...
inline int _sym_idx(int i, int n) {
    if (n == 1) return 0;
    int p = 2 * n;
    i %= p; if (i < 0) i += p;
    return i < n ? i : p - 1 - i;
}

// 1D DWT de um nível: x -> (cA, cD), out_len = (n + L - 1) / 2.
inline void _dwt1(const std::vector<double>& x,
                  const std::vector<double>& dl, const std::vector<double>& dh,
                  std::vector<double>& cA, std::vector<double>& cD) {
    int n = (int)x.size(), L = (int)dl.size(), ol = (n + L - 1) / 2;
    cA.assign(ol, 0.0); cD.assign(ol, 0.0);
    for (int k = 0; k < ol; ++k) {
        double a = 0, d = 0;
        for (int i = 0; i < L; ++i) {
            double xi = x[_sym_idx(2 * k + i - (L - 2), n)];
            a += xi * dl[L - 1 - i];        // filtro invertido (correlação)
            d += xi * dh[L - 1 - i];
        }
        cA[k] = a; cD[k] = d;
    }
}

// 1D IDWT de um nível: (cA, cD) -> sinal de comprimento out_len.
inline std::vector<double> _idwt1(const std::vector<double>& cA,
                                  const std::vector<double>& cD,
                                  const std::vector<double>& rl,
                                  const std::vector<double>& rh, int out_len) {
    int n = (int)cA.size(), L = (int)rl.size();
    std::vector<double> ya(2 * n, 0.0), yd(2 * n, 0.0);
    for (int i = 0; i < n; ++i) { ya[2 * i] = cA[i]; yd[2 * i] = cD[i]; }
    std::vector<double> full(2 * n + L - 1, 0.0);
    for (int i = 0; i < (int)ya.size(); ++i)
        for (int j = 0; j < L; ++j) {
            full[i + j] += ya[i] * rl[j];
            full[i + j] += yd[i] * rh[j];
        }
    int start = L - 2;
    std::vector<double> out(out_len, 0.0);
    for (int i = 0; i < out_len && start + i < (int)full.size(); ++i)
        out[i] = full[start + i];
    return out;
}

// Aplica _dwt1 em cada linha; devolve (L, H) com metade das colunas.
inline void _rows_dwt(const cv::Mat& m, const std::vector<double>& dl,
                      const std::vector<double>& dh, cv::Mat& Lo, cv::Mat& Hi) {
    int R = m.rows, C = m.cols, oc = (C + (int)dl.size() - 1) / 2;
    Lo.create(R, oc, CV_64F); Hi.create(R, oc, CV_64F);
    std::vector<double> row(C), cA, cD;
    for (int y = 0; y < R; ++y) {
        for (int x = 0; x < C; ++x) row[x] = m.at<double>(y, x);
        _dwt1(row, dl, dh, cA, cD);
        for (int x = 0; x < oc; ++x) { Lo.at<double>(y, x) = cA[x]; Hi.at<double>(y, x) = cD[x]; }
    }
}
inline void _cols_dwt(const cv::Mat& m, const std::vector<double>& dl,
                      const std::vector<double>& dh, cv::Mat& Lo, cv::Mat& Hi) {
    cv::Mat mt = m.t(), lt, ht;
    _rows_dwt(mt, dl, dh, lt, ht);
    Lo = lt.t(); Hi = ht.t();
}

struct Subbands { cv::Mat LL, LH, HL, HH; };   // CV_64F

// pywt.dwt2(x, wavelet) -> (LL, (LH, HL, HH)). Convenção: dwt nas linhas
// (eixo -1), depois nas colunas (eixo -2).
inline Subbands dwt2(const cv::Mat& src, const std::string& wavelet = "haar") {
    std::vector<double> dl, dh, rl, rh;
    _wave_filters(wavelet, dl, dh, rl, rh);
    cv::Mat s; src.convertTo(s, CV_64F);
    cv::Mat Lo, Hi;
    _rows_dwt(s, dl, dh, Lo, Hi);
    Subbands o;
    _cols_dwt(Lo, dl, dh, o.LL, o.LH);
    _cols_dwt(Hi, dl, dh, o.HL, o.HH);
    return o;
}

inline cv::Mat idwt2(const Subbands& c, const std::string& wavelet = "haar") {
    std::vector<double> dl, dh, rl, rh;
    _wave_filters(wavelet, dl, dh, rl, rh);
    int Lc = (int)rl.size();
    // inverte colunas: (LL,LH)->Lo ; (HL,HH)->Hi ; out_rows = 2*n - (Lc-2)
    auto icols = [&](const cv::Mat& A, const cv::Mat& D) {
        cv::Mat At = A.t(), Dt = D.t();
        int n = At.cols, ol = 2 * n - (Lc - 2);
        cv::Mat R(At.rows, ol, CV_64F);
        std::vector<double> a(n), d(n);
        for (int y = 0; y < At.rows; ++y) {
            for (int i = 0; i < n; ++i) { a[i] = At.at<double>(y, i); d[i] = Dt.at<double>(y, i); }
            auto r = _idwt1(a, d, rl, rh, ol);
            for (int i = 0; i < ol; ++i) R.at<double>(y, i) = r[i];
        }
        return R.t();
    };
    cv::Mat Lo = icols(c.LL, c.LH), Hi = icols(c.HL, c.HH);
    // inverte linhas
    int n = Lo.cols, ol = 2 * n - (Lc - 2);
    cv::Mat out(Lo.rows, ol, CV_64F);
    std::vector<double> a(n), d(n);
    for (int y = 0; y < Lo.rows; ++y) {
        for (int i = 0; i < n; ++i) { a[i] = Lo.at<double>(y, i); d[i] = Hi.at<double>(y, i); }
        auto r = _idwt1(a, d, rl, rh, ol);
        for (int i = 0; i < ol; ++i) out.at<double>(y, i) = r[i];
    }
    return out;
}

// pywt.wavedec2 / waverec2 — multi-nível. detail[j] = {LH, HL, HH} do nível
// j+1 (j=0 é o mais fino). LL é a aproximação do nível mais grosso.
// detail[j] = {LH, HL, HH} do nível j (vector, não array — mais tolerante
// ao código que o tradutor gera).
struct WaveDec2 { cv::Mat LL; std::vector<std::vector<cv::Mat>> detail; };

inline WaveDec2 wavedec2(const cv::Mat& src, const std::string& wavelet, int level) {
    WaveDec2 c;
    cv::Mat cur; src.convertTo(cur, CV_64F);
    for (int l = 0; l < level; ++l) {
        Subbands sb = dwt2(cur, wavelet);
        c.detail.push_back({sb.LH, sb.HL, sb.HH});
        cur = sb.LL;
    }
    c.LL = cur;
    return c;
}

inline cv::Mat waverec2(const WaveDec2& c, const std::string& wavelet) {
    cv::Mat cur = c.LL;
    for (int l = (int)c.detail.size() - 1; l >= 0; --l) {
        Subbands sb;
        sb.LL = cur; sb.LH = c.detail[l][0];
        sb.HL = c.detail[l][1]; sb.HH = c.detail[l][2];
        // idwt2 pode devolver 1-2 px a mais por causa do padding do filtro —
        // recorta para o tamanho de LH (que tem as dims corretas do nível).
        cv::Mat r = idwt2(sb, wavelet);
        int rr = std::min(r.rows, sb.LH.rows * 2);
        int cc = std::min(r.cols, sb.LH.cols * 2);
        cur = r(cv::Rect(0, 0, cc, rr)).clone();
    }
    return cur;
}

// pywt.threshold(x, t, mode) — 'hard' zera |x|<=t ; 'soft' encolhe.
inline cv::Mat wave_threshold(const cv::Mat& x, double t,
                              const std::string& mode = "hard") {
    cv::Mat s; x.convertTo(s, CV_64F);
    cv::Mat o = s.clone();
    for (int y = 0; y < o.rows; ++y)
        for (int c = 0; c < o.cols; ++c) {
            double v = o.at<double>(y, c);
            if (mode == "soft") {
                double a = std::fabs(v) - t;
                o.at<double>(y, c) = a > 0 ? (v > 0 ? a : -a) : 0.0;
            } else {  // hard
                if (std::fabs(v) <= t) o.at<double>(y, c) = 0.0;
            }
        }
    return o;
}

// ── Domínio da frequência (cap05) ─────────────────────────────────────────
// Equivalente header-only do padrão np.fft.fft2 / fftshift / ifft2 usado no
// livro. Filtros H são cv::Mat CV_64F já CENTRADOS (DC no meio), mesma
// convenção de np.fft.fftshift. Operam sobre imagem de 1 canal.

// distancia_centro(M, N) do livro: matriz M×N (CV_64F) com a distância
// euclidiana de cada ponto (u,v) ao centro (M/2, N/2) do espectro centrado.
inline cv::Mat distCenter(int M, int N) {
    cv::Mat D(M, N, CV_64F);
    for (int u = 0; u < M; ++u) {
        double du = u - M / 2;
        for (int v = 0; v < N; ++v) {
            double dv = v - N / 2;
            D.at<double>(u, v) = std::sqrt(du * du + dv * dv);
        }
    }
    return D;
}

// Troca os 4 quadrantes de `m` no lugar. Para dimensões pares coincide com
// np.fft.fftshift E np.fft.ifftshift (ambos deslocam N/2); é o que as
// figuras do capítulo usam.
inline void _fftshift(cv::Mat& m) {
    int cx = m.cols / 2, cy = m.rows / 2;
    cv::Mat q0(m, cv::Rect(0, 0, cx, cy)),  q1(m, cv::Rect(cx, 0, cx, cy));
    cv::Mat q2(m, cv::Rect(0, cy, cx, cy)), q3(m, cv::Rect(cx, cy, cx, cy));
    cv::Mat t;
    q0.copyTo(t); q3.copyTo(q0); t.copyTo(q3);
    q1.copyTo(t); q2.copyTo(q1); t.copyTo(q2);
}

// np.fft.fftshift(np.fft.fft2(img)) — espectro complexo CENTRADO (CV_64FC2).
inline cv::Mat fft2c(const cv::Mat& img) {
    cv::Mat f; img.convertTo(f, CV_64F);
    cv::Mat planes[] = {f, cv::Mat::zeros(f.size(), CV_64F)};
    cv::Mat cpx; cv::merge(planes, 2, cpx);
    cv::dft(cpx, cpx, cv::DFT_COMPLEX_OUTPUT);
    _fftshift(cpx);
    return cpx;
}

// np.real(np.fft.ifft2(np.fft.ifftshift(Fc))) — CV_64F, 1 canal.
inline cv::Mat ifft2c(const cv::Mat& Fc) {
    cv::Mat F = Fc.clone();
    _fftshift(F);                       // desfaz o shift (par: == ifftshift)
    cv::Mat out;
    cv::idft(F, out, cv::DFT_SCALE | cv::DFT_REAL_OUTPUT);
    return out;
}

// Resposta espacial de um filtro real CENTRADO H:
// fftshift(real(ifft2(ifftshift(H)))) — o pico fica no centro para visualização
// (ex.: filtro Ideal na frequência -> sinc 2D no espaço, causa do ringing).
inline Image spatialKernel(const cv::Mat& H) {
    cv::Mat Hd; H.convertTo(Hd, CV_64F);
    cv::Mat planes[] = {Hd, cv::Mat::zeros(Hd.size(), CV_64F)};
    cv::Mat cpx; cv::merge(planes, 2, cpx);
    cv::Mat sp = ifft2c(cpx);
    _fftshift(sp);
    cv::Mat out; cv::normalize(sp, out, 0, 255, cv::NORM_MINMAX);
    out.convertTo(out, CV_8U);
    return Image(out);
}

// aplicar_filtro_freq(img, H) do livro: aplica o filtro centrado H (CV_64F,
// mesmo tamanho da imagem) via FFT e devolve a imagem filtrada normalizada
// para [0,255] (mm::Image, 1 canal).
inline Image freqFilter(const Image& img, const cv::Mat& H) {
    cv::Mat g = gray(img);                       // garante 1 canal (8-bit)
    cv::Mat src; g.convertTo(src, CV_64F);
    cv::Mat planes[2]; cv::split(fft2c(src), planes);
    cv::Mat Hd; H.convertTo(Hd, CV_64F);
    planes[0] = planes[0].mul(Hd);
    planes[1] = planes[1].mul(Hd);
    cv::Mat Fg; cv::merge(planes, 2, Fg);
    cv::Mat real = ifft2c(Fg), out;
    cv::normalize(real, out, 0, 255, cv::NORM_MINMAX);
    out.convertTo(out, CV_8U);
    return Image(out);
}

// Espectro de magnitude para visualização: log(1+|F|) normalizado [0,255]
// (cv2.normalize(np.log1p(np.abs(F)), ...) do livro). `img` de 1 canal.
inline Image spectrumMag(const Image& img) {
    cv::Mat g = gray(img), src; g.convertTo(src, CV_64F);
    cv::Mat planes[2]; cv::split(fft2c(src), planes);
    cv::Mat mag; cv::magnitude(planes[0], planes[1], mag);
    cv::log(mag + 1.0, mag);
    cv::Mat out; cv::normalize(mag, out, 0, 255, cv::NORM_MINMAX);
    out.convertTo(out, CV_8U);
    return Image(out);
}

// DCT-II / IDCT-II 2D ortonormais (== scipy.fft.dct(..., norm='ortho') 2D).
// Entrada/saída CV_64F; `cv::dct`/`cv::idct` do OpenCV já são ortonormais.
inline cv::Mat dct2(const cv::Mat& block) {
    cv::Mat b; block.convertTo(b, CV_64F);
    cv::Mat o; cv::dct(b, o); return o;
}
inline cv::Mat idct2(const cv::Mat& coef) {
    cv::Mat c; coef.convertTo(c, CV_64F);
    cv::Mat o; cv::idct(c, o); return o;
}

// ── Construtores de filtro no domínio da frequência (H centrado, CV_64F) ──
// Passe `highpass=true` para o complemento (1 - H). D0 = frequência de corte.
inline cv::Mat gaussFilter(int M, int N, double D0, bool highpass = false) {
    cv::Mat D = distCenter(M, N), H(M, N, CV_64F);
    for (int u = 0; u < M; ++u)
        for (int v = 0; v < N; ++v) {
            double d = D.at<double>(u, v);
            double lp = std::exp(-(d * d) / (2.0 * D0 * D0));
            H.at<double>(u, v) = highpass ? 1.0 - lp : lp;
        }
    return H;
}
inline cv::Mat idealFilter(int M, int N, double D0, bool highpass = false) {
    cv::Mat D = distCenter(M, N), H(M, N, CV_64F);
    for (int u = 0; u < M; ++u)
        for (int v = 0; v < N; ++v) {
            double lp = (D.at<double>(u, v) <= D0) ? 1.0 : 0.0;
            H.at<double>(u, v) = highpass ? 1.0 - lp : lp;
        }
    return H;
}
inline cv::Mat butterFilter(int M, int N, double D0, int n = 2,
                            bool highpass = false) {
    cv::Mat D = distCenter(M, N), H(M, N, CV_64F);
    for (int u = 0; u < M; ++u)
        for (int v = 0; v < N; ++v) {
            double lp = 1.0 / (1.0 + std::pow(D.at<double>(u, v) / D0, 2 * n));
            H.at<double>(u, v) = highpass ? 1.0 - lp : lp;
        }
    return H;
}

// ── Pipeline JPEG simplificado (cap05) ───────────────────────────────────
// DCT em blocos 8×8 -> quantização pela tabela de luminância escalada pelo
// fator de qualidade -> dequantização -> IDCT. `quality` em 1..100.
inline Image jpegCompress(const Image& img, int quality) {
    static const double QL[64] = {
        16,11,10,16,24,40,51,61,   12,12,14,19,26,58,60,55,
        14,13,16,24,40,57,69,56,   14,17,22,29,51,87,80,62,
        18,22,37,56,68,109,103,77, 24,35,55,64,81,104,113,92,
        49,64,78,87,103,121,120,101, 72,92,95,98,112,100,103,99};
    if (quality < 1) quality = 1;
    if (quality > 100) quality = 100;
    double escala = quality < 50 ? 5000.0 / quality : 200.0 - 2.0 * quality;
    cv::Mat Q(8, 8, CV_64F);
    for (int i = 0; i < 64; ++i)
        Q.at<double>(i / 8, i % 8) =
            std::min(255.0, std::max(1.0, std::round(QL[i] * escala / 100.0)));

    cv::Mat g = gray(img), src; g.convertTo(src, CV_64F);
    cv::Mat out = cv::Mat::zeros(src.size(), CV_64F);
    for (int r = 0; r + 8 <= src.rows; r += 8)
        for (int c = 0; c + 8 <= src.cols; c += 8) {
            cv::Mat blk = src(cv::Rect(c, r, 8, 8)).clone() - 128.0;
            cv::Mat C = dct2(blk), Cq(8, 8, CV_64F);
            for (int y = 0; y < 8; ++y)
                for (int x = 0; x < 8; ++x) {
                    double q = Q.at<double>(y, x);
                    Cq.at<double>(y, x) = std::round(C.at<double>(y, x) / q) * q;
                }
            cv::Mat rec = idct2(Cq) + 128.0;
            rec.copyTo(out(cv::Rect(c, r, 8, 8)));
        }
    cv::Mat o8; out.convertTo(o8, CV_8U);   // convertTo satura em [0,255]
    return Image(o8);
}

// ── Gráfico de linhas header-only (cap05) ────────────────────────────────
// Substitui os gráficos matplotlib nas células da trilha C++. `xs[k]`/`ys[k]`
// são a k-ésima curva; `colors` em BGR (ciclo padrão se vazio); `labels` para
// a legenda (opcional). Devolve uma imagem BGR pronta para mm::show.
inline Image lineChart(const std::vector<std::vector<double>>& xs,
                       const std::vector<std::vector<double>>& ys,
                       std::vector<cv::Scalar> colors = {},
                       std::vector<std::string> labels = {},
                       const std::string& title = "",
                       const std::string& xlabel = "",
                       const std::string& ylabel = "",
                       int width = 760, int height = 420,
                       bool logx = false, bool logy = false) {
    const std::vector<cv::Scalar> CYCLE = {
        {48, 90, 216}, {117, 158, 29}, {183, 74, 83}, {40, 39, 214},
        {148, 103, 189}, {75, 119, 44}, {33, 145, 237}};
    auto tx = [&](double v) { return logx ? std::log10(std::max(v, 1e-12)) : v; };
    auto ty = [&](double v) { return logy ? std::log10(std::max(v, 1e-12)) : v; };

    double xmin = 1e300, xmax = -1e300, ymin = 1e300, ymax = -1e300;
    for (size_t k = 0; k < xs.size(); ++k)
        for (size_t i = 0; i < xs[k].size(); ++i) {
            double X = tx(xs[k][i]), Y = ty(ys[k][i]);
            if (!std::isfinite(X) || !std::isfinite(Y)) continue;
            xmin = std::min(xmin, X); xmax = std::max(xmax, X);
            ymin = std::min(ymin, Y); ymax = std::max(ymax, Y);
        }
    if (xmax <= xmin) xmax = xmin + 1;
    if (ymax <= ymin) ymax = ymin + 1;
    double ypad = 0.06 * (ymax - ymin);
    bool ynonneg = ymin >= 0.0;
    ymin -= ypad; ymax += ypad;
    if (ynonneg && ymin < 0.0) ymin = 0.0;   // não inventar eixo negativo

    const int L = 62, R = 18, T = title.empty() ? 18 : 40, B = 46;
    cv::Mat cv_(height, width, CV_8UC3, cv::Scalar(255, 255, 255));
    cv::Rect plot(L, T, width - L - R, height - T - B);
    cv::rectangle(cv_, plot, cv::Scalar(150, 150, 150), 1);

    auto px = [&](double X) {
        return (int)std::lround(plot.x + (tx(X) - xmin) / (xmax - xmin) * plot.width);
    };
    auto py = [&](double Y) {
        return (int)std::lround(plot.y + plot.height -
                                (ty(Y) - ymin) / (ymax - ymin) * plot.height);
    };

    // grade + rótulos numéricos (5×4)
    for (int i = 0; i <= 5; ++i) {
        double X = xmin + (xmax - xmin) * i / 5.0;
        int gx = plot.x + plot.width * i / 5;
        cv::line(cv_, {gx, plot.y}, {gx, plot.y + plot.height},
                 cv::Scalar(230, 230, 230), 1);
        char buf[32];
        std::snprintf(buf, sizeof buf, "%.3g", logx ? std::pow(10, X) : X);
        cv::putText(cv_, buf, {gx - 14, plot.y + plot.height + 16},
                    cv::FONT_HERSHEY_SIMPLEX, 0.38, cv::Scalar(90, 90, 90), 1, cv::LINE_AA);
    }
    for (int j = 0; j <= 4; ++j) {
        double Y = ymin + (ymax - ymin) * j / 4.0;
        int gy = plot.y + plot.height - plot.height * j / 4;
        cv::line(cv_, {plot.x, gy}, {plot.x + plot.width, gy},
                 cv::Scalar(230, 230, 230), 1);
        char buf[32];
        std::snprintf(buf, sizeof buf, "%.3g", logy ? std::pow(10, Y) : Y);
        cv::putText(cv_, buf, {6, gy + 4}, cv::FONT_HERSHEY_SIMPLEX, 0.38,
                    cv::Scalar(90, 90, 90), 1, cv::LINE_AA);
    }

    // curvas
    for (size_t k = 0; k < xs.size(); ++k) {
        cv::Scalar col = k < colors.size() ? colors[k] : CYCLE[k % CYCLE.size()];
        std::vector<cv::Point> pts;
        for (size_t i = 0; i < xs[k].size() && i < ys[k].size(); ++i)
            pts.push_back({px(xs[k][i]), py(ys[k][i])});
        for (size_t i = 1; i < pts.size(); ++i)
            cv::line(cv_, pts[i - 1], pts[i], col, 2, cv::LINE_AA);
        for (const auto& p : pts) cv::circle(cv_, p, 2, col, -1, cv::LINE_AA);
    }

    // legenda — largura proporcional ao rótulo mais longo
    if (!labels.empty()) {
        size_t maxlen = 0;
        for (const auto& s : labels) maxlen = std::max(maxlen, s.size());
        int boxw = std::min(plot.width - 20, 34 + (int)maxlen * 7);
        int lx = plot.x + plot.width - boxw;
        for (size_t k = 0; k < labels.size(); ++k) {
            cv::Scalar col = k < colors.size() ? colors[k] : CYCLE[k % CYCLE.size()];
            int ly = plot.y + 14 + (int)k * 16;
            cv::line(cv_, {lx, ly}, {lx + 20, ly}, col, 2, cv::LINE_AA);
            cv::putText(cv_, labels[k], {lx + 25, ly + 4},
                        cv::FONT_HERSHEY_SIMPLEX, 0.38, cv::Scalar(60, 60, 60), 1, cv::LINE_AA);
        }
    }
    if (!title.empty())
        cv::putText(cv_, title, {L, 26}, cv::FONT_HERSHEY_SIMPLEX, 0.6,
                    cv::Scalar(30, 30, 30), 1, cv::LINE_AA);
    if (!xlabel.empty())
        cv::putText(cv_, xlabel, {width / 2 - 40, height - 8},
                    cv::FONT_HERSHEY_SIMPLEX, 0.45, cv::Scalar(60, 60, 60), 1, cv::LINE_AA);
    if (!ylabel.empty())
        cv::putText(cv_, ylabel, {6, T - 6}, cv::FONT_HERSHEY_SIMPLEX, 0.45,
                    cv::Scalar(60, 60, 60), 1, cv::LINE_AA);
    return Image(cv_);
}

// pywt.Wavelet(name).wavefun(level) -> (x, phi, psi) via algoritmo em cascata
// (upsample + convolução com os filtros de reconstrução). Forma compatível com
// o PyWavelets; suficiente para o gráfico de ψ do cap05. name: haar|db4|sym4|bior2.2.
inline void wavefun(const std::string& name, int level,
                    std::vector<double>& x, std::vector<double>& phi,
                    std::vector<double>& psi) {
    std::vector<double> dl, dh, rl, rh;
    _wave_filters(name, dl, dh, rl, rh);
    auto up = [](const std::vector<double>& v) {
        std::vector<double> o(v.empty() ? 0 : v.size() * 2 - 1, 0.0);
        for (size_t i = 0; i < v.size(); ++i) o[i * 2] = v[i];
        return o;
    };
    auto conv = [](const std::vector<double>& a, const std::vector<double>& b) {
        std::vector<double> o(a.size() + b.size() - 1, 0.0);
        for (size_t i = 0; i < a.size(); ++i)
            for (size_t j = 0; j < b.size(); ++j) o[i + j] += a[i] * b[j];
        return o;
    };
    // Cascata (rl/rh do _wave_filters já somam ±sqrt(2), sem fator extra):
    //   phi: level iterações  conv(up(.), rl)
    //   psi: 1ª iteração conv(up(.), rh), demais conv(up(.), rl)  -> mesmo comprimento
    int lv = std::max(1, level);
    std::vector<double> p = {1.0};
    for (int it = 0; it < lv; ++it) p = conv(up(p), rl);
    std::vector<double> q = conv(up(std::vector<double>{1.0}), rh);
    for (int it = 1; it < lv; ++it) q = conv(up(q), rl);
    phi = p; psi = q;
    int n = (int)std::min(phi.size(), psi.size());
    phi.resize(n); psi.resize(n);
    double span = (double)(rl.size() - 1);
    x.resize(n);
    for (int i = 0; i < n; ++i) x[i] = n > 1 ? span * i / (n - 1) : 0.0;
}

// Overload: um único eixo x compartilhado por todas as curvas de `ys`.
inline Image lineChart(const std::vector<double>& x,
                       const std::vector<std::vector<double>>& ys,
                       std::vector<cv::Scalar> colors = {},
                       std::vector<std::string> labels = {},
                       const std::string& title = "",
                       const std::string& xlabel = "",
                       const std::string& ylabel = "",
                       int width = 760, int height = 420,
                       bool logx = false, bool logy = false) {
    std::vector<std::vector<double>> xs(ys.size(), x);
    return lineChart(xs, ys, std::move(colors), std::move(labels),
                     title, xlabel, ylabel, width, height, logx, logy);
}

// Overloads genéricos: aceitam vetores de QUALQUER tipo numérico (ex.:
// std::vector<int> para tamanhos de kernel). Convertem para double e delegam.
template <class Tx, class Ty>
inline Image lineChart(const std::vector<Tx>& x,
                       const std::vector<std::vector<Ty>>& ys,
                       std::vector<cv::Scalar> colors = {},
                       std::vector<std::string> labels = {},
                       const std::string& title = "", const std::string& xlabel = "",
                       const std::string& ylabel = "", int width = 760, int height = 420,
                       bool logx = false, bool logy = false) {
    std::vector<double> xd(x.begin(), x.end());
    std::vector<std::vector<double>> yd;
    for (const auto& v : ys) yd.emplace_back(v.begin(), v.end());
    return lineChart(xd, yd, std::move(colors), std::move(labels),
                     title, xlabel, ylabel, width, height, logx, logy);
}
template <class Tx, class Ty>
inline Image lineChart(const std::vector<std::vector<Tx>>& xs,
                       const std::vector<std::vector<Ty>>& ys,
                       std::vector<cv::Scalar> colors = {},
                       std::vector<std::string> labels = {},
                       const std::string& title = "", const std::string& xlabel = "",
                       const std::string& ylabel = "", int width = 760, int height = 420,
                       bool logx = false, bool logy = false) {
    std::vector<std::vector<double>> xd, yd;
    for (const auto& v : xs) xd.emplace_back(v.begin(), v.end());
    for (const auto& v : ys) yd.emplace_back(v.begin(), v.end());
    return lineChart(xd, yd, std::move(colors), std::move(labels),
                     title, xlabel, ylabel, width, height, logx, logy);
}

// PSNR entre duas imagens (dB) — espelha cv::PSNR. Harmoniza canais/tamanho
// (mm::read devolve 3 canais mesmo para PNG cinza; jpeg/etc. devolvem 1).
inline double psnr(const Image& a, const Image& b) {
    cv::Mat ma = (a.channels == 1) ? (cv::Mat)a : (cv::Mat)gray(a);
    cv::Mat mb = (b.channels == 1) ? (cv::Mat)b : (cv::Mat)gray(b);
    if (ma.size() != mb.size()) cv::resize(mb, mb, ma.size());
    return cv::PSNR(ma, mb);
}

#endif  // MM_USE_OPENCV

}  // namespace mm
