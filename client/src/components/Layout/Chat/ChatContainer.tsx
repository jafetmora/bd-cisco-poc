import { useRef, useState } from "react";
import { FaHistory } from "react-icons/fa";
import { BsPencilSquare } from "react-icons/bs";
import MessageBubble from "./MessageBubble";
import ChatInputBar from "./ChatInputBar";
import { MdNoteAdd, MdEditNote, MdEmail } from "react-icons/md";
import ChatHistory from "./ChatHistory";

const chatData = [
  {
    avatar: "RM",
    message:
      "I want a quote for Cisco Duo Subscription and Secure Endpoint for 100 users, 2 years, Advantage edition, and 5 hardware tokens.",
    time: "10:12 AM",
  },
  {
    avatar: "CC",
    message:
      "Sure! Here's a quote for Cisco Duo Subscription (Advantage edition, 2 years, 100 users):",
    time: "10:13 AM",
  },
  {
    avatar: "RM",
    message: "change client Request Date to 26",
    time: "10:14 AM",
  },
  {
    avatar: "CC",
    message: "Sure! changing the date",
    time: "10:15 AM",
  },
];

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

type TabType = 'history' | 'chat';

export default function ChatContainer() {
  const [messages, setMessages] = useState(chatData);
  const [activeTab, setActiveTab] = useState<TabType>('chat');

  // Optional: ref for click outside (not required for fixed overlay)
  const historyPanelRef = useRef<HTMLDivElement>(null);

  const handleSelectHistory = (id: number) => {
    // Could load the selected chat here
  };

  return (
    <div className="flex flex-col h-full w-full bg-[#F8FAFB] shadow border border-gray-200 overflow-hidden relative">
      {/* Chat header */}
      <div className="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-[187px]">
          {/* Logo (placeholder) */}
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-sky-400 to-primary flex items-center justify-center p-4">
            <span className="font-light text-white text-lg">CC</span>
          </div>
          <span className="font-segoe text-primary text-lg leading-8 tracking-[-0.6px]">
            AI Assistant
          </span>
        </div>
        {/* Tab bar with icons */}
        <div className="flex gap-3">
          <button
            title="Chat History"
            className={`p-2 rounded-full transition ${activeTab === 'history' ? 'bg-blue-100 text-blue-600' : 'text-gray-600 hover:text-blue-600'}`}
            onClick={() => setActiveTab('history')}
            aria-selected={activeTab === 'history'}
          >
            <FaHistory className="w-6 h-6" />
          </button>
          <button
            title="Chat"
            className={`p-2 rounded-full transition ${activeTab === 'chat' ? 'bg-blue-100 text-blue-600' : 'text-gray-600 hover:text-blue-600'}`}
            onClick={() => setActiveTab('chat')}
            aria-selected={activeTab === 'chat'}
          >
            <BsPencilSquare className="w-6 h-6" />
          </button>
        </div>
      </div> 

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {activeTab === 'history' && (
          <ChatHistory previousChats={chatHistoryData} onSelect={handleSelectHistory} />
        )}
        {activeTab === 'chat' && (
          <>
            {messages.map((msg, index) => (
              <MessageBubble key={index} {...msg} />
            ))}
          </>
        )}
      </div>

      {/* Chat actions and input only for Chat tab */}
      {activeTab === 'chat' && (
        <>
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
          {/* Input and quick actions */}
          <ChatInputBar onSend={(msg) => setMessages([...messages, msg])} />
        </>
      )}
    </div>
  );
}
