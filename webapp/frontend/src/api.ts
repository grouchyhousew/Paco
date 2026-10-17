export type User = { id: number; username?: string; first_name?: string };
export type Wallet = { balance: number; currency: string };

const apiBase = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

function initData(): string {
  return window.Telegram?.WebApp?.initData ?? '';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  const data = initData();
  if (data) headers.set('X-Telegram-Init-Data', data);
  const response = await fetch(`${apiBase}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<User>('/api/me'),
  wallet: () => request<Wallet>('/api/wallet'),
  games: () => request<{ games: Array<{ id: string; name: string; status: string }> }>('/api/games'),
  playFruit: (payload: { idempotency_key: string; client_seed: string; nonce: number; amount: number; rows?: number; cols?: number }) =>
    request<any>('/api/games/fruit-fall/play', { method: 'POST', body: JSON.stringify(payload) }),
  playCrash: (payload: { idempotency_key: string; client_seed: string; nonce: number; amount: number; auto_cashout: number }) =>
    request<any>('/api/games/crash/play', { method: 'POST', body: JSON.stringify(payload) }),
};
