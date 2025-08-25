const tabs = ["Items", "Discounts & Credits"];

export default function TabSection({
  activeTab,
  onChange,
}: {
  activeTab: string;
  onChange: (t: string) => void;
}) {
  return (
    <div className="flex gap-6 border-b border-gray-200 px-8 pt-2">
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={`p-4 text-md border-b-2 ${activeTab === tab ? "border-blue-500 text-blue-700" : "border-transparent text-gray-400 hover:text-blue-500"}`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
