import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { QuoteSession } from "../types/Quotes";
import { getQuote } from "../services/api";
import { socket } from "../services/socket";
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
  const [quoteSession, setQuoteSession] = useState<QuoteSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyQuoteUpdate = useCallback<QuoteContextValue["applyQuoteUpdate"]>(
    (payload) => setQuoteSession(payload),
    [],
  );

  const sendQuoteUpdate = useCallback<QuoteContextValue["sendQuoteUpdate"]>(
    (payload) => {
      setQuoteSession(payload);
      socket.emit("QUOTE_UPDATED_CLIENT", payload);
    },
    [],
  );

  const loadInitialQuoteSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await getQuote();
      setQuoteSession(payload);
    } catch (e: unknown) {
      setError(getErrorMessage(e) ?? "Failed to load initial quote");
    } finally {
      setLoading(false);
    }
  }, []);

  const onSocketMessage = useCallback(
    (payload: QuoteSession) => {
      applyQuoteUpdate(payload);
    },
    [applyQuoteUpdate],
  );

  const connectSocket = useCallback(() => {
    socket.on("QUOTE_UPDATED", onSocketMessage);
  }, [onSocketMessage]);

  const disconnectSocket = useCallback(() => {
    socket.off("QUOTE_UPDATED", onSocketMessage);
  }, [onSocketMessage]);

  useEffect(() => {
    loadInitialQuoteSession();
    connectSocket();
    return () => disconnectSocket();
  }, [loadInitialQuoteSession, connectSocket, disconnectSocket]);

  const value = useMemo<QuoteContextValue>(
    () => ({
      quoteSession,
      loading,
      error,
      loadInitialQuoteSession,
      connectSocket,
      disconnectSocket,
      applyQuoteUpdate,
      sendQuoteUpdate,
    }),
    [
      quoteSession,
      loading,
      error,
      loadInitialQuoteSession,
      connectSocket,
      disconnectSocket,
      applyQuoteUpdate,
      sendQuoteUpdate,
    ],
  );

  return (
    <QuoteContext.Provider value={value}>{children}</QuoteContext.Provider>
  );
}
