export default function Logo() {
  return (
    <div className="flex items-center gap-2 min-w-[187px]">
      {/* Logo gráfico (placeholder) */}
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sky-400 to-primary flex items-center justify-center">
        <span className="font-bold text-white text-lg">CC</span>
      </div>
      <span className="font-segoe text-primary text-2xl leading-8 tracking-[-0.6px]">
        Cisco Commerce
      </span>
    </div>
  );
}
