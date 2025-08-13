import { createContext } from "react";
import type { QuotePayload } from "../types/Quotes";

export type QuoteContextValue = {
  quote: QuotePayload | null;
  loading: boolean;
  error: string | null;
  loadInitialQuote: () => Promise<void>;
  connectSocket: () => void;
  disconnectSocket: () => void;
  applyQuoteUpdate: (payload: QuotePayload) => void;
};

export const QuoteContext = createContext<QuoteContextValue | undefined>(
  undefined,
);
