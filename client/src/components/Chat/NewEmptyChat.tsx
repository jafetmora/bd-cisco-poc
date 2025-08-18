 import { useState } from "react";
 import { FiSend } from "react-icons/fi";


interface NewEmptyChatProps {
  onSendText: (text: string) => void | Promise<void>;
}

export default function NewEmptyChat({ onSendText }: NewEmptyChatProps) {
  const [text, setText] = useState("");
  const suggestions: string[] = [
    "Build a quote with access switch for...",
    "Create a quote with Hypershield subscription with high speed core switch",
    "Show me all renewals coming up in 30 days",
  ];

  const handleClick = async (text: string) => {
    await onSendText(text);
  };

  const handleSend = async () => {
    const value = text.trim();
    if (!value) return;
    setText("");
    await onSendText(value);
  };

  return (
    <div className="w-full h-full flex flex-col items-center justify-center text-center gap-8 py-10">
      <div className="max-w-2xl px-4">
        <h1 className="text-2xl font-semibold text-slate-800">
          <img src="/image.png" alt="Hero" className="mx-auto block" />
        </h1>
      </div>

      {/* Inline input similar to ChatInputBar, centered and larger */}
      <div className="w-full px-6">
        <div className="max-w-3xl mx-auto bg-white rounded-full shadow flex items-center px-6 py-3">
          <input
            className="flex-1 min-w-0 w-full bg-transparent text-base placeholder-gray-400 focus:outline-none"
            placeholder="Type..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
          />
          <button
            onClick={handleSend}
            className="bg-blue-500 hover:bg-blue-600 text-white p-3 rounded-full ml-3"
          >
            <FiSend className="w-6 h-6" />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 justify-center px-4">
        {suggestions.map((s, i) => (
          <button
            key={i}
            className="bg-white border border-[#BAE6FD] text-[#0369A1] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition"
            onClick={() => handleClick(s)}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
