import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { QuoteSession } from "../types/Quotes";
import { socket } from "../services/socket";
import { QuoteContext, type QuoteContextValue } from "./QuoteContext";
import { getQuote, updateQuote } from "../services/api";
import { v4 as uuidv4 } from "uuid";
import { useAuth } from "../hooks/useAuth";

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
  const { state: authState, isAuthenticated } = useAuth();

  const applyQuoteUpdate = useCallback<QuoteContextValue["applyQuoteUpdate"]>(
    (payload) => setQuoteSession(payload),
    [],
  );

  const sendQuoteUpdate = useCallback<QuoteContextValue["sendQuoteUpdate"]>(
    (payload) => {
      setQuoteSession({ ...payload, thinking: true });
      socket.emit("QUOTE_UPDATED_CLIENT", payload);
    },
    [],
  );

  const loadExistingQuoteSession = useCallback(async (sessionId: string) => {
    setLoading(true);
    setError(null);
    try {
      const quoteSession = await getQuote(sessionId);
      setQuoteSession({ ...quoteSession, thinking: false });
    } catch (e: unknown) {
      setError(getErrorMessage(e) ?? "Failed to load initial quote");
    } finally {
      setLoading(false);
    }
  }, []);

  const saveQuoteSession = useCallback(async (session: QuoteSession): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const savedSession = await updateQuote(session);
      setQuoteSession({ ...savedSession, thinking: false, unsavedChanges: false });
    } catch (e: unknown) {
      setError(getErrorMessage(e) ?? "Failed to save quote session");
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadInitialQuoteSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const emptySession: QuoteSession = {
        id: uuidv4(),
        userId: "user-local",
        chatMessages: [],
        scenarios: [],
        title: "New Session",
        thinking: false,
        unsavedChanges: false,
      };
      setQuoteSession(emptySession);
    } catch (e: unknown) {
      setError(getErrorMessage(e) ?? "Failed to load initial quote");
    } finally {
      setLoading(false);
    }
  }, []);

  const onSocketMessage = useCallback(
    (payload: QuoteSession) => {
      applyQuoteUpdate({ ...payload, thinking: false });
    },
    [applyQuoteUpdate],
  );

  useEffect(() => {
    socket.on("QUOTE_UPDATED", onSocketMessage);
    return () => {
      socket.off("QUOTE_UPDATED", onSocketMessage);
    };
  }, [onSocketMessage]);

  useEffect(() => {
    if (isAuthenticated && authState.token) {
      socket.connect(authState.token);
    } else {
      socket.disconnect();
    }
  }, [isAuthenticated, authState.token]);

  useEffect(() => {
    loadInitialQuoteSession();
  }, [loadInitialQuoteSession]);

  const value = useMemo<QuoteContextValue>(
    () => ({
      quoteSession,
      loading,
      error,
      loadExistingQuoteSession,
      loadInitialQuoteSession,
      saveQuoteSession,
      connectSocket: () => {},
      disconnectSocket: () => {},
      applyQuoteUpdate,
      sendQuoteUpdate,
    }),
    [
      quoteSession,
      loading,
      error,
      loadExistingQuoteSession,
      loadInitialQuoteSession,
      applyQuoteUpdate,
      sendQuoteUpdate,
    ],
  );

  return (
    <QuoteContext.Provider value={value}>{children}</QuoteContext.Provider>
  );
}
