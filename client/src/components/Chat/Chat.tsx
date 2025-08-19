import MessageBubble from "./MessageBubble";
import ChatInputBar from "./ChatInputBar";
import { MdNoteAdd, MdEditNote } from "react-icons/md";
import type { DisplayMode } from "../../store/DisplayModeContext";

import QuoteDraft from "./QuoteDraft";
import type { Scenario, Quote } from "../../types/Quotes";
import NewEmptyChat from "./NewEmptyChat";

interface ChatProps {
  setMode?: (mode: DisplayMode) => void;
  chatMessages: Array<{
    id?: string;
    role: string;
    content: string;
    timestamp?: string;
    scenarioIds?: string[];
  }>;
  scenarios: Scenario[];
  onSendText?: (text: string) => void;
  mode?: DisplayMode;
  thinking?: boolean;
}

export default function Chat({
  chatMessages,
  onSendText,
  mode,
  scenarios,
  setMode,
  thinking,
}: ChatProps) {
  const hasQuote = (s: Scenario): s is Scenario & { quote: Quote } =>
    s.quote !== null;
  return (
    <div className="flex flex-col h-full w-full">
      <main className="flex-1 bg-[#F9FAFB] w-full h-full px-8 overflow-y-auto py-8">
        <div className="text-xs text-gray-400 text-right pr-2 pb-1"></div>
        <div className="flex flex-col gap-4">
          {/* Render chat messages normally */}
          {chatMessages.length > 0 &&
            chatMessages.map((msg, index) => (
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
            ))}
          {/* Thinking indicator */}
          {thinking && (
            <MessageBubble
              avatar="CC"
              message={
                <div className="flex items-center gap-2 text-gray-600">
                  <span className="italic">Thinking</span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-sky-400 animate-bounce [animation-delay:-0.3s]"></span>
                    <span className="w-2 h-2 rounded-full bg-sky-400 animate-bounce [animation-delay:-0.15s]"></span>
                    <span className="w-2 h-2 rounded-full bg-sky-400 animate-bounce"></span>
                  </span>
                </div>
              }
              time={""}
              align={"left"}
            />
          )}
          {/* Show QuoteDraft only once if mode is 'draft' and there is a scenario with a quote */}
          {mode === "draft" &&
            Array.isArray(scenarios) &&
            (() => {
              const scenarioWithQuote = scenarios.find(hasQuote);
              if (!scenarioWithQuote) return null;
              return (
                <QuoteDraft
                  key={"quote-draft-main"}
                  quote={scenarioWithQuote.quote}
                  scenarioLabel={scenarioWithQuote.label}
                  setMode={setMode}
                />
              );
            })()}

          {chatMessages.length === 0 && (
            <NewEmptyChat onSendText={onSendText ?? (() => {})} />
          )}
        </div>
      </main>
      {chatMessages.length > 0 && (
        <>
          <div className="flex justify-evenly gap-3 mt-4 pb-3">
            <button className="bg-white text-[#0369A1] border border-[#BAE6FD] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition flex items-center gap-2">
              <MdNoteAdd className="w-6 h-6" /> Create Order
            </button>
            <button className="bg-white text-[#0369A1] border border-[#BAE6FD] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition flex items-center gap-2">
              <MdEditNote className="w-6 h-6" /> Engage with AM
            </button>
          </div>
          <div className="w-full bg-[#E0F2FE] border-t border-[#BAE6FD]/70 px-8">
            <ChatInputBar onSendText={onSendText ?? (() => {})} />
          </div>
        </>
      )}
    </div>
  );
}
