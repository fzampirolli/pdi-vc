# Valor Fixo (conforme pede EP1_1)
C <- 65

# Cálculo
F <- C * 9/5 + 32

# sprintf garante a formatação %.1f (um decimal)
# cat imprime sem índices [1] que o print() coloca
cat(sprintf("%d graus Celsius corresponde a %.1f graus Fahrenheit\n", C, F))