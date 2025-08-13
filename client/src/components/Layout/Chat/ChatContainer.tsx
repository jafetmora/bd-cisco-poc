import { useState } from "react";
import { useQuote } from "../../../store/useQuote";
import { FaHistory } from "react-icons/fa";
import { BsPencilSquare } from "react-icons/bs";
import MessageBubble from "./MessageBubble";
import ChatInputBar from "./ChatInputBar";
import { MdNoteAdd, MdEditNote, MdEmail } from "react-icons/md";
import ChatHistory from "./ChatHistory";

const chatHistoryData = [
  {
    id: 1,
    title: "Cisco Duo Subscription for 100 users",
    lastMessage: "Sure! Here's a quote for Cisco Duo Subscription...",
    time: "Today, 10:15 AM",
  },
  {
    id: 2,
    title: "Renewal: Secure Endpoint",
    lastMessage: "Renewal details sent to your email.",
    time: "Yesterday, 4:37 PM",
  },
  {
    id: 3,
    title: "General Inquiry",
    lastMessage: "Can you send me the updated price list?",
    time: "2 days ago",
  },
];

type TabType = "history" | "chat";

export default function ChatContainer() {
  const { quoteSession, sendQuoteUpdate } = useQuote();
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("chat");

  const handleSelectHistory = (id: number) => {
    console.log("Selected history item:", id);
    setIsHistoryOpen(false);
    console.log("isHistoryOpen:", isHistoryOpen);
  };

  const handleSendText = async (text: string) => {
    if (!quoteSession) return;

    const userMsg = {
      id: crypto.randomUUID(),
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

  return (
    <div
      className="
        grid h-full min-h-0 w-full
        grid-rows-[auto,1fr,auto]
        bg-[#F8FAFB] shadow border border-gray-200 overflow-hidden
      "
    >
      {/* Header (row 1) */}
      <div className="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-[187px]">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-sky-400 to-primary flex items-center justify-center p-4">
            <span className="font-light text-white text-lg">CC</span>
          </div>
          <span className="font-segoe text-primary text-lg leading-8 tracking-[-0.6px]">
            AI Assistant
          </span>
        </div>
        <div className="flex gap-3">
          <button
            title="Chat History"
            className={`p-2 rounded-full transition ${activeTab === "history" ? "bg-blue-100 text-blue-600" : "text-gray-600 hover:text-blue-600"}`}
            onClick={() => setActiveTab("history")}
            aria-selected={activeTab === "history"}
          >
            <FaHistory className="w-6 h-6" />
          </button>
          <button
            title="Chat"
            className={`p-2 rounded-full transition ${activeTab === "chat" ? "bg-blue-100 text-blue-600" : "text-gray-600 hover:text-blue-600"}`}
            onClick={() => setActiveTab("chat")}
            aria-selected={activeTab === "chat"}
          >
            <BsPencilSquare className="w-6 h-6" />
          </button>
        </div>
      </div>

      {/* Contenido scrollable (row 2) */}
      <div className="overflow-y-auto px-4 py-6 space-y-6 min-h-0">
        {activeTab === "history" && (
          <ChatHistory
            previousChats={chatHistoryData}
            onSelect={handleSelectHistory}
          />
        )}

        {activeTab === "chat" &&
          (quoteSession?.chatMessages?.length ? (
            quoteSession.chatMessages.map((msg, index) => (
              <MessageBubble
                key={msg.id || index}
                avatar={msg.role === "assistant" ? "CC" : "RM"}
                message={msg.content}
                time={
                  msg.timestamp
                    ? new Date(msg.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : ""
                }
                align={msg.role === "assistant" ? "left" : "right"}
              />
            ))
          ) : (
            <div className="h-full w-full flex items-center justify-center text-gray-400 text-sm">
              Start typing to generate a quote…
            </div>
          ))}
      </div>

      {/* Footer SIEMPRE abajo (row 3) */}
      {activeTab === "chat" && (
        <div className="border-t border-[#BAE6FD]/70 pt-3 bg-[#F8FAFB]">
          <div className="flex justify-evenly gap-3 mb-4">
            <button className="bg-white text-[#0369A1] border border-[#BAE6FD] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition flex items-center gap-2">
              <MdNoteAdd className="w-6 h-6" /> Create Order
            </button>
            <button className="bg-white text-[#0369A1] border border-[#BAE6FD] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition flex items-center gap-2">
              <MdEditNote className="w-6 h-6" /> Engage with AM
            </button>
            <button className="bg-white text-[#0369A1] border border-[#BAE6FD] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition flex items-center gap-2">
              <MdEmail className="w-6 h-6" /> Draft Email
            </button>
          </div>

          <ChatInputBar onSendText={handleSendText} />
        </div>
      )}
    </div>
  );
}
