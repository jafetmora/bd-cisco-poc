import { useState } from "react";
import { FaChevronDown, FaFileImport, FaSearch } from "react-icons/fa";

export default function ItemSearchHeader() {
  const [showPreferences, setShowPreferences] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div className="bg-gray-100 mt-3 mx-8 rounded-md p-4 flex flex-wrap md:flex-nowrap items-center justify-between gap-8">
      <div
        className={`flex items-center gap-2 flex-1 bg-white rounded-md px-3 py-4 transition-all duration-300 ${isFocused ? "ring-2 ring-blue-300 shadow-md" : ""}`}
      >
        <FaSearch className="text-gray-500 w-4 h-4" />
        <input
          type="text"
          placeholder="Add items by SKU, Description and product family"
          className="bg-transparent w-full text-xl placeholder-gray-400 focus:outline-none"
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
        />
      </div>
      <label className="text-blue-600 text-md cursor-pointer flex items-center gap-2 whitespace-nowrap">
        <FaFileImport className="w-4 h-4" />
        <input type="file" className="hidden" />
        Import Quote
      </label>
      <div className="relative">
        <button
          className="text-md text-blue-600 flex items-center gap-2 whitespace-nowrap"
          onClick={() => setShowPreferences((prev) => !prev)}
        >
          Quote Preferences <FaChevronDown className="w-3 h-3" />
        </button>
        {showPreferences && (
          <div className="absolute right-0 mt-2 w-52 bg-white shadow border border-gray-200 rounded-md z-10 text-md">
            <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
              Preference A
            </div>
            <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
              Preference B
            </div>
            <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
              Preference C
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
