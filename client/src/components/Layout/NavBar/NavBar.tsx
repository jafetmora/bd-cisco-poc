import Logo from "./Logo";
import NavMenu from "./NavMenu";

export default function NavBar() {
  return (
    <nav className="bg-white shadow-nav h-20 flex flex-row items-center px-8 w-full justify-between">
      <Logo />
      <NavMenu />
    </nav>
  );
}
