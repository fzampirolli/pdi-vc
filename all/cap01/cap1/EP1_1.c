#include <stdio.h>

int main() {
  int C = 65;
  // Note o 9.0 para garantir que a divisão seja feita em ponto flutuante
  float F = C * 9.0/5 + 32;

  // %.1f define a formatação para 1 casa decimal
  printf("%d graus Celsius corresponde a %.1f graus Fahrenheit\n", C, F);

  return 0;
}