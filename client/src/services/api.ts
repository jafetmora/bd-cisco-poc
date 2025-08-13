import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export default api;

import type { QuoteSession } from "../types/Quotes";

export async function getQuote(): Promise<QuoteSession> {
  const response = await api.get("/quote");
  return response.data;
}
