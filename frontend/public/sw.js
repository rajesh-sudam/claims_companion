// This is a placeholder service worker file.
// It can be used to add Progressive Web App features in the future.

self.addEventListener('fetch', (event) => {
  // For now, just pass through all network requests.
  event.respondWith(fetch(event.request));
});
