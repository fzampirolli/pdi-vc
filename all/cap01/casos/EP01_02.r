C <- as.integer(readLines("stdin", n=1))
F <- C * 9/5 + 32
cat(C, "graus Celsius corresponde a", format(F, nsmall = 1), "graus Fahrenheit\n")