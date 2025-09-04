interface QuoteStatusBarProps {
  modified: boolean;
  onSave: () => void;
  saving?: boolean;
}

export default function QuoteStatusBar({
  modified,
  onSave,
  saving,
}: QuoteStatusBarProps) {
  return (
    <div
      className="w-full flex items-center justify-between px-8 py-3 bg-white border-t-2 border-gray-300 shadow z-50 sticky bottom-0"
      style={{ minHeight: 56 }}
    >
      <div className="flex items-center gap-4">
        <span
          className={`text-sm font-medium ${modified ? "text-primary" : "text-gray-500"}`}
        >
          {modified ? "Unsaved changes" : "All changes saved"}
        </span>
      </div>
      <button
        className={`px-6 py-2 rounded font-semibold text-white transition-colors duration-200 focus:outline-none ${
          modified
            ? "bg-primary hover:bg-primary-dark"
            : "bg-gray-300 cursor-not-allowed"
        }`}
        onClick={onSave}
        disabled={!modified || saving}
      >
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}
