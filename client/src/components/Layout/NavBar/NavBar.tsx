import Logo from "./Logo";
import NavMenu from "./NavMenu";

export default function NavBar() {
  return (
    <nav className="w-full h-[60px] bg-[#2E3336] flex items-center px-8">
      <Logo />
      <NavMenu />
    </nav>
  );
}
