/**
 * Dynamic Environment Configuration for Vulcan Frontend
 * Automatically determines API and WebSocket URLs based on client origin or env vars.
 */

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    // If explicitly configured with an external URL, respect it
    if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.includes('localhost')) {
      return process.env.NEXT_PUBLIC_API_URL;
    }
    // Dynamically match server host: if accessed via IP or domain on :3000, connect to backend on :8000
    const proto = window.location.protocol;
    const hostname = window.location.hostname;
    return `${proto}//${hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

export function getWsBaseUrl(): string {
  const httpUrl = getApiBaseUrl();
  return httpUrl.replace(/^http/, 'ws');
}
