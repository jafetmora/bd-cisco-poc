import MainPanelContainer from "../../components/MainPanel/MainPanelContainer";
import AIAssistantContainer from "../../components/AIAssistant/AIAssistantContainer";
import { useDisplayMode } from "../../store/DisplayModeContext";

export default function AppMain() {
  const { mode } = useDisplayMode();
  return (
    <div className="flex flex-1 min-h-0">
      {mode === "draft" ? (
        <>
          <AIAssistantContainer />
          <MainPanelContainer />
        </>
      ) : (
        <>
          <MainPanelContainer />
          <AIAssistantContainer />
        </>
      )}
    </div>
  );
}
