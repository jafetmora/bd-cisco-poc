import React from "react";
import "./spinner.css";
import { useQuote } from "../../store/useQuote";
import QuoteTab from "../Quote/QuoteTab";
import QuoteStatusBar from "../Quote/QuoteStatusBar";
import Chat from "../Chat/Chat";
import { useDisplayMode } from "../../store/DisplayModeContext";

export default function MainPanelContainer() {
  const { quoteSession, loading, error, sendQuoteUpdate, saveQuoteSession } = useQuote();
  const { mode, setMode } = useDisplayMode();

  const handleSendText = (text: string) => {
    if (!quoteSession) return;
    const userMsg = {
      id: Date.now().toString(),
      sessionId: quoteSession.id,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    const updatedSession = {
      ...quoteSession,
      chatMessages: [...(quoteSession.chatMessages || []), userMsg],
    };
    sendQuoteUpdate(updatedSession);
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full text-red-600">
        Error: {error}
      </div>
    );
  }

  if (loading || !quoteSession) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full text-gray-500">
        <svg className="animate-spin-smooth" width="102" height="103" viewBox="0 0 102 103" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" clip-rule="evenodd" d="M96.9549 58.1172C99.6412 58.9642 101.132 61.8284 100.285 64.5147L99.0142 68.546L97.3114 72.6569L95.2568 76.6038L92.866 80.3565L90.1573 83.8866L87.1512 87.1672L83.8706 90.1733L80.3405 92.8821L76.5877 95.2728L72.8384 97.2246C70.34 98.5252 67.2603 97.5542 65.9597 95.0558C64.6591 92.5574 65.6301 89.4777 68.1285 88.1771L71.4829 86.431L74.4844 84.5188L77.3079 82.3522L79.9318 79.9479L82.3362 77.3239L84.5027 74.5005L86.4149 71.4989L88.0582 68.3421L89.4202 65.0541L90.5573 61.4475C91.4043 58.7612 94.2686 57.2702 96.9549 58.1172Z" fill="#2859B6"/>
        <path fill-rule="evenodd" clip-rule="evenodd" d="M97.3928 48.1111C94.6429 48.7207 91.9195 46.9857 91.3098 44.2358L90.4913 40.5439L89.4211 37.1497L88.0592 33.8616L86.4159 30.7048L84.5037 27.7033L82.3371 24.8798L79.9328 22.2559L77.3089 19.8515L74.4854 17.685L71.4838 15.7728L68.327 14.1295L65.039 12.7675L61.6448 11.6973L58.1703 10.927L54.6418 10.4625L51.0862 10.3073L47.5307 10.4625L44.0023 10.927L40.5277 11.6973L37.1335 12.7675L33.8455 14.1295L30.6887 15.7728L27.6871 17.685L24.8636 19.8515L22.2397 22.2559L19.8354 24.8798L17.6688 27.7033L15.7566 30.7048L14.1133 33.8617L12.7514 37.1496L11.6812 40.5439L10.9109 44.0184L10.4464 47.5469L10.2911 51.1025L10.4463 54.6579L10.9109 58.1864L11.6812 61.661L12.7514 65.0552L14.1133 68.3432L15.7566 71.5L17.6688 74.5015L19.8354 77.325L22.2398 79.9489L24.8636 82.3533L27.6871 84.5198L30.6887 86.4321L33.8455 88.0754L37.1334 89.4373L40.5277 90.5075L44.0022 91.2778L47.5307 91.7423L51.3087 91.9073C54.1227 92.0301 56.3043 94.4109 56.1814 97.2249C56.0585 100.039 53.6778 102.22 50.8638 102.098L46.6409 101.913L42.2294 101.332L37.8852 100.369L33.6416 99.0313L29.5307 97.3285L25.5838 95.2739L21.8311 92.8831L18.301 90.1744L15.0204 87.1683L12.0143 83.8877L9.30551 80.3576L6.91475 76.6048L4.86015 72.658L3.15737 68.5471L1.81935 64.3034L0.856273 59.9593L0.275478 55.5478L0.081394 51.1024L0.275492 46.657L0.856279 42.2455L1.81935 37.9014L3.15736 33.6577L4.86015 29.5468L6.91475 25.6L9.30553 21.8472L12.0143 18.3171L15.0204 15.0365L18.301 12.0304L21.8311 9.32168L25.5838 6.93091L29.5307 4.87632L33.6416 3.17353L37.8852 1.83551L42.2294 0.872438L46.6409 0.291645L51.0862 0.0975568L55.5316 0.291644L59.9432 0.872436L64.2873 1.8355L68.5309 3.17353L72.6418 4.87631L76.5887 6.93091L80.3414 9.32168L83.8715 12.0304L87.1521 15.0365L90.1582 18.3171L92.867 21.8472L95.2578 25.6L97.3123 29.5468L99.0151 33.6577L100.353 37.9014L101.268 42.0281C101.878 44.778 100.143 47.5014 97.3928 48.1111Z" fill="#CADCED"/>
        </svg>
      </div>
    );
  }

  return (
    <div className="min-h-screen h-full w-full flex flex-col">
      {mode === "draft" ? (
        <Chat
          chatMessages={quoteSession?.chatMessages || []}
          scenarios={quoteSession?.scenarios || []}
          thinking={quoteSession?.thinking || false}
          mode={mode}
          setMode={setMode}
          onSendText={handleSendText}
        />
      ) : (
        <>
          <div className="flex-1 flex flex-col">
            <QuoteTab
              scenarios={quoteSession?.scenarios || []}
              title={quoteSession?.title || ""}
            />
          </div>
          <QuoteStatusBar
            modified={quoteSession?.unsavedChanges || false}
            onSave={() => {
              if (!quoteSession) return;
              saveQuoteSession(quoteSession);
            }}
          />
        </>
      )}
    </div>
  );
}
