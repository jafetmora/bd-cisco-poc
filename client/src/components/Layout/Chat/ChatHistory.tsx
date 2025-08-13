import { FaRegCommentDots } from "react-icons/fa";

export type ChatHistoryItem = {
  id: number;
  title: string;
  lastMessage: string;
  time: string;
};

export default function ChatHistory({
  previousChats,
  onSelect,
}: {
  previousChats: ChatHistoryItem[];
  onSelect?: (id: number) => void;
}) {
  return (
    <div className="w-full bg-white border border-gray-200 rounded-xl shadow-md overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center gap-2 bg-gray-50">
        <FaRegCommentDots className="w-5 h-5 text-primary" />
        <span className="font-segoe text-primary text-lg">Chat History</span>
      </div>
      <ul className="divide-y divide-gray-100">
        {previousChats.map((chat) => (
          <li
            key={chat.id}
            className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition"
            onClick={() => onSelect?.(chat.id)}
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-neutral truncate max-w-[200px]">
                {chat.title}
              </span>
              <span className="text-xs text-light ml-2 whitespace-nowrap">
                {chat.time}
              </span>
            </div>
            <div className="text-xs text-light mt-1 truncate max-w-[240px]">
              {chat.lastMessage}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
