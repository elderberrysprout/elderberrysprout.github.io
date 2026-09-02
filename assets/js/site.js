document.querySelector(".nav-toggle")?.addEventListener("click", () => {
  const nav = document.querySelector(".site-nav");
  const btn = document.querySelector(".nav-toggle");
  const open = nav.classList.toggle("open");
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.setAttribute("aria-label", open ? "Close Menu" : "Open Menu");
});
