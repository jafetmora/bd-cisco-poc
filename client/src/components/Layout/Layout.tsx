import NavBar from './NavBar/NavBar';
import Aside from './Aside/Aside';
import Main from './Main/Main';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />
      <div className="flex flex-1 min-h-0">
        <Aside />
        <Main />
      </div>
    </div>
  );
}
