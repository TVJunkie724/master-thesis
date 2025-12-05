document.addEventListener("DOMContentLoaded", async () => {

  /* ============================================================
     1. Load sidebar HTML dynamically
     ============================================================ */
  const placeholder = document.getElementById("nav-placeholder");
  if (!placeholder) return;

  try {
    const resp = await fetch("docs-nav.html");
    placeholder.innerHTML = await resp.text();
  } catch (err) {
    console.error("Navigation load failed:", err);
    return; // Stop if nav failed
  }

  /* ============================================================
     2. Sidebar collapse / expand
     ============================================================ */
  const sidebar = document.getElementById("sidebar");
  const layout = document.querySelector(".layout");
  const toggle = document.getElementById("sidebar-toggle");

  if (toggle && sidebar && layout) {
    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      layout.classList.toggle("sidebar-collapsed");
    });
  }

  /* ============================================================
     3. Highlight active menu link
     ============================================================ */
  const current = window.location.pathname.replace(/\/$/, "");
  const links = placeholder.querySelectorAll("a.nav-link");

  links.forEach(link => {
    const href = link.getAttribute("href")?.replace(/\/$/, "");
    if (!href) return;

    if (current.endsWith(href)) {
      link.classList.add("active");
      link.classList.add("bg-primary");
      link.classList.add("text-white");
    }
  });

  /* ============================================================
     4. Insert <wbr> to allow breaking long field names at dots
     ============================================================ */
  document.querySelectorAll("td.mono, th.mono").forEach(cell => {
    cell.innerHTML = cell.innerText.replace(/\./g, ".<wbr>");
  });

  /* ============================================================
     5. Bootstrap-like Back-to-Top Button
     ============================================================ */
  const backToTop = document.getElementById("backToTop");
  const main = document.querySelector(".layout main");

  console.log("BackToTop element:", backToTop, " | main:", main);

  if (backToTop && main) {

    function updateBtnVisibility() {
      const scrollY = main.scrollTop || window.scrollY;
      if (scrollY > 300) {
        backToTop.style.display = "flex";
        backToTop.classList.add("show");
      } else {
        backToTop.classList.remove("show");
        backToTop.style.display = "none";
      }
    }

    main.addEventListener("scroll", updateBtnVisibility);
    window.addEventListener("scroll", updateBtnVisibility);

    backToTop.addEventListener("click", () =>
      main.scrollTo({ top: 0, behavior: "smooth" })
    );
  }


});
