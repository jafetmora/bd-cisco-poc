// MessageBubble.tsx
// Bubble styled according to feedback with CC/RM colors, full-width, and timestamp positioning

interface MessageBubbleProps {
  avatar: string;
  message: string;
  time?: string;
  align?: "left" | "right";
}

export default function MessageBubble({
  avatar,
  message,
  time,
}: MessageBubbleProps) {
  const isAssistant = avatar === "CC";
  const textColor = "text-gray-800";

  return (
    <div className="w-full flex">
      <div className="flex gap-3 items-start w-full">
        <div
          className={`w-14 h-12 rounded-full flex items-center font-light justify-center text-md 
    ${
      isAssistant
        ? "text-white bg-gradient-to-b from-[#38BDF8] to-[#0369A1]"
        : "text-[#0369A1] bg-[#E0F2FE]"
    }`}
        >
          {avatar}
        </div>

        <div
          className={`rounded-xl shadow-md p-4 w-full bg-white ${textColor} relative`}
        >
          <div className="whitespace-pre-line font-light text-md mb-4">
            {message}
          </div>
          {time && (
            <div className="absolute bottom-2 left-4 text-[10px] text-gray-500">
              {time}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
