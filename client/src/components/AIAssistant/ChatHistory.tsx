import { useState } from "react";
import { MdOutlineInsertComment } from "react-icons/md";
import { IoChevronDown, IoSearch } from "react-icons/io5";
import { MdAddComment } from "react-icons/md";
import { BsStack } from "react-icons/bs";

export type ChatHistoryItem = {
  id: string;
  title: string;
  lastMessage: string;
  time: string;
};

export default function ChatHistory({
  previousChats,
  onSelect,
  onNew,
}: {
  previousChats: ChatHistoryItem[];
  onSelect?: (id: string) => void;
  onNew?: () => void;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="w-full bg-transparent">
      {/* Vertical Menu always visible */}
      <nav className="flex flex-col gap-1 px-2 pb-3 pt-2">
        <button
          className="flex items-center gap-2 px-3 py-2 rounded text-primary bg-transparent hover:bg-sky-50 font-medium text-sm transition"
          onClick={onNew}
        >
          <MdAddComment className="w-5 h-5" /> New Chat
        </button>
        <button className="flex items-center gap-2 px-3 py-2 rounded text-gray-700 bg-transparent hover:bg-sky-50 font-medium text-sm transition">
          <IoSearch className="w-5 h-5" /> Search Chat
        </button>
        <button className="flex items-center gap-2 px-3 py-2 rounded text-gray-700 bg-transparent hover:bg-sky-50 font-medium text-sm transition">
          <BsStack className="w-5 h-5" /> All Quotes
        </button>
      </nav>
      {/* Accordion for chat history */}
      <button
        className="w-full px-2 py-2 flex items-center gap-2 group select-none focus:outline-none"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="chat-history-list"
        type="button"
      >
        <span className="font-segoe text-primary text-lg flex-1 text-left">Chats</span>
        <IoChevronDown
          className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${open ? "rotate-0" : "-rotate-90"}`}
        />
      </button>
      <div
        id="chat-history-list"
        className={`transition-all duration-200 ${open ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0 overflow-hidden"}`}
      >
        <ul className="flex flex-col gap-2">
          {previousChats.map((chat) => (
            <li key={chat.id}>
              <button
                className="w-full flex items-center gap-2 px-3 py-2 rounded text-gray-700 bg-transparent hover:bg-sky-50 font-medium text-sm transition"
                onClick={() => onSelect?.(chat.id)}
                type="button"
              >
                <MdOutlineInsertComment className="w-5 h-5 text-black flex-shrink-0" />
                <span className="flex-1 text-left truncate">{chat.title}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
