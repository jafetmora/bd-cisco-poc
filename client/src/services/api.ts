import axios from "axios";

const API_BASE_URL = import.meta.env?.VITE_API_URL ?? "http://localhost:8002";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: false,
});

export default api;

let AUTH_TOKEN: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setAuthToken(token: string | null) {
  AUTH_TOKEN = token;
}

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

api.interceptors.request.use((config) => {
  if (AUTH_TOKEN) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${AUTH_TOKEN}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(error);
  },
);

import type { QuoteSession } from "../types/Quotes";

export async function getQuote(sessionId?: string): Promise<QuoteSession> {
  const response = await api.get("/quote", {
    params: {
      sessionId,
    },
  });
  return response.data;
}
