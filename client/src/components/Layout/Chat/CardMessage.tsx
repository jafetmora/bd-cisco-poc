interface CardMessageProps {
  avatar: string;
  name?: string;
  message: string;
  time: string;
  align?: "left" | "right";
  accent?: boolean;
}

export default function CardMessage({
  avatar,
  message,
  time,
  align = "left",
  accent = false,
}: CardMessageProps) {
  const isRight = align === "right";
  return (
    <div
      className={`flex gap-3 items-start w-full ${isRight ? "justify-end flex-row-reverse" : ""}`}
    >
      <div
        className={`w-10 h-10 ${accent ? "bg-accent text-white" : "bg-secondary text-accent"} rounded-full flex items-center justify-center border-2 border-accent font-segoe text-lg font-bold`}
      >
        {avatar}
      </div>
      <div className={`flex-1 ${isRight ? "text-right" : ""}`}>
        <div
          className={`${accent ? "bg-white text-neutral border border-border" : "bg-secondary text-primary"} rounded-lg px-4 py-2 mb-1 inline-block max-w-[80%]`}
        >
          {message}
        </div>
        <div className={`text-xs text-light ${isRight ? "text-right" : ""}`}>
          {time}
        </div>
      </div>
    </div>
  );
}
