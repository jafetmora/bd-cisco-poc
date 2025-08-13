import NavBar from "./NavBar/NavBar";
import Aside from "./Aside/Aside";
import QuoteMainView from "./Quote/Main";
import { QuoteProvider } from "../../store/QuoteProvider";

export default function Layout() {
  return (
    <QuoteProvider>
      <div className="max-h-screen flex flex-col h-screen">
        <NavBar />
        <div className="flex flex-1 min-h-0">
          <QuoteMainView />
          <Aside />
        </div>
      </div>
    </QuoteProvider>
  );
}
