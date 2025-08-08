import { useState } from "react";
import { FiSend, FiPaperclip } from "react-icons/fi";

interface ChatInputBarProps {
  onSend: (msg: { avatar: string; message: string; time: string }) => void;
}

export default function ChatInputBar({ onSend }: ChatInputBarProps) {
  const [text, setText] = useState("");

  const handleSend = () => {
    if (!text.trim()) return;

    const userMessage = {
      avatar: "RM",
      message: text,
      time: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    onSend(userMessage);
    setText("");

    setTimeout(() => {
      const assistantReply = {
        avatar: "CC",
        message: generateMockReply(text),
        time: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        align: "right" as const,
      };
      onSend(assistantReply);
    }, 500);
  };

  const generateMockReply = (text: string): string => {
    const lower = text.toLowerCase();

    if (lower.includes("change") || lower.includes("update")) {
      return "Sure, updating the quote as requested.";
    }

    if (lower.includes("add") || lower.includes("include")) {
      return "Got it! Adding that to your quote.";
    }

    if (lower.includes("remove") || lower.includes("delete")) {
      return "Okay, I'll remove that from the quote.";
    }

    return "Thanks! I'll update the quote accordingly.";
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
