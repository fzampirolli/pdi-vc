import java.util.Scanner;
class EP1_2 {
  public static void main(String[] args) {
    Scanner teclado1 = new Scanner(System.in);
    int C = teclado1.nextInt();
    float F = C * 9/5 + 32;
    System.out.println(C + " graus Celsius corresponde a " + F + " graus Fahrenheit");
  }
}