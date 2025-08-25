import { FiSidebar } from "react-icons/fi";
import { useQuote } from "../../store/useQuote";
import { useDisplayMode } from "../../store/DisplayModeContext";
import Chat from "../Chat/Chat";
import ChatHistory from "./ChatHistory";

const chatHistoryData = [
  {
    id: "1",
    title: "Cisco Duo Subscription for 100 users",
    lastMessage: "Sure! Here's a quote for Cisco Duo Subscription...",
    time: "Today, 10:15 AM",
  },
  {
    id: "2",
    title: "Renewal: Secure Endpoint",
    lastMessage: "Renewal details sent to your email.",
    time: "Yesterday, 4:37 PM",
  },
  {
    id: "3",
    title: "General Inquiry",
    lastMessage: "Can you send me the updated price list?",
    time: "2 days ago",
  },
];

export default function AIAssistantContainer() {
  const {
    quoteSession,
    sendQuoteUpdate,
    loadExistingQuoteSession,
    loadInitialQuoteSession,
  } = useQuote();
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

  const hasScenarios = (quoteSession?.scenarios?.length ?? 0) > 0;
  const toggleMode = () => {
    if (mode === "draft" && !hasScenarios) return;
    setMode(mode === "draft" ? "detailed" : "draft");
  };

  return (
    <aside className="w-[20%] bg-gray-100 border-r border-gray-200 flex flex-col">
      <div className="grid h-full min-h-0 w-full grid-rows-[auto,1fr,auto] bg-[#F8FAFB] shadow border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-[187px]">
            <img src="/image-icon.png" alt="Assistant" className="block" />
            <span className="font-segoe text-primary text-lg leading-8 tracking-[-0.6px]">
              AI Assistant
            </span>
          </div>
          <button
            className="ml-4 p-2 rounded bg-transparent hover:bg-sky-50 text-gray-700"
            onClick={toggleMode}
            aria-label="Toggle sidebar / mode"
            type="button"
            title={
              mode === "draft" && !hasScenarios
                ? "Add scenarios to enable Detailed view"
                : `Mode: ${mode === "draft" ? "Draft" : "Detailed"}`
            }
          >
            <FiSidebar className="w-[30px] h-[30px]" />
          </button>
        </div>
        {/* Content */}
        <div className="overflow-y-auto space-y-6 min-h-0">
          {mode === "detailed" ? (
            <Chat
              chatMessages={quoteSession?.chatMessages || []}
              scenarios={quoteSession?.scenarios || []}
              onSendText={handleSendText}
              mode={mode}
              thinking={quoteSession?.thinking}
            />
          ) : (
            <ChatHistory
              previousChats={chatHistoryData}
              onSelect={(sessionId) => loadExistingQuoteSession(sessionId)}
              onNew={loadInitialQuoteSession}
            />
          )}
        </div>
      </div>
    </aside>
  );
}
