import { readAuthToken } from "./auth-token";

const env = import.meta.env;

const trimTrailingSlash = (input: string) => input.replace(/\/$/, "");

const smartFallback =
  typeof location !== "undefined" && /\.danielfranca\.pt$/i.test(location.hostname)
    ? "https://api.danielfranca.pt"
    : "http://localhost:8000";

const CRM_RAW_BASE =
  env?.VITE_CRM_BASE_URL || env?.VITE_API_BASE_URL || env?.VITE_API_URL || smartFallback;
const CORE_RAW_BASE = env?.VITE_CORE_BASE_URL || "http://localhost:8001";

const API_BASE = `${trimTrailingSlash(CRM_RAW_BASE)}/api`;
const CRM_API_BASE = API_BASE;
const CORE_BASE = trimTrailingSlash(CORE_RAW_BASE);
const CORE_AUTH_BASE = `${CORE_BASE}/auth`;

export class ApiError extends Error {
  status?: number;
  data?: unknown;

  constructor(message: string, options?: { status?: number; data?: unknown }) {
    super(message);
    this.name = "ApiError";
    this.status = options?.status;
    this.data = options?.data;
  }
}

function getStoredToken(): string | null {
  const stored = readAuthToken();
  if (stored) return stored;

  const envToken = env?.VITE_AUTH_TOKEN;
  return envToken ?? null;
}

function buildHeaders(headers?: HeadersInit, body?: BodyInit | null) {
  const merged = new Headers(headers);
  const token = getStoredToken();

  if (token && !merged.has("Authorization")) {
    merged.set("Authorization", `Bearer ${token}`);
  }
  const hasContentType = merged.has("Content-Type");
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  if (!hasContentType && !isFormData) {
    merged.set("Content-Type", "application/json");
  }

  return merged;
}

function buildUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;
  return `${API_BASE}/${cleanPath}`;
}

function buildCoreUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;
  return `${CORE_BASE}/${cleanPath}`;
}

type ResponseType = "json" | "text" | "blob";

async function handleResponse<T>(
  res: Response,
  responseType?: ResponseType
): Promise<T> {
  const fallbackType: ResponseType = res.headers
    .get("content-type")
    ?.includes("application/json")
    ? "json"
    : "text";

  const kind = responseType ?? fallbackType;

  let payload: any;
  if (kind === "blob") {
    payload = await res.blob();
  } else if (kind === "text" || (kind === "json" && res.status === 204)) {
    payload = res.status === 204 ? "" : await res.text();
  } else {
    payload = await res.json();
  }

  if (!res.ok) {
    const detail =
      (kind === "json" && (payload as Record<string, unknown>)?.detail) ||
      (typeof payload === "string" ? payload : null) ||
      res.statusText;

    throw new ApiError(detail || `HTTP ${res.status}`, {
      status: res.status,
      data: payload,
    });
  }

  return payload as T;
}

type RequestOptions = RequestInit & { responseType?: ResponseType };

function prepareBody(body: unknown): BodyInit | null | undefined {
  if (body == null) return undefined;
  if (typeof FormData !== "undefined" && body instanceof FormData) return body;
  if (body instanceof Blob) return body;
  if (body instanceof URLSearchParams) return body;
  if (body instanceof ArrayBuffer) return body;
  if (ArrayBuffer.isView(body)) return body as ArrayBufferView;
  if (typeof body === "string") return body;
  return JSON.stringify(body);
}

async function request<T>(path: string, init?: RequestOptions) {
  const preparedBody = prepareBody(init?.body);
  const headers = buildHeaders(init?.headers, preparedBody ?? undefined);
  const response = await fetch(buildUrl(path), {
    credentials: "include",
    ...init,
    headers,
    body: preparedBody,
  });

  return handleResponse<T>(response, init?.responseType);
}

async function coreRequest<T>(path: string, init?: RequestOptions) {
  const preparedBody = prepareBody(init?.body);
  const headers = buildHeaders(init?.headers, preparedBody ?? undefined);
  const response = await fetch(buildCoreUrl(path), {
    credentials: "include",
    ...init,
    headers,
    body: preparedBody,
  });

  return handleResponse<T>(response, init?.responseType);
}

export const apiClient = {
  get: <T = unknown>(path: string, init?: RequestInit) =>
    request<T>(path, { ...init, method: "GET" }),
  getText: (path: string, init?: RequestInit) =>
    request<string>(path, { ...init, method: "GET", responseType: "text" }),
  getBlob: (path: string, init?: RequestInit) =>
    request<Blob>(path, { ...init, method: "GET", responseType: "blob" }),
  post: <T = unknown>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, {
      ...init,
      method: "POST",
      body,
    }),
  patch: <T = unknown>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, {
      ...init,
      method: "PATCH",
      body,
    }),
  put: <T = unknown>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, {
      ...init,
      method: "PUT",
      body,
    }),
  delete: <T = unknown>(path: string, init?: RequestInit) =>
    request<T>(path, { ...init, method: "DELETE" }),
};

export const coreClient = {
  get: <T = unknown>(path: string, init?: RequestInit) =>
    coreRequest<T>(path, { ...init, method: "GET" }),
  post: <T = unknown>(path: string, body?: unknown, init?: RequestInit) =>
    coreRequest<T>(path, {
      ...init,
      method: "POST",
      body,
    }),
  put: <T = unknown>(path: string, body?: unknown, init?: RequestInit) =>
    coreRequest<T>(path, {
      ...init,
      method: "PUT",
      body,
    }),
  patch: <T = unknown>(path: string, body?: unknown, init?: RequestInit) =>
    coreRequest<T>(path, {
      ...init,
      method: "PATCH",
      body,
    }),
};

export { API_BASE, CRM_API_BASE, CORE_AUTH_BASE, CORE_BASE };
