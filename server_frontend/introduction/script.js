// DOM 로드 완료 대기
document.addEventListener('DOMContentLoaded', function() {
    // Lucide 아이콘 초기화
    lucide.createIcons();
    
    // 컴포넌트 초기화
    initMobileMenu();
    initScrollAnimations();
    initSmoothScrolling();
    initStatCounters();
    initImageLazyLoading();
    initAccessibility();
});

/**
 * 모바일 메뉴 토글 기능
 */
function initMobileMenu() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (!mobileMenuButton || !mobileMenu) return;
    
    mobileMenuButton.addEventListener('click', function() {
        const isHidden = mobileMenu.classList.contains('hidden');
        
        if (isHidden) {
            mobileMenu.classList.remove('hidden');
            mobileMenu.classList.add('show');
            mobileMenuButton.setAttribute('aria-expanded', 'true');
        } else {
            mobileMenu.classList.add('hidden');
            mobileMenu.classList.remove('show');
            mobileMenuButton.setAttribute('aria-expanded', 'false');
        }
    });
    
    // 메뉴 링크 클릭시 메뉴 닫기
    const menuLinks = mobileMenu.querySelectorAll('a');
    menuLinks.forEach(link => {
        link.addEventListener('click', () => {
            mobileMenu.classList.add('hidden');
            mobileMenu.classList.remove('show');
            mobileMenuButton.setAttribute('aria-expanded', 'false');
        });
    });
}

/**
 * 스크롤 애니메이션 초기화
 */
function initScrollAnimations() {
    const sections = document.querySelectorAll('.section-fade-in');
    
    // Intersection Observer 지원 확인
    if (!window.IntersectionObserver) {
        // 구형 브라우저에서는 모든 섹션을 바로 표시
        sections.forEach(section => {
            section.classList.add('visible');
        });
        return;
    }
    
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                // 애니메이션 완료 후 관찰 중단 (성능 향상)
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    sections.forEach(section => {
        observer.observe(section);
    });
}

/**
 * 부드러운 스크롤링
 */
function initSmoothScrolling() {
    const navLinks = document.querySelectorAll('a[href^="#"]');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            const targetElement = document.querySelector(href);
            if (!targetElement) return;
            
            e.preventDefault();
            
            const headerHeight = document.querySelector('header').offsetHeight;
            const targetPosition = targetElement.offsetTop - headerHeight - 20;
            
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        });
    });
}

/**
 * 통계 숫자 카운트 애니메이션
 */
function initStatCounters() {
    const statNumbers = document.querySelectorAll('.stat-number');
    
    function animateValue(element, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const value = Math.floor(progress * (end - start) + start);
            element.textContent = value.toLocaleString();
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                const finalValue = parseInt(element.textContent.replace(/,/g, ''));
                animateValue(element, 0, finalValue, 2000);
                observer.unobserve(element);
            }
        });
    });
    
    statNumbers.forEach(stat => {
        observer.observe(stat);
    });
}

/**
 * 이미지 지연 로딩
 */
function initImageLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('loading');
                    img.classList.add('loaded');
                    imageObserver.unobserve(img);
                }
            });
        });
        
        images.forEach(img => {
            img.classList.add('loading');
            imageObserver.observe(img);
        });
    } else {
        // 폴백: 모든 이미지 즉시 로드
        images.forEach(img => {
            img.src = img.dataset.src;
        });
    }
}

/**
 * 접근성 개선
 */
function initAccessibility() {
    // 키보드 네비게이션 개선
    const focusableElements = document.querySelectorAll(
        'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    
    // ESC 키로 모바일 메뉴 닫기
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const mobileMenu = document.getElementById('mobile-menu');
            const mobileMenuButton = document.getElementById('mobile-menu-button');
            
            if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
                mobileMenu.classList.add('hidden');
                mobileMenu.classList.remove('show');
                mobileMenuButton.setAttribute('aria-expanded', 'false');
                mobileMenuButton.focus();
            }
        }
    });
    
    // 포커스 트래핑 (모바일 메뉴에서)
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenu) {
        const focusableInMenu = mobileMenu.querySelectorAll(
            'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        if (focusableInMenu.length > 0) {
            const firstFocusable = focusableInMenu[0];
            const lastFocusable = focusableInMenu[focusableInMenu.length - 1];
            
            mobileMenu.addEventListener('keydown', function(e) {
                if (e.key === 'Tab') {
                    if (e.shiftKey) {
                        if (document.activeElement === firstFocusable) {
                            e.preventDefault();
                            lastFocusable.focus();
                        }
                    } else {
                        if (document.activeElement === lastFocusable) {
                            e.preventDefault();
                            firstFocusable.focus();
                        }
                    }
                }
            });
        }
    }
}

/**
 * 성능 모니터링 및 분석
 */
function initPerformanceMonitoring() {
    // Performance API 지원 확인
    if ('performance' in window) {
        window.addEventListener('load', () => {
            // 페이지 로드 시간 측정
            const loadTime = performance.timing.loadEventEnd - performance.timing.navigationStart;
            console.log('Page load time:', loadTime + 'ms');
            
            // 리소스 로딩 시간 분석
            const resources = performance.getEntriesByType('resource');
            resources.forEach(resource => {
                if (resource.duration > 1000) {
                    console.warn('Slow resource:', resource.name, resource.duration + 'ms');
                }
            });
        });
    }
}

// 페이지 성능 모니터링 초기화
initPerformanceMonitoring();

// 전역 에러 핸들링
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    // 프로덕션에서는 에러 리포팅 서비스로 전송
});

// 서비스 워커 등록 (PWA 지원 준비)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}
