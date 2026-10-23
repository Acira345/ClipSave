class CuentaBancaria {
  #saldo;

  constructor(titular, saldoInicial) {
    this.titular = titular;
    this.#saldo = saldoInicial >= 0 ? saldoInicial : 0;
  }

  get saldoActual() {
    return `$${this.#saldo} MXN`;
  }

  set nuevoSaldo(monto) {
    if (monto < 0) {
      console.log("Error: No se puede asignar un saldo negativo.");
    } else {
      this.#saldo = monto;
      console.log(`Saldo ajustado correctamente a $${this.#saldo} MXN`);
    }
  }

  depositar(cantidad) {
    if (cantidad > 0) {
      this.#saldo += cantidad;
      console.log(`${this.titular} depositó $${cantidad}. Total: ${this.saldoActual}`);
    }
  }
}

class CuentaAhorro extends CuentaBancaria {
  constructor(titular, saldoInicial, tasaInteres) {
    super(titular, saldoInicial);
    this.tasaInteres = tasaInteres;
  }

  mostrarDetalles() {
    console.log(`Cuenta de Ahorro de ${this.titular} | Saldo: ${this.saldoActual} | Interés: ${this.tasaInteres}%`);
  }
}

const miCuenta = new CuentaAhorro("Ana Gómez", 1000, 5);

miCuenta.mostrarDetalles();
miCuenta.depositar(500);

console.log("Consulta mediante getter:", miCuenta.saldoActual);

miCuenta.nuevoSaldo = -200; // Disparará la validación de error
miCuenta.nuevoSaldo = 2500; // Actualizará el campo privado #saldo
