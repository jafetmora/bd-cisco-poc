import ChatContainer from "../Chat/ChatContainer";

export default function Aside() {
  return (
    <aside className="w-[20%] bg-gray-100 border-r border-gray-200 flex flex-col min-h-0">
      <ChatContainer />
    </aside>
  );
}
