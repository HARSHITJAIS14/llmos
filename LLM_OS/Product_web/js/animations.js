document.addEventListener('DOMContentLoaded', () => {
    // Setup Intersection Observer for scroll animations
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.15 // Trigger when 15% of the element is visible
    };

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Add the 'visible' class to trigger CSS transition
                entry.target.classList.add('visible');
                // Unobserve after animating once
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Target elements with animation classes
    const animatedElements = document.querySelectorAll('.fade-in, .slide-up');
    
    animatedElements.forEach(el => {
        observer.observe(el);
    });

    // Optional: Add a subtle parallax effect to edge-images
    const edgeImages = document.querySelectorAll('.edge-image img');
    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        edgeImages.forEach(img => {
            const rect = img.getBoundingClientRect();
            // Only apply parallax if image is somewhat in viewport
            if(rect.top < window.innerHeight && rect.bottom > 0) {
                const yOffset = (rect.top - window.innerHeight / 2) * 0.1;
                img.style.transform = `translateY(${yOffset}px)`;
            }
        });
    });
});
