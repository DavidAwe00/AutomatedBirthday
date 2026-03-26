// Auto-dismiss flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s, transform 0.4s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-6px)';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
});

// Clear search helper (called inline from template)
function clearSearch() {
  const input = document.getElementById('searchInput');
  if (input) {
    input.value = '';
    input.closest('form').submit();
  }
}

// Register PWA service worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}
