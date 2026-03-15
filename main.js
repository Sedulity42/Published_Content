// Matthew D. Lestourgeon — Portfolio
// Navigation and scroll animations

(function () {
    'use strict';

    // Mobile navigation toggle
    var toggle = document.querySelector('.nav-toggle');
    var navLinks = document.querySelector('.nav-links');

    if (toggle && navLinks) {
        toggle.addEventListener('click', function () {
            var expanded = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', String(!expanded));
            navLinks.classList.toggle('open');
        });

        // Close mobile nav when a link is clicked
        navLinks.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                navLinks.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
            });
        });
    }

    // Header scroll state
    var header = document.getElementById('site-header');
    if (header) {
        window.addEventListener('scroll', function () {
            if (window.scrollY > 16) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        }, { passive: true });
    }

    // Fade-in on scroll for elements with [data-animate]
    var animatedElements = document.querySelectorAll('[data-animate]');

    if (animatedElements.length > 0 && 'IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -40px 0px'
        });

        animatedElements.forEach(function (el) {
            observer.observe(el);
        });
    } else {
        // Fallback: show everything immediately
        animatedElements.forEach(function (el) {
            el.classList.add('visible');
        });
    }

    // Hero loader — cycling phrases with loading bar
    var loaderLabel = document.querySelector('.hero-loader-label');
    var loaderFill = document.querySelector('.hero-loader-fill');

    if (loaderLabel && loaderFill) {
        var phrases = [
            'Building tools',
            'Building teams',
            'Hunting threats',
            'Deploying countermeasures',
            'Updating threat intel',
            'Patching vulnerabilities',
            'Warming up the SOC',
            'Correlating log sources',
            'Enumerating attack surface',
            'Pondering the orb',
            'SELECT * FROM skills',
            'Defragmenting thoughts',
            'Consulting the RFC',
            'Loading caffeine.dll',
            'Reverse engineering Monday'
        ];

        // Fisher-Yates shuffle
        for (var i = phrases.length - 1; i > 0; i--) {
            var j = Math.floor(Math.random() * (i + 1));
            var temp = phrases[i];
            phrases[i] = phrases[j];
            phrases[j] = temp;
        }

        var currentIndex = 0;
        var FILL_DURATION = 2000;
        var PAUSE_AFTER = 600;
        var STEPS = 40;
        var stepTime = FILL_DURATION / STEPS;

        function runPhrase() {
            var step = 0;
            loaderLabel.textContent = phrases[currentIndex] + '...';
            loaderFill.classList.remove('complete');
            loaderFill.style.width = '0%';

            var interval = setInterval(function () {
                step++;
                loaderFill.style.width = ((step / STEPS) * 100) + '%';
                if (step >= STEPS) {
                    clearInterval(interval);
                    loaderFill.classList.add('complete');
                    setTimeout(function () {
                        currentIndex = (currentIndex + 1) % phrases.length;
                        runPhrase();
                    }, PAUSE_AFTER);
                }
            }, stepTime);
        }

        runPhrase();
    }
})();
