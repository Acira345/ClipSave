console.log("Hello, World!");
//console.warn("This is a warning message.");
//console.error("This is an error message.");
//alert("This is an alert message.");

console.log("Alumnos");
console.table(alumnos);

const alumnos = [
  { nombre: "Juan", nota: 8.5, carrera: "Ingeniería" },
  { nombre: "María", nota: 9.0, carrera: "Medicina" },
  { nombre: "Pedro", nota: 7.5, carrera: "Derecho" },
];

console.log("Alumnos con nota mayor a 8:");

const nombre = prompt("Ingrese su nombre:");
console.log("Hola, " + nombre + "! Bienvenido al programa.");