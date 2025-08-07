import { useState } from "react";
import { FiSend, FiPaperclip } from "react-icons/fi";

interface ChatInputBarProps {
  onSend: (msg: {
    avatar: string;
    message: string;
    time: string;
    align: "right";
  }) => void;
}

export default function ChatInputBar({ onSend }: ChatInputBarProps) {
  const [text, setText] = useState("");

  const handleSend = () => {
    if (!text.trim()) return;
    onSend({
      avatar: "CC",
      message: text,
      time: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      align: "right",
    });
    setText("");
  };

  return (
    <div className="bg-[#E0F2FE] p-5">
      {/* Input Bar */}
      <div className="bg-white rounded-full shadow flex justify-center items-center px-4 py-2">
        <input
          className="flex-1 bg-transparent text-sm placeholder-gray-400 focus:outline-none"
          placeholder="Type..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <label className="text-blue-600 text-md cursor-pointer flex items-center gap-2 whitespace-nowrap">
          <FiPaperclip className="w-5 h-5 text-gray-500 mx-2 cursor-pointer" />
          <input type="file" className="hidden" />
        </label>
        <button
          onClick={handleSend}
          className="bg-blue-500 hover:bg-blue-600 text-white p-2 rounded-full ml-2"
        >
          <FiSend className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
