#include <iostream> // Para cout, cin, endl
#include <iomanip>  // Para fixed, setprecision

int main() {
  // std::cout << "Entre com C: " << std::endl;
  int C;
  std::cin >> C;

  // Atenção: A operação 9/5 em C++ com inteiros resulta em 1 (divisão inteira).
  // Para obter o resultado correto, um dos números precisa ser float/double.
  float F = C * 9.0/5 + 32; // Use 9.0 ou 5.0 para forçar a divisão de ponto flutuante

  std::cout << std::fixed << std::setprecision(1); // Fixa a saída em uma casa decimal
  std::cout << C << " graus Celsius corresponde a " << F << " graus Fahrenheit" << std::endl;

  return 0; // Boa prática: indica que o programa terminou com sucesso
}