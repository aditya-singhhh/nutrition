import * as SecureStore from 'expo-secure-store';

export const DEFAULT_BASE_URL = 'https://health-companion-api-p1f1.onrender.com';

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

// Called when the server says our login has expired, so the app can return to the login screen.
let onExpired: (() => void) | null = null;
export const setOnSessionExpired = (fn: (() => void) | null) => { onExpired = fn; };

export async function setBaseUrl(url: string): Promise<void> {
  baseUrl = url.trim().replace(/\/+$/, '') || DEFAULT_BASE_URL;
  await SecureStore.setItemAsync('hc_base', baseUrl);
}

export async function setToken(t: string | null): Promise<void> {
  token = t;
  if (t) await SecureStore.setItemAsync('hc_token', t);
  else await SecureStore.deleteItemAsync('hc_token');
}

export async function request<T = any>(method: string, path: string, body?: unknown | FormData, timeoutMs = 30000): Promise<T> {
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  const headers: Record<string, string> = isForm ? {} : { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    res = await fetch(`${baseUrl}/api/v1${path}`, {
      method,
      headers,
      signal: ctl.signal,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
    });
  } catch (e: any) {
    if (e?.name === 'AbortError') throw new ApiError(0, 'The server is taking too long. It may be waking up, so please try again in a minute.');
    throw new ApiError(0, `Cannot reach the server at ${baseUrl}. Check the server address and your connection.`);
  } finally {
    clearTimeout(timer);
  }
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (res.status === 401 && token && !path.startsWith('/auth/')) {
    await setToken(null);
    onExpired?.();
    throw new ApiError(401, 'Your session expired. Please log in again.');
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
  deleteAccount: () => request('DELETE', '/users/me'),
  updateProfile: (body: unknown) => request('PUT', '/users/me/profile', body),
  today: () => request('GET', '/nutrition/today'),
  scanBarcode: (barcode: string) => request('POST', '/scan/barcode', { barcode }),
  searchFoods: (q: string) => request<{ items: any[] }>('GET', `/foods?q=${encodeURIComponent(q)}`),
  alternatives: (r: { barcode?: string; slug?: string }) => request('GET', r.barcode ? `/products/${r.barcode}/alternatives` : `/foods/${r.slug}/alternatives`, undefined, 30000),
  analyzeFood: (food_slug: string) => request('POST', '/food/analyze', { food_slug, servings: 1 }),
  logMeal: (item: { food_slug?: string; barcode?: string }) =>
    request('POST', '/meals', { meal_type: 'snack', items: [{ ...item, servings: 1 }] }),
  logPhotoMeal: (prediction_id: number, items: { food_slug: string; grams: number; grams_min: number; grams_max: number }[]) =>
    request('POST', '/meals', { meal_type: 'snack', source: 'photo', items: items.map((i) => ({ ...i, prediction_id })) }),
  // One call for food OR label. Base64 JSON is more reliable than multipart on React Native.
  scanSmart: (image_base64: string, barcode?: string) => request('POST', '/scan/smart', { image_base64, barcode }, 90000),
  feedback: (prediction_id: number, prediction_correct: boolean, corrected_items: { food_slug: string; grams?: number }[]) =>
    request('POST', `/predictions/${prediction_id}/feedback`, { prediction_correct, corrected_items }),
  chat: (message: string, session_id?: number) => request('POST', '/chat', { message, session_id }),
};

