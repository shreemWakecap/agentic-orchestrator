/**
 * Animations Module
 *
 * Reusable micro-interactions and animation utilities for the SDLC Orchestrator.
 * This module provides:
 * - Ripple effect for buttons and clickable elements
 * - Smooth number counter animations (count up/down)
 * - Skeleton loading state utilities
 * - Scroll-triggered reveal animations using Intersection Observer
 *
 * Usage:
 * Include this file after common.js. Functions are exposed via the global
 * OrchestratorAnimations object.
 */

const OrchestratorAnimations = (function() {
    'use strict';

    // =========================================================================
    // Configuration
    // =========================================================================

    const config = {
        ripple: {
            duration: 600,
            color: 'rgba(255, 255, 255, 0.4)',
            darkColor: 'rgba(0, 0, 0, 0.1)'
        },
        countUp: {
            duration: 1000,
            easing: 'easeOutQuart'
        },
        skeleton: {
            baseClass: 'skeleton-loading',
            shimmerClass: 'skeleton-shimmer'
        },
        scrollReveal: {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        }
    };

    // =========================================================================
    // Easing Functions
    // =========================================================================

    const easings = {
        linear: function(t) { return t; },
        easeInQuad: function(t) { return t * t; },
        easeOutQuad: function(t) { return t * (2 - t); },
        easeInOutQuad: function(t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; },
        easeOutQuart: function(t) { return 1 - Math.pow(1 - t, 4); },
        easeOutCubic: function(t) { return 1 - Math.pow(1 - t, 3); },
        easeOutExpo: function(t) { return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); }
    };

    // =========================================================================
    // Ripple Effect
    // =========================================================================

    /**
     * Create a ripple effect on an element
     * @param {MouseEvent|TouchEvent} event - The triggering event
     * @param {Object} [options] - Configuration options
     * @param {string} [options.color] - Ripple color (CSS color value)
     * @param {number} [options.duration] - Animation duration in ms
     * @param {boolean} [options.centered] - Center the ripple instead of using click position
     */
    function ripple(event, options) {
        options = options || {};

        var target = event.currentTarget || event.target;
        if (!target) return;

        // Ensure element has relative/absolute positioning for ripple containment
        var computedStyle = window.getComputedStyle(target);
        if (computedStyle.position === 'static') {
            target.style.position = 'relative';
        }

        // Ensure overflow hidden for ripple containment
        target.style.overflow = 'hidden';

        var rect = target.getBoundingClientRect();
        var rippleEl = document.createElement('span');

        // Determine ripple size (largest dimension ensures full coverage)
        var size = Math.max(rect.width, rect.height) * 2;

        // Determine position
        var x, y;
        if (options.centered) {
            x = rect.width / 2;
            y = rect.height / 2;
        } else {
            var clientX = event.clientX || (event.touches && event.touches[0] ? event.touches[0].clientX : rect.left + rect.width / 2);
            var clientY = event.clientY || (event.touches && event.touches[0] ? event.touches[0].clientY : rect.top + rect.height / 2);
            x = clientX - rect.left;
            y = clientY - rect.top;
        }

        // Determine color based on element background or options
        var rippleColor = options.color || config.ripple.color;
        if (!options.color) {
            var bgColor = computedStyle.backgroundColor;
            if (bgColor && (bgColor.indexOf('255, 255, 255') !== -1 || bgColor === 'transparent' || bgColor === 'rgba(0, 0, 0, 0)')) {
                rippleColor = config.ripple.darkColor;
            }
        }

        var duration = options.duration || config.ripple.duration;

        // Style the ripple element
        rippleEl.className = 'ripple-effect';
        rippleEl.style.cssText = [
            'position: absolute',
            'border-radius: 50%',
            'transform: scale(0)',
            'pointer-events: none',
            'width: ' + size + 'px',
            'height: ' + size + 'px',
            'left: ' + (x - size / 2) + 'px',
            'top: ' + (y - size / 2) + 'px',
            'background: ' + rippleColor,
            'animation: ripple-animation ' + duration + 'ms ease-out forwards'
        ].join(';');

        target.appendChild(rippleEl);

        // Remove ripple after animation completes
        setTimeout(function() {
            if (rippleEl.parentNode) {
                rippleEl.parentNode.removeChild(rippleEl);
            }
        }, duration);
    }

    /**
     * Initialize ripple effect on elements matching a selector
     * @param {string} selector - CSS selector for elements to add ripple to
     * @param {Object} [options] - Ripple options passed to each ripple call
     * @returns {Function} Cleanup function to remove event listeners
     */
    function initRipple(selector, options) {
        var elements = document.querySelectorAll(selector);
        var handlers = [];

        elements.forEach(function(element) {
            var handler = function(event) {
                ripple(event, options);
            };
            element.addEventListener('mousedown', handler);
            element.addEventListener('touchstart', handler, { passive: true });
            handlers.push({ element: element, handler: handler });
        });

        // Inject keyframes if not already present
        injectRippleStyles();

        return function cleanup() {
            handlers.forEach(function(item) {
                item.element.removeEventListener('mousedown', item.handler);
                item.element.removeEventListener('touchstart', item.handler);
            });
        };
    }

    /**
     * Inject ripple animation keyframes into document
     */
    function injectRippleStyles() {
        if (document.getElementById('ripple-styles')) return;

        var style = document.createElement('style');
        style.id = 'ripple-styles';
        style.textContent = [
            '@keyframes ripple-animation {',
            '  to {',
            '    transform: scale(1);',
            '    opacity: 0;',
            '  }',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    // =========================================================================
    // Count Up Animation
    // =========================================================================

    /**
     * Animate a number counting up (or down)
     * @param {HTMLElement|string} elementOrId - Element or element ID to animate
     * @param {number} endValue - Target number to count to
     * @param {Object} [options] - Configuration options
     * @param {number} [options.startValue=0] - Starting number
     * @param {number} [options.duration=1000] - Animation duration in ms
     * @param {string} [options.easing='easeOutQuart'] - Easing function name
     * @param {string} [options.prefix=''] - Text to prepend to number
     * @param {string} [options.suffix=''] - Text to append to number
     * @param {number} [options.decimals=0] - Number of decimal places
     * @param {string} [options.separator=','] - Thousands separator
     * @param {Function} [options.onComplete] - Callback when animation completes
     * @returns {Object} Controller with stop() method
     */
    function countUp(elementOrId, endValue, options) {
        options = options || {};

        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) {
            console.warn('countUp: Element not found');
            return { stop: function() {} };
        }

        var startValue = options.startValue !== undefined ? options.startValue : 0;
        var duration = options.duration || config.countUp.duration;
        var easingName = options.easing || config.countUp.easing;
        var easing = easings[easingName] || easings.easeOutQuart;
        var prefix = options.prefix || '';
        var suffix = options.suffix || '';
        var decimals = options.decimals || 0;
        var separator = options.separator !== undefined ? options.separator : ',';

        var startTime = null;
        var animationId = null;
        var stopped = false;

        function formatNumber(num) {
            var fixed = num.toFixed(decimals);
            if (separator) {
                var parts = fixed.split('.');
                parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, separator);
                return parts.join('.');
            }
            return fixed;
        }

        function animate(currentTime) {
            if (stopped) return;

            if (!startTime) startTime = currentTime;
            var elapsed = currentTime - startTime;
            var progress = Math.min(elapsed / duration, 1);
            var easedProgress = easing(progress);

            var currentValue = startValue + (endValue - startValue) * easedProgress;
            element.textContent = prefix + formatNumber(currentValue) + suffix;

            if (progress < 1) {
                animationId = requestAnimationFrame(animate);
            } else {
                element.textContent = prefix + formatNumber(endValue) + suffix;
                if (options.onComplete) {
                    options.onComplete();
                }
            }
        }

        animationId = requestAnimationFrame(animate);

        return {
            stop: function() {
                stopped = true;
                if (animationId) {
                    cancelAnimationFrame(animationId);
                }
            }
        };
    }

    /**
     * Animate multiple counters simultaneously
     * @param {Array<Object>} counters - Array of counter configurations
     * @param {string|HTMLElement} counters[].element - Element or ID
     * @param {number} counters[].value - Target value
     * @param {Object} [counters[].options] - Options for this counter
     * @returns {Object} Controller with stopAll() method
     */
    function countUpMultiple(counters) {
        var controllers = counters.map(function(counter) {
            return countUp(counter.element, counter.value, counter.options);
        });

        return {
            stopAll: function() {
                controllers.forEach(function(controller) {
                    controller.stop();
                });
            }
        };
    }

    // =========================================================================
    // Skeleton Loading States
    // =========================================================================

    /**
     * Show skeleton loading state on an element
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @param {Object} [options] - Configuration options
     * @param {string} [options.type='text'] - Type: 'text', 'circle', 'rect', 'card'
     * @param {number} [options.lines=1] - Number of skeleton lines (for text type)
     * @param {string} [options.width] - Custom width
     * @param {string} [options.height] - Custom height
     */
    function showSkeleton(elementOrId, options) {
        options = options || {};

        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) return;

        // Store original content
        element.dataset.skeletonOriginal = element.innerHTML;
        element.dataset.skeletonActive = 'true';

        var type = options.type || 'text';
        var lines = options.lines || 1;
        var skeletonHtml = '';

        // Inject skeleton styles if not present
        injectSkeletonStyles();

        switch (type) {
            case 'circle':
                var size = options.width || options.height || '40px';
                skeletonHtml = '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:' + size + ';height:' + size + ';border-radius:50%;"></div>';
                break;

            case 'rect':
                var width = options.width || '100%';
                var height = options.height || '100px';
                skeletonHtml = '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:' + width + ';height:' + height + ';border-radius:4px;"></div>';
                break;

            case 'card':
                skeletonHtml = [
                    '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:100%;height:120px;border-radius:8px;margin-bottom:12px;"></div>',
                    '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:80%;height:16px;border-radius:4px;margin-bottom:8px;"></div>',
                    '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:60%;height:16px;border-radius:4px;"></div>'
                ].join('');
                break;

            case 'text':
            default:
                var lineHtml = [];
                for (var i = 0; i < lines; i++) {
                    var lineWidth = i === lines - 1 && lines > 1 ? '60%' : (options.width || '100%');
                    var lineHeight = options.height || '16px';
                    lineHtml.push('<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:' + lineWidth + ';height:' + lineHeight + ';border-radius:4px;margin-bottom:8px;"></div>');
                }
                skeletonHtml = lineHtml.join('');
                break;
        }

        element.innerHTML = skeletonHtml;
    }

    /**
     * Hide skeleton loading state and restore original content
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @param {string} [newContent] - New content to set (if not provided, restores original)
     */
    function hideSkeleton(elementOrId, newContent) {
        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) return;

        if (newContent !== undefined) {
            element.innerHTML = newContent;
        } else if (element.dataset.skeletonOriginal !== undefined) {
            element.innerHTML = element.dataset.skeletonOriginal;
        }

        delete element.dataset.skeletonOriginal;
        delete element.dataset.skeletonActive;
    }

    /**
     * Check if an element is showing skeleton
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @returns {boolean} Whether skeleton is active
     */
    function isSkeletonActive(elementOrId) {
        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        return element && element.dataset.skeletonActive === 'true';
    }

    /**
     * Create skeleton placeholder HTML
     * @param {Object} options - Skeleton options (same as showSkeleton)
     * @returns {string} HTML string for skeleton
     */
    function createSkeletonHtml(options) {
        options = options || {};
        var type = options.type || 'text';
        var lines = options.lines || 1;

        injectSkeletonStyles();

        switch (type) {
            case 'circle':
                var size = options.width || options.height || '40px';
                return '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:' + size + ';height:' + size + ';border-radius:50%;"></div>';

            case 'rect':
                var width = options.width || '100%';
                var height = options.height || '100px';
                return '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:' + width + ';height:' + height + ';border-radius:4px;"></div>';

            case 'card':
                return [
                    '<div class="skeleton-card">',
                    '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:100%;height:120px;border-radius:8px;margin-bottom:12px;"></div>',
                    '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:80%;height:16px;border-radius:4px;margin-bottom:8px;"></div>',
                    '<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:60%;height:16px;border-radius:4px;"></div>',
                    '</div>'
                ].join('');

            case 'text':
            default:
                var lineHtml = [];
                for (var i = 0; i < lines; i++) {
                    var lineWidth = i === lines - 1 && lines > 1 ? '60%' : (options.width || '100%');
                    var lineHeight = options.height || '16px';
                    lineHtml.push('<div class="' + config.skeleton.baseClass + ' ' + config.skeleton.shimmerClass + '" style="width:' + lineWidth + ';height:' + lineHeight + ';border-radius:4px;margin-bottom:8px;"></div>');
                }
                return lineHtml.join('');
        }
    }

    /**
     * Inject skeleton animation styles into document
     */
    function injectSkeletonStyles() {
        if (document.getElementById('skeleton-styles')) return;

        var style = document.createElement('style');
        style.id = 'skeleton-styles';
        style.textContent = [
            '.skeleton-loading {',
            '  background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);',
            '  background-size: 200% 100%;',
            '  display: block;',
            '}',
            '.dark .skeleton-loading {',
            '  background: linear-gradient(90deg, #374151 25%, #4b5563 50%, #374151 75%);',
            '  background-size: 200% 100%;',
            '}',
            '.skeleton-shimmer {',
            '  animation: skeleton-shimmer 1.5s infinite;',
            '}',
            '@keyframes skeleton-shimmer {',
            '  0% { background-position: 200% 0; }',
            '  100% { background-position: -200% 0; }',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    // =========================================================================
    // Scroll Reveal Animations
    // =========================================================================

    var scrollRevealObserver = null;
    var revealedElements = new WeakSet();

    /**
     * Initialize scroll reveal for elements
     * @param {string} selector - CSS selector for elements to reveal
     * @param {Object} [options] - Configuration options
     * @param {number} [options.threshold=0.1] - Visibility threshold (0-1)
     * @param {string} [options.rootMargin='0px 0px -50px 0px'] - Root margin for observer
     * @param {string} [options.animation='fadeInUp'] - Animation type
     * @param {number} [options.duration=500] - Animation duration in ms
     * @param {number} [options.delay=0] - Base delay before animation
     * @param {number} [options.stagger=100] - Stagger delay between elements
     * @param {boolean} [options.once=true] - Only animate once
     * @returns {Function} Cleanup function
     */
    function initScrollReveal(selector, options) {
        options = options || {};

        var threshold = options.threshold !== undefined ? options.threshold : config.scrollReveal.threshold;
        var rootMargin = options.rootMargin || config.scrollReveal.rootMargin;
        var animation = options.animation || 'fadeInUp';
        var duration = options.duration || 500;
        var baseDelay = options.delay || 0;
        var stagger = options.stagger || 100;
        var once = options.once !== false;

        // Inject reveal styles
        injectRevealStyles();

        var elements = document.querySelectorAll(selector);
        var elementIndex = 0;

        // Prepare elements with initial hidden state
        elements.forEach(function(element, index) {
            element.style.opacity = '0';
            element.style.transition = 'none';
            element.dataset.revealAnimation = animation;
            element.dataset.revealDelay = String(baseDelay + (index * stagger));
            element.dataset.revealDuration = String(duration);

            // Apply initial transform based on animation
            applyInitialState(element, animation);
        });

        // Create observer
        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    var element = entry.target;

                    if (once && revealedElements.has(element)) {
                        return;
                    }

                    var delay = parseInt(element.dataset.revealDelay || '0', 10);
                    var dur = parseInt(element.dataset.revealDuration || '500', 10);
                    var anim = element.dataset.revealAnimation || 'fadeInUp';

                    setTimeout(function() {
                        revealElement(element, anim, dur);
                        revealedElements.add(element);

                        if (once) {
                            observer.unobserve(element);
                        }
                    }, delay);
                } else if (!once) {
                    // Reset element when out of view (if not once-only)
                    var element = entry.target;
                    var anim = element.dataset.revealAnimation || 'fadeInUp';
                    applyInitialState(element, anim);
                    element.style.opacity = '0';
                }
            });
        }, {
            threshold: threshold,
            rootMargin: rootMargin
        });

        // Observe elements
        elements.forEach(function(element) {
            observer.observe(element);
        });

        return function cleanup() {
            elements.forEach(function(element) {
                observer.unobserve(element);
            });
            observer.disconnect();
        };
    }

    /**
     * Apply initial hidden state based on animation type
     * @param {HTMLElement} element - Element to prepare
     * @param {string} animation - Animation type
     */
    function applyInitialState(element, animation) {
        switch (animation) {
            case 'fadeInUp':
                element.style.transform = 'translateY(30px)';
                break;
            case 'fadeInDown':
                element.style.transform = 'translateY(-30px)';
                break;
            case 'fadeInLeft':
                element.style.transform = 'translateX(-30px)';
                break;
            case 'fadeInRight':
                element.style.transform = 'translateX(30px)';
                break;
            case 'scaleIn':
                element.style.transform = 'scale(0.9)';
                break;
            case 'fadeIn':
            default:
                element.style.transform = 'none';
                break;
        }
    }

    /**
     * Reveal an element with animation
     * @param {HTMLElement} element - Element to reveal
     * @param {string} animation - Animation type
     * @param {number} duration - Animation duration in ms
     */
    function revealElement(element, animation, duration) {
        element.style.transition = 'opacity ' + duration + 'ms ease-out, transform ' + duration + 'ms ease-out';
        element.style.opacity = '1';
        element.style.transform = 'translateY(0) translateX(0) scale(1)';
    }

    /**
     * Manually reveal an element
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @param {Object} [options] - Animation options
     */
    function reveal(elementOrId, options) {
        options = options || {};

        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) return;

        var animation = options.animation || 'fadeInUp';
        var duration = options.duration || 500;
        var delay = options.delay || 0;

        element.style.opacity = '0';
        applyInitialState(element, animation);

        setTimeout(function() {
            revealElement(element, animation, duration);
        }, delay);
    }

    /**
     * Inject reveal animation styles
     */
    function injectRevealStyles() {
        if (document.getElementById('reveal-styles')) return;

        var style = document.createElement('style');
        style.id = 'reveal-styles';
        style.textContent = [
            '.reveal-hidden {',
            '  opacity: 0;',
            '  visibility: hidden;',
            '}',
            '.reveal-visible {',
            '  opacity: 1;',
            '  visibility: visible;',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    // =========================================================================
    // Utility Animations
    // =========================================================================

    /**
     * Shake an element (useful for error feedback)
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @param {Object} [options] - Configuration options
     * @param {number} [options.duration=500] - Animation duration in ms
     * @param {number} [options.intensity=10] - Shake intensity in pixels
     */
    function shake(elementOrId, options) {
        options = options || {};

        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) return;

        var duration = options.duration || 500;
        var intensity = options.intensity || 10;

        injectShakeStyles(intensity);

        element.style.animation = 'shake-animation ' + duration + 'ms ease-in-out';

        setTimeout(function() {
            element.style.animation = '';
        }, duration);
    }

    /**
     * Inject shake animation styles
     * @param {number} intensity - Shake intensity in pixels
     */
    function injectShakeStyles(intensity) {
        var styleId = 'shake-styles-' + intensity;
        if (document.getElementById(styleId)) return;

        var style = document.createElement('style');
        style.id = styleId;
        style.textContent = [
            '@keyframes shake-animation {',
            '  0%, 100% { transform: translateX(0); }',
            '  10%, 30%, 50%, 70%, 90% { transform: translateX(-' + intensity + 'px); }',
            '  20%, 40%, 60%, 80% { transform: translateX(' + intensity + 'px); }',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    /**
     * Pulse an element (useful for drawing attention)
     * @param {HTMLElement|string} elementOrId - Element or element ID
     * @param {Object} [options] - Configuration options
     * @param {number} [options.duration=1000] - Animation duration in ms
     * @param {number} [options.scale=1.05] - Pulse scale factor
     * @param {number} [options.iterations=2] - Number of pulse iterations
     */
    function pulse(elementOrId, options) {
        options = options || {};

        var element = typeof elementOrId === 'string'
            ? document.getElementById(elementOrId)
            : elementOrId;

        if (!element) return;

        var duration = options.duration || 1000;
        var scale = options.scale || 1.05;
        var iterations = options.iterations || 2;

        injectPulseStyles(scale);

        element.style.animation = 'pulse-animation ' + (duration / iterations) + 'ms ease-in-out ' + iterations;

        setTimeout(function() {
            element.style.animation = '';
        }, duration);
    }

    /**
     * Inject pulse animation styles
     * @param {number} scale - Pulse scale factor
     */
    function injectPulseStyles(scale) {
        var styleId = 'pulse-styles-' + String(scale).replace('.', '-');
        if (document.getElementById(styleId)) return;

        var style = document.createElement('style');
        style.id = styleId;
        style.textContent = [
            '@keyframes pulse-animation {',
            '  0%, 100% { transform: scale(1); }',
            '  50% { transform: scale(' + scale + '); }',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

    // =========================================================================
    // Public API
    // =========================================================================

    return {
        // Configuration
        config: config,
        easings: easings,

        // Ripple Effect
        ripple: ripple,
        initRipple: initRipple,

        // Count Up Animation
        countUp: countUp,
        countUpMultiple: countUpMultiple,

        // Skeleton Loading
        showSkeleton: showSkeleton,
        hideSkeleton: hideSkeleton,
        isSkeletonActive: isSkeletonActive,
        createSkeletonHtml: createSkeletonHtml,

        // Scroll Reveal
        initScrollReveal: initScrollReveal,
        reveal: reveal,

        // Utility Animations
        shake: shake,
        pulse: pulse
    };
})();

// Expose globally for use by other modules
window.OrchestratorAnimations = OrchestratorAnimations;

// Export for testing (CommonJS/ES module environments)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OrchestratorAnimations;
}
