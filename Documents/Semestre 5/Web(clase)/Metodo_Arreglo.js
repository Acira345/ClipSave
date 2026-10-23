// 1. Arreglo base
const datos = [
  { id: 1, titulo: "The Legend of Zelda", genero: "Aventura", precio: 60, enOferta: false, detalles: { horasJuego: 100 } },
  { id: 2, titulo: "Hollow Knight", genero: "Metroidvania", precio: 15, enOferta: true, detalles: { horasJuego: 40 } },
  { id: 3, titulo: "Elden Ring", genero: "RPG", precio: 50, enOferta: true, detalles: { horasJuego: 120 } },
  { id: 4, titulo: "Celeste", genero: "Plataformas", precio: 20, enOferta: true },
  { id: 5, titulo: "Cyberpunk 2077", genero: "RPG", precio: 45, enOferta: false, detalles: { horasJuego: 80 } }
];

// 1. Lista filtrada con los juegos que estan en oferta
const filtrados = datos.filter(({ enOferta }) => enOferta === true);

// 2. Total de un campo numérico: Sumar el precio de todos los videeojuegos
const total = datos.reduce((acumulador, { precio }) => acumulador + precio, 0);

// 3. Promedio de ese campo: Dividir el total entre la cantidad de elementos
const promedio = total / datos.length;

// 4. Lista ordenada: Ordenar por horas de juego de menor a mayor
const ordenados = [...datos].sort((a, b) => {
  const horasA = a.detalles?.horasJuego ?? 0;
  const horasB = b.detalles?.horasJuego ?? 0;
  return horasA - horasB;
});

console.log({ filtrados, total, promedio, ordenados });

// Verificación de que el arreglo original no se modifico
console.log("Arreglo original intacto:", datos);