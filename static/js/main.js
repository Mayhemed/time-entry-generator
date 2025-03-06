document.addEventListener('DOMContentLoaded', function() {
    console.log('Time Entry Generator/Auditor system initialized');
    
    // Add event handlers for UI components if needed
    const buildTimelineBtn = document.getElementById('build-timeline-btn');
    if (buildTimelineBtn) {
        buildTimelineBtn.addEventListener('click', function() {
            this.disabled = true;
            this.textContent = 'Processing...';
            
            fetch('/build-timeline', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('relationship-count').textContent = data.relationship_count || 0;
                this.disabled = false;
                this.textContent = 'Build Timeline';
                alert('Timeline built successfully! ' + data.relationship_count + ' relationships identified.');
            })
            .catch(error => {
                console.error('Error:', error);
                this.disabled = false;
                this.textContent = 'Build Timeline';
                alert('Error building timeline.');
            });
        });
    }
});