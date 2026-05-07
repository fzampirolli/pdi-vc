#include <stdio.h>

int main() { 
  int C;
  scanf("%d", &C);

  // Importante: 9.0 garante que a divisão seja decimal (float).
  // Se fosse apenas 9/5, o C faria divisão inteira (resultado 1).
  float F = C * 9.0 / 5 + 32;

  printf("%d graus Celsius corresponde a %.1f graus Fahrenheit\n", C, F);

  return 0;
}