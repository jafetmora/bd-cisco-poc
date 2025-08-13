import { useEffect, useRef, useState } from "react";

export function useHighlight<T>(
  value: T,
  ms = 1200,
  isEqual?: (a: T, b: T) => boolean,
) {
  const [highlight, setHighlight] = useState(false);
  const prevRef = useRef<T>(value);

  useEffect(() => {
    const eq = isEqual ?? ((a, b) => a === b);
    if (!eq(value, prevRef.current)) {
      setHighlight(true);
      const t = setTimeout(() => setHighlight(false), ms);
      prevRef.current = value;
      return () => clearTimeout(t);
    }
  }, [value, ms, isEqual]);

  return highlight;
}
