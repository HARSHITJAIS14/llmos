document.addEventListener('DOMContentLoaded', () => {
    const wrapper = document.querySelector('.scroll-sequence-wrapper');
    const steps = document.querySelectorAll('.sequence-step');
    
    if (!wrapper || steps.length === 0) return;

    window.addEventListener('scroll', () => {
        const wrapperRect = wrapper.getBoundingClientRect();
        
        // Calculate how far we've scrolled into the wrapper
        // wrapperRect.top is 0 when the top of the wrapper hits the top of the viewport
        const scrollDistance = -wrapperRect.top;
        const scrollableHeight = wrapper.offsetHeight - window.innerHeight;
        
        // If we haven't reached the wrapper yet, ensure step 1 is active
        if (scrollDistance < 0) {
            steps.forEach((step, index) => {
                if (index === 0) {
                    step.classList.add('active');
                    step.classList.remove('past');
                } else {
                    step.classList.remove('active', 'past');
                }
            });
            return;
        }

        // Calculate progress from 0 to 1
        let progress = scrollDistance / scrollableHeight;
        
        // Clamp progress between 0 and 1
        progress = Math.max(0, Math.min(1, progress));
        
        // Determine which step should be active
        const totalSteps = steps.length;
        let activeIndex = Math.floor(progress * totalSteps);
        
        // Fix boundary issue at exactly 1.0
        if (activeIndex >= totalSteps) {
            activeIndex = totalSteps - 1;
        }

        // Apply classes
        steps.forEach((step, index) => {
            if (index < activeIndex) {
                step.classList.remove('active');
                step.classList.add('past');
            } else if (index === activeIndex) {
                step.classList.add('active');
                step.classList.remove('past');
            } else {
                step.classList.remove('active');
                step.classList.remove('past');
            }
        });
    });
});
