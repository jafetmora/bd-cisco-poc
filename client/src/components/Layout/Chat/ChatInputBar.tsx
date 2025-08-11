import { useState } from "react";
import { FiSend, FiPaperclip } from "react-icons/fi";

interface ChatInputBarProps {
  onSendText: (text: string) => void | Promise<void>;
}

export default function ChatInputBar({ onSendText }: ChatInputBarProps) {
  const [text, setText] = useState("");

  const handleSend = async () => {
    const value = text.trim();
    if (!value) return;
    setText("");
    await onSendText(value);
  };

  return (
    <div className="bg-[#E0F2FE] p-5">
      <div className="bg-white rounded-full shadow flex justify-center items-center px-4 py-2">
        <input
          className="flex-1 bg-transparent text-sm placeholder-gray-400 focus:outline-none"
          placeholder="Type..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
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
