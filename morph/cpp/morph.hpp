// morph.hpp — v0
//
// Equivalente C++ mínimo da morph.py: só as 7 funções que o cap01 usa
// (read, gray, randomImage, show, write, threshold, drawImg). Header-only,
// pensado pra compilar com um `g++ arquivo.cpp -o arquivo` simples, sem
// dependência de OpenCV — usa stb_image/stb_image_write (vendorizadas ao
// lado, ver THIRD_PARTY_LICENSES.md) pra ler/escrever PNG/JPEG.
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
#include <cstdint>
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

inline Image threshold(const Image& img, std::optional<int> limiar = std::nullopt) {
    Image src = (img.channels == 1) ? img : gray(img);
    int T;
    if (limiar.has_value()) {
        T = *limiar;
    } else {
        // Otsu: maximiza a variância entre classes sobre o histograma 256-bin.
        int hist[256] = {0};
        for (auto v : src.data) hist[v]++;
        int total = (int)src.data.size();
        double sum = 0;
        for (int i = 0; i < 256; ++i) sum += i * hist[i];
        double sumB = 0;
        int wB = 0;
        double maxVar = 0;
        T = 0;
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
    }
    Image out(src.h, src.w, 1);
    for (size_t i = 0; i < src.data.size(); ++i)
        out.data[i] = (src.data[i] > T) ? 255 : 0;
    return out;
}

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

}  // namespace mm
