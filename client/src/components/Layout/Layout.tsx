import NavBar from "./NavBar/NavBar";
import Aside from "./Aside/Aside";
import QuoteMainView from "./Quote/Main";

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />
      <div className="flex flex-1 min-h-0">
        <QuoteMainView />
        <Aside />
      </div>
    </div>
  );
}
