function openExternalLinksInNewTab() {
  const currentHost = window.location.host;

  document.querySelectorAll('a[href^="http://"], a[href^="https://"]').forEach((link) => {
    const url = new URL(link.href);
    if (url.host === currentHost) {
      return;
    }

    link.target = "_blank";
    link.rel = "noopener noreferrer";
  });
}

document.addEventListener("DOMContentLoaded", openExternalLinksInNewTab);
if (typeof document$ !== "undefined") {
  document$.subscribe(openExternalLinksInNewTab);
}
