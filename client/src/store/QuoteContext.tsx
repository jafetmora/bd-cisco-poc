import { createContext } from "react";
import type { QuoteSession } from "../types/Quotes";

export type QuoteContextValue = {
  quoteSession: QuoteSession | null;
  loading: boolean;
  error: string | null;
  loadExistingQuoteSession: (sessionId: string) => Promise<void>;
  loadInitialQuoteSession: () => Promise<void>;
  saveQuoteSession: (session: QuoteSession) => Promise<void>;
  connectSocket: () => void;
  disconnectSocket: () => void;
  applyQuoteUpdate: (payload: QuoteSession) => void;
  sendQuoteUpdate: (payload: QuoteSession) => void;
};

export const QuoteContext = createContext<QuoteContextValue | undefined>(
  undefined,
);
