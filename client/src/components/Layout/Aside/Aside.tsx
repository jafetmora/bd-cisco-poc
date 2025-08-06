import HorizontalBorder from './HorizontalBorder';
import ThreadsMenu from './ThreadsMenu';

export default function Aside() {
  return (
    <aside className="w-64 bg-gray-100 border-r border-gray-200 flex flex-col min-h-0">
      <div className="flex-1 p-0">
        <ThreadsMenu />
      </div>
      <HorizontalBorder />
    </aside>
  );
}
