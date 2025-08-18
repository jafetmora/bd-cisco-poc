import React, { createContext, useContext, useState } from "react";

export type DisplayMode = "draft" | "detailed";

interface DisplayModeContextType {
  mode: DisplayMode;
  setMode: (mode: DisplayMode) => void;
}

const DisplayModeContext = createContext<DisplayModeContextType | undefined>(undefined);

export const DisplayModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<DisplayMode>("draft");
  return (
    <DisplayModeContext.Provider value={{ mode, setMode }}>
      {children}
    </DisplayModeContext.Provider>
  );
};

export function useDisplayMode() {
  const context = useContext(DisplayModeContext);
  if (!context) {
    throw new Error("useDisplayMode must be used within a DisplayModeProvider");
  }
  return context;
}
