import AppHeader from "../layout/AppHeader/AppHeader";
import AppMain from "../layout/AppMain/AppMain";
import { QuoteProvider } from "../store/QuoteProvider";
import { DisplayModeProvider } from "../store/DisplayModeContext";

export default function MainPage() {
  return (
    <QuoteProvider>
      <DisplayModeProvider>
        <div className="max-h-screen flex flex-col h-screen">
          <AppHeader />
          <AppMain />
        </div>
      </DisplayModeProvider>
    </QuoteProvider>
  );
}
