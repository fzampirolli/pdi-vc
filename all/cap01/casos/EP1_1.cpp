// %%writefile EP1_1.cpp
#include <iostream> // Para cout, endl
#include <iomanip>  // Para fixed, setprecision

int main() {
    int C = 65;

    float F = C * (9.0/5) + 32;

    // Configura a saída para mostrar sempre 1 casa decimal (ex: 149.0)
    std::cout << std::fixed << std::setprecision(1);

    std::cout << C << " graus Celsius corresponde a " << F << " graus Fahrenheit" << std::endl;

    return 0;
}