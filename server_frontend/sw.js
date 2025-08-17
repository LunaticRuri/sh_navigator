// 서비스 워커 v1.0.0
const CACHE_NAME = 'sh-navigator-v1';
const urlsToCache = [
    '/',
    '/introduction/',
    '/introduction/index.html',
    '/introduction/styles.css',
    '/introduction/script.js',
    '/favicon.ico',
    'https://cdn.tailwindcss.com',
    'https://unpkg.com/lucide@latest',
    'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap'
];

// 설치 이벤트
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Opened cache');
                return cache.addAll(urlsToCache);
            })
    );
});

// Fetch 이벤트
self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // 캐시에 있으면 캐시된 버전을 반환
                if (response) {
                    return response;
                }

                // 캐시에 없으면 네트워크에서 가져옴
                return fetch(event.request).then(response => {
                    // 유효한 응답인지 확인
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }

                    // 응답을 복제하여 캐시에 저장
                    const responseToCache = response.clone();
                    caches.open(CACHE_NAME)
                        .then(cache => {
                            cache.put(event.request, responseToCache);
                        });

                    return response;
                });
            })
            .catch(() => {
                // 오프라인 상태일 때 기본 페이지 반환
                return caches.match('/introduction/index.html');
            })
    );
});

// 업데이트 이벤트
self.addEventListener('activate', event => {
    const cacheWhitelist = [CACHE_NAME];

    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheWhitelist.indexOf(cacheName) === -1) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});
