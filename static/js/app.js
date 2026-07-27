// Minimal JS utilities - main logic is in inline scripts per page
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss flash messages after 5s
    document.querySelectorAll('.flash').forEach(function(el) {
        setTimeout(function() { el.style.display = 'none'; }, 5000);
    });
});
