// “Database” of restaurants
const RESTAURANTS = {
  "chicken-tikka-masala": {
    img:    "../assets/images/chicken_tikka_masala.jpg",
    title:  "Chicken Tikka Masala",
    stars:  "★★★★☆",
    status: "Open · Closes 10:00 pm",
    eta:    "15 min by car",
    lat:    41.8781,
    lng:   -87.6298,
    menuUrl: "https://example.com/tikka-menu"
  },
  "spicy-rigatoni": {
    img:    "../assets/images/spicy-chicken-rigatoni.png",
    title:  "Spicy Sausage Rigatoni",
    stars:  "★★★☆☆",
    status: "Open · Closes 9:30 pm",
    eta:    "10 min by car",
    lat:    40.7128,
    lng:   -74.0060,
    menuUrl: "https://example.com/rigatoni-menu"
  },
  "spicy-tuna-roll": {
    img:    "../assets/images/spicytunaroll.jpg",
    title:  "Spicy Tuna Roll",
    stars:  "★★★☆☆",
    status: "Open · Closes 11:00 pm",
    eta:    "20 min by car",
    lat:    37.7749,
    lng:   -122.4194,
    menuUrl: "https://example.com/tuna-menu"
  }
};

// Called by each “→” arrow in recommendations.html
function goToMap(btn) {
  const card = btn.closest(".rec-card");
  const id   = card.dataset.id;
  window.location.href = `map-view?restaurant=${encodeURIComponent(id)}`;
}

// Maps API callback
function initMap() {
  // 1) Read the slug
  const params = new URLSearchParams(window.location.search);
  const id     = params.get("restaurant");
  console.log("initMap(): restaurant slug =", id);

  // 2) Lookup data
  const data = RESTAURANTS[id];
  if (!data) {
    console.error("Unknown restaurant id:", id);
    // Optionally show an error message in the UI here
    return;
  }

  // 3) Fill in the info‑card
  document.getElementById("rest-img").src         = data.img;
  document.getElementById("rest-img").alt         = data.title;
  document.getElementById("rest-title").textContent  = data.title;
  document.getElementById("rest-stars").textContent  = data.stars;
  document.getElementById("rest-status").textContent = data.status;
  document.getElementById("rest-eta").textContent    = data.eta;

  // 4) Draw the map at the correct coords
  const map = new google.maps.Map(
    document.getElementById("map-container"),
    { center: { lat: data.lat, lng: data.lng }, zoom: 14 }
  );
  new google.maps.Marker({ position: { lat: data.lat, lng: data.lng }, map });

  // 5) Wire up “View Menu”
  const menuBtn = document.getElementById("menu-btn");
  menuBtn.onclick = () => {
    if (data.menuUrl) window.open(data.menuUrl, "_blank");
  };
}
// ─── Group‑Sync “＋” Button Toggle ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // keep track of who’s in the group
  const group = new Set();

  // grab all of the little “＋” buttons
  document.querySelectorAll('.add-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const card = btn.closest('.contact-card');
      const name = card.querySelector('.contact-info h3').textContent.trim();

      if (group.has(name)) {
        // if already in group, remove them
        group.delete(name);
        btn.textContent = '＋';
        btn.classList.remove('added');
      } else {
        // otherwise add them
        group.add(name);
        btn.textContent = '✓';
        btn.classList.add('added');
      }

      console.log('Current group members:', Array.from(group));
    });
  });
});
