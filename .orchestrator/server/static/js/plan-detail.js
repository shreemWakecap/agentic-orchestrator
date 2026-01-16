/**
 * Plan detail page functionality
 * Handles starting builds and reviews for plans
 */

async function startBuild(planPath) {
    try {
        const response = await fetch('/api/workflows/build', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_path: planPath })
        });
        const data = await response.json();
        if (data.run_id) {
            window.location.href = '/runs/' + data.run_id;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to start build');
    }
}

async function startReview(planPath) {
    try {
        const response = await fetch('/api/workflows/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_path: planPath, refresh_docs: false })
        });
        const data = await response.json();
        if (data.run_id) {
            window.location.href = '/runs/' + data.run_id;
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to start review');
    }
}
