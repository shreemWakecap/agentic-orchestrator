/**
 * Dashboard page functionality
 * Handles plan creation form submission
 */

function initDashboard() {
    const form = document.getElementById('plan-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const input = document.getElementById('plan-description');
        const description = input.value;
        const button = this.querySelector('button[type="submit"]');

        if (!description.trim()) {
            input.focus();
            input.style.borderColor = '#EF4444';
            setTimeout(() => input.style.borderColor = '', 2000);
            return;
        }

        button.disabled = true;
        button.textContent = 'Creating...';

        try {
            const response = await fetch('/api/workflows/plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: description })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            if (data.run_id) {
                window.location.href = '/runs/' + data.run_id;
            } else {
                throw new Error('No run_id in response');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to create plan: ' + error.message);
            button.disabled = false;
            button.textContent = 'Create Plan';
        }
    });
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', initDashboard);
