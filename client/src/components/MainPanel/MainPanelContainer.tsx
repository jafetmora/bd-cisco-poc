import { useQuote } from "../../store/useQuote";
import QuoteTab from "../Quote/QuoteTab";
import Chat from "../Chat/Chat";
import { useDisplayMode } from "../../store/DisplayModeContext";

export default function MainPanelContainer() {
  const { quoteSession, loading, error, sendQuoteUpdate } = useQuote();
  const { mode, setMode } = useDisplayMode();

  const handleSendText = (text: string) => {
    if (!quoteSession) return;
    const userMsg = {
      id: Date.now().toString(),
      sessionId: quoteSession.id,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    const updatedSession = {
      ...quoteSession,
      chatMessages: [...(quoteSession.chatMessages || []), userMsg],
    };
    sendQuoteUpdate(updatedSession);
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full text-red-600">
        Error: {error}
      </div>
    );
  }

  if (loading || !quoteSession) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full text-gray-500">
        Loading...
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      {mode === "draft" ? (
        <Chat chatMessages={quoteSession?.chatMessages || []} scenarios={quoteSession?.scenarios || []} mode={mode} setMode={setMode} onSendText={handleSendText}/>
      ) : (
        <QuoteTab scenarios={quoteSession?.scenarios || []} title={quoteSession?.title || ""}/>
      )}
    </div>
  );
}
