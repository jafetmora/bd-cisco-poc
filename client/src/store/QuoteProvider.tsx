import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { QuotePayload } from "../types/Quotes";
import { getMockQuote } from "../services/mockApi";
import { mockSocket } from "../services/mockSocket";
import { QuoteContext, type QuoteContextValue } from "./QuoteContext";

function getErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  try {
    return JSON.stringify(err);
  } catch {
    return "Unknown error";
  }
}

export function QuoteProvider({ children }: { children: ReactNode }) {
  const [quote, setQuote] = useState<QuotePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyQuoteUpdate = useCallback<QuoteContextValue["applyQuoteUpdate"]>(
    (payload) => setQuote(payload),
    [],
  );

  const loadInitialQuote = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await getMockQuote();
      setQuote(payload);
    } catch (e: unknown) {
      setError(getErrorMessage(e) ?? "Failed to load initial quote");
    } finally {
      setLoading(false);
    }
  }, []);

  const onSocketMessage = useCallback(
    (payload: QuotePayload) => {
      applyQuoteUpdate(payload);
    },
    [applyQuoteUpdate],
  );

  const connectSocket = useCallback(() => {
    mockSocket.on("QUOTE_UPDATED", onSocketMessage);
  }, [onSocketMessage]);

  const disconnectSocket = useCallback(() => {
    mockSocket.off("QUOTE_UPDATED", onSocketMessage);
  }, [onSocketMessage]);

  useEffect(() => {
    loadInitialQuote();
    connectSocket();
    return () => disconnectSocket();
  }, [loadInitialQuote, connectSocket, disconnectSocket]);

  const value = useMemo<QuoteContextValue>(
    () => ({
      quote,
      loading,
      error,
      loadInitialQuote,
      connectSocket,
      disconnectSocket,
      applyQuoteUpdate,
    }),
    [
      quote,
      loading,
      error,
      loadInitialQuote,
      connectSocket,
      disconnectSocket,
      applyQuoteUpdate,
    ],
  );

  return (
    <QuoteContext.Provider value={value}>{children}</QuoteContext.Provider>
  );
}
