import { useContext } from "react";
import { QuoteContext } from "./QuoteContext";

export function useQuote() {
  const ctx = useContext(QuoteContext);
  if (!ctx) throw new Error("useQuote must be used within a QuoteProvider");
  return ctx;
}
