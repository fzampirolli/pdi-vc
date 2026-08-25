# Bibliotecas de terceiros vendorizadas

## stb_image.h / stb_image_write.h

- Origem: https://github.com/nothings/stb
- Commit fixado: `2c980bb59875b0d32144a71867fbdebb2f77cd20` (2026-08-02)
- Versões: stb_image v2.30, stb_image_write v1.16
- Licença: domínio público (Unlicense) OU MIT, à escolha do usuário — ver cabeçalho
  de cada arquivo (seção "LICENSE" ao final de cada header).
- Autor: Sean Barrett e colaboradores.

Usadas por `morph/cpp/morph.hpp` para decodificar/codificar PNG/JPEG sem depender
de OpenCV ou de qualquer biblioteca de sistema — mantém o `g++` simples o
suficiente pra compilar em uma célula `%%writefile` + `!g++ ...` no Colab, sem
`apt install` adicional.

Para atualizar a versão fixada:

```bash
SHA=<novo commit sha de nothings/stb>
curl -sL "https://raw.githubusercontent.com/nothings/stb/${SHA}/stb_image.h" -o morph/cpp/stb_image.h
curl -sL "https://raw.githubusercontent.com/nothings/stb/${SHA}/stb_image_write.h" -o morph/cpp/stb_image_write.h
```
