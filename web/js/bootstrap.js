function bootstrap() {
  const page = (document.body?.dataset?.page || "").toString();
  if (page === "home") {
    initHomePage();
    return;
  }
  if (page === "search") {
    initSearchPage();
    return;
  }
  if (page === "detail") {
    initDetailPage();
    return;
  }
  if (page === "db") {
    initDbPage();
  }
}

window.__IPC_BOOTSTRAP_AVAILABLE = true;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
