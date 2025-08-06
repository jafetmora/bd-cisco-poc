const threads = [
  {
    id: 1,
    title: 'Enterprise Duo Subscription',
    active: true,
  },
  {
    id: 2,
    title: 'Summarize my EA pipeline',
    active: false,
  },
  {
    id: 3,
    title: 
      "Who's assigned to my highest-value...",
    active: false,
  },
];

export default function ThreadsMenu() {
  return (
    <nav className="flex flex-col gap-2">
      <h2 className="font-segoe text-primary text-lg px-4 pt-4 pb-2">Threads</h2>
      {threads.map(thread => (
        <a
          key={thread.id}
          href="#"
          className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-colors font-segoe text-base leading-6
            ${thread.active ? 'bg-secondary text-primary font-semibold' : 'hover:bg-gray-50 text-neutral'}`}
        >
          {/* Ícone de chat (Heroicon) */}
          <svg className={`w-5 h-5 ${thread.active ? 'text-primary' : 'text-light'}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17 8h2a2 2 0 012 2v8a2 2 0 01-2 2H7a2 2 0 01-2-2v-2M15 3H9a2 2 0 00-2 2v12a2 2 0 002 2h6a2 2 0 002-2V5a2 2 0 00-2-2z" />
          </svg>
          <span className="truncate">{thread.title}</span>
        </a>
      ))}
    </nav>
  );
}
