const dishes = [
  { title: "Chicken Tikka Masala", img: "/assets/images/chicken_tikka_masala.jpg" },
  { title: "Spicy Sausage Rigatoni", img: "/assets/images/spicy-chicken-rigatoni.png" },
  { title: "Spicy Tuna Roll", img: "/assets/images/spicytunaroll.jpg" },
  { title: "Pizza", img: "/assets/images/pizza.png" },
  { title: "Tacos", img: "/assets/images/tacos.png" },
  { title: "Pancakes", img: "/assets/images/pancakes.png" }
];

let currentIndex = 0;
const container = document.querySelector(".swipe-container");

function showCard(i) {
  container.innerHTML = "";
  if (i >= dishes.length) {
    window.location.href = "/pages/recommendations.html";
    return;
  }
  const { title, img } = dishes[i];
  const card = document.createElement("div");
  card.className = "swipe-card";
  card.style.backgroundImage = `url(${img})`;
  const h2 = document.createElement("div");
  h2.className = "swipe-title";
  h2.textContent = title;
  card.appendChild(h2);
  container.appendChild(card);
}

function swipe(dir) {
  const card = container.querySelector(".swipe-card");
  if (!card) return;
  const x = dir === "right" ? window.innerWidth : -window.innerWidth;
  card.style.transform = `translateX(${x}px) rotate(${dir === "right" ? 30 : -30}deg)`;
  card.style.opacity = 0;
  setTimeout(() => {
    currentIndex++;
    showCard(currentIndex);
  }, 300);
}

document.getElementById("like-btn").onclick    = () => swipe("right");
document.getElementById("dislike-btn").onclick = () => swipe("left");

let startX = 0;
container.addEventListener("touchstart", e => startX = e.touches[0].clientX);
container.addEventListener("touchend", e => {
  const endX = e.changedTouches[0].clientX;
  if (endX - startX > 50)      swipe("right");
  else if (startX - endX > 50) swipe("left");
});

showCard(currentIndex);
