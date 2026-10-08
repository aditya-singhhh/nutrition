import * as SecureStore from 'expo-secure-store';

export const DEFAULT_BASE_URL = 'http://10.0.2.2:8000'; // Android emulator -> host machine

let baseUrl = DEFAULT_BASE_URL;
let token: string | null = null;

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

export async function loadSession(): Promise<boolean> {
  try {
    baseUrl = (await SecureStore.getItemAsync('hc_base')) || DEFAULT_BASE_URL;
    token = await SecureStore.getItemAsync('hc_token');
  } catch {
    token = null;
  }
  return token !== null;
}

export const getBaseUrl = () => baseUrl;

export async function setBaseUrl(url: string): Promise<void> {
  baseUrl = url.trim().replace(/\/+$/, '') || DEFAULT_BASE_URL;
  await SecureStore.setItemAsync('hc_base', baseUrl);
}

export async function setToken(t: string | null): Promise<void> {
  token = t;
  if (t) await SecureStore.setItemAsync('hc_token', t);
  else await SecureStore.deleteItemAsync('hc_token');
}

export async function request<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${baseUrl}/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Cannot reach the server at ${baseUrl}. Check the server address and your connection.`);
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    let detail: unknown = data?.detail ?? `Request failed (${res.status})`;
    if (Array.isArray(detail)) detail = detail.map((d: any) => d.msg).join('; ');
    throw new ApiError(res.status, detail);
  }
  return data as T;
}

export const api = {
  register: (email: string, password: string) =>
    request<{ access_token: string }>('POST', '/auth/register', {
      email, password, consent_health_data: true, accepted_terms: true,
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>('POST', '/auth/login', { email, password }),
  me: () => request('GET', '/users/me'),
  updateProfile: (body: unknown) => request('PUT', '/users/me/profile', body),
  today: () => request('GET', '/nutrition/today'),
  scanBarcode: (barcode: string) => request('POST', '/scan/barcode', { barcode }),
  searchFoods: (q: string) => request<{ items: any[] }>('GET', `/foods?q=${encodeURIComponent(q)}`),
  analyzeFood: (food_slug: string) => request('POST', '/food/analyze', { food_slug, servings: 1 }),
  logMeal: (item: { food_slug?: string; barcode?: string }) =>
    request('POST', '/meals', { meal_type: 'snack', items: [{ ...item, servings: 1 }] }),
  chat: (message: string, session_id?: number) => request('POST', '/chat', { message, session_id }),
};
