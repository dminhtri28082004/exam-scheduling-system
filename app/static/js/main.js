// Common JavaScript functions

// Format date to Vietnamese format
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('vi-VN');
}

// Format time to HH:MM format
function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

// Check if token is expired and redirect to login
function checkAuth() {
    const token = getCookie('access_token');
    if (!token) {
        window.location.href = '/ui/login';
    }
}

// Get cookie by name
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
}

// Get token for API requests
function getAuthToken() {
    const tokenCookie = getCookie('access_token');
    
    // If the token already starts with 'Bearer ', return it as is
    if (tokenCookie.startsWith('Bearer ')) {
        return tokenCookie;
    }
    
    // Otherwise, add the Bearer prefix
    return tokenCookie ? `Bearer ${tokenCookie}` : '';
}

// Document ready handler
document.addEventListener('DOMContentLoaded', function() {
    // Enable Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
