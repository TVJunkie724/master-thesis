// docs-nav.js
async function loadSidebar() {
  try {
    const response = await fetch("../docs/docs-nav.html");
    const html = await response.text();
    const sidebarContainer = document.getElementById("sidebar-container");
    if (sidebarContainer) {
      sidebarContainer.innerHTML = html;
    }
  } catch (err) {
    console.error("Failed to load sidebar:", err);
  }
}

function toggleSidebar() {
  document.querySelector(".sidebar").classList.toggle("collapsed");
  document.getElementById("sidebar-toggle").classList.toggle("collapsed");
}

// Load sidebar on page ready
document.addEventListener("DOMContentLoaded", loadSidebar);
