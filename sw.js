// アプリ本体はネット優先・圏外（地下鉄など）ではキャッシュ。
// 音声（a/*.bin）はページ側が Cache Storage に保存するので、ここでは触らない。
const CACHE = 'oet-lc-shell-v1';
const FILES = ['./', './index.html', './manifest.json', './icon.png', './data.enc.json'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES))); self.skipWaiting(); });
self.addEventListener('activate', e => {
  // 古いアプリ本体のキャッシュだけ消す（保存した音声 oet-lc-audio-* は残す）
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith('oet-lc-shell-') && k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || url.pathname.includes('/a/')) return;
  e.respondWith(fetch(e.request).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true }).then(r => r || caches.match('./index.html'))));
});
