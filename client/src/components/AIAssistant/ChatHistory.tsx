import { useState } from "react";
import { FaRegCommentDots } from "react-icons/fa";
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
          className="flex items-center gap-2 px-3 py-2 rounded text-primary bg-sky-50 hover:bg-sky-100 font-medium text-sm transition"
          onClick={onNew}
        >
          <MdAddComment className="w-5 h-5" /> New Chat
        </button>
        <button className="flex items-center gap-2 px-3 py-2 rounded text-gray-700 bg-gray-100 hover:bg-gray-200 font-medium text-sm transition">
          <IoSearch className="w-5 h-5" /> Search Chat
        </button>
        <button className="flex items-center gap-2 px-3 py-2 rounded text-gray-700 bg-gray-100 hover:bg-gray-200 font-medium text-sm transition">
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
        <FaRegCommentDots className="w-5 h-5 text-primary" />
        <span className="font-segoe text-primary text-lg flex-1 text-left">Chat History</span>
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
            <li
              key={chat.id}
              className="flex items-center gap-3 bg-white rounded-xl border border-gray-200 shadow-sm px-4 py-3 hover:border-primary hover:shadow-md cursor-pointer transition group"
              onClick={() => onSelect?.(chat.id)}
            >
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-sky-400 to-primary flex items-center justify-center">
                <FaRegCommentDots className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-neutral truncate max-w-[200px] group-hover:text-primary">
                    {chat.title}
                  </span>
                  <span className="text-xs text-gray-400 ml-2 whitespace-nowrap">
                    {chat.time}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-1 truncate max-w-[240px]">
                  {chat.lastMessage}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
