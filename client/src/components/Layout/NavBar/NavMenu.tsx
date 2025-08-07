export default function NavMenu() {
  return (
    <div className="flex items-center gap-6">
      {/* Sino de notificações */}
      <div className="relative">
        <button className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-secondary transition-colors">
          {/* Heroicon Bell */}
          <svg
            className="w-6 h-6 text-accent"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V4a2 2 0 10-4 0v1.341C6.67 7.165 6 8.97 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
        </button>
        <span className="absolute top-1 right-1 bg-pink text-white rounded-full text-xs w-5 h-5 flex items-center justify-center border-2 border-white">
          2
        </span>
      </div>
      {/* Botão +Create */}
      <button className="bg-accent text-white rounded-full px-4 py-2 shadow-button hover:bg-primary transition-colors font-segoe text-base font-medium flex items-center gap-2">
        <span className="font-bold text-lg">+</span> Create
      </button>
      {/* Campo de busca */}
      <div className="relative w-64">
        <input
          className="bg-grayBg border border-border rounded-full px-10 h-[42px] text-neutral w-full focus:outline-none focus:ring-2 focus:ring-accent placeholder:text-light font-segoe"
          placeholder="Search quotes, deals, customers..."
        />
        {/* Ícone de busca */}
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-accent"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
          <line
            x1="21"
            y1="21"
            x2="16.65"
            y2="16.65"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>
      {/* Avatar do usuário */}
      <div className="w-10 h-10 bg-secondary rounded-full flex items-center justify-center border-2 border-accent shadow-card font-segoe text-accent text-lg font-bold">
        RM
      </div>
      {/* Nome do usuário */}
      <span className="text-neutral font-segoe">Rafael Mauro</span>
    </div>
  );
}
