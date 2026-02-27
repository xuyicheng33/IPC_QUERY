function initHomePage() {
  const form = $("#homeSearchForm");
  const input = $("#homeQ");
  if (!form || !input) return;

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const q = (input.value || "").trim();
    if (!q) {
      input.focus();
      return;
    }
    const params = new URLSearchParams();
    params.set("q", q);
    params.set("match", "pn");
    params.set("page", "1");
    window.location.href = `/search?${params.toString()}`;
  });
}
