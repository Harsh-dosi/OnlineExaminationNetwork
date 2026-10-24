// Online Examination Network — main.js
// Auto-dismiss flash alerts, utility helpers

document.addEventListener('DOMContentLoaded', function() {
  // Auto-dismiss flash messages after 6 seconds
  document.querySelectorAll('.alert').forEach(function(el) {
    setTimeout(function() {
      el.style.opacity = '0';
      el.style.transform = 'translateX(100%)';
      el.style.transition = 'all 0.4s ease';
      setTimeout(() => el.remove(), 400);
    }, 6000);
  });
});
