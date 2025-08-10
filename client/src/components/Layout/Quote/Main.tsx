// QuoteMainView.tsx - Step header + QuoteHeaderBar
import { useState } from "react";
import {
  FaChevronDown,
  FaShareAlt,
  FaPrint,
  FaEnvelope,
  FaTrash,
  FaPen,
  FaFileImport,
  FaSearch,
} from "react-icons/fa";
import QuotationTable from "./QuoteTable";

const steps = [
  "Deal",
  "Quote",
  "Install/Billing",
  "Review",
  "Approvals",
  "Orders",
];
const tabs = ["Items", "Discounts & Credits"];

function StepHeader({ currentStep = 1 }: { currentStep?: number }) {
  return (
    <div className="flex justify-between px-8 pt-6 pb-4">
      {steps.map((step, index) => (
        <div key={step} className="flex-1 flex flex-col items-center">
          <div
            className={`w-6 h-6 rounded-full flex items-center justify-center font-semibold text-xs ${index <= currentStep ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-600"}`}
          >
            {index + 1}
          </div>
          <div
            className={`text-xs mt-1 ${index === currentStep ? "text-blue-700 font-medium" : "text-gray-400"}`}
          >
            {step}
          </div>
        </div>
      ))}
    </div>
  );
}

function QuoteHeaderBar() {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="bg-white shadow rounded-xl mx-8 p-6 border border-gray-200 flex items-start justify-between">
      <div>
        <div className="flex space-x-3">
          <h2 className="text-xl font-semibold mb-2">Acme Quote for DUO</h2>
          <FaPen className="cursor-pointer w-3 h-3" />
        </div>
        <div className="w-full flex flex-wrap gap-x-8 gap-y-3 text-sm text-gray-600 mt-6">
          <div className="flex flex-col min-w-[150px] text-lg">
            <span className="text-gray-400">Deal ID:</span> 98432547
          </div>
          <div className="flex flex-col min-w-[150px] text-lg">
            <span className="text-gray-400">Quote Number:</span> 4751837672
          </div>
          <div className="flex flex-col min-w-[180px] text-lg">
            <span className="text-gray-400">Quote Status:</span>{" "}
            <span className="text-yellow-600">⚠ Not Submitted</span>
          </div>
          <div className="flex flex-col min-w-[150px] text-lg">
            <span className="text-gray-400">Expiry Date:</span> Aug 26, 2025
          </div>
          <div className="flex flex-col min-w-[200px] text-lg">
            <span className="text-gray-400">Price Protection Expiry:</span> Jun
            22, 2025
          </div>
          <div className="flex flex-col min-w-[280px] text-lg">
            <span className="text-gray-400">Price List:</span> Global Price List
            in US Availability (USD)
          </div>
        </div>
      </div>
      <div className="relative">
        <button
          className="text-blue-600 hover:text-blue-800 text-sm flex items-center gap-2"
          onClick={() => setShowMenu(!showMenu)}
        >
          More <FaChevronDown className="w-3 h-3" />
        </button>
        {showMenu && (
          <div className="absolute right-0 mt-2 bg-white border border-gray-200 rounded-md shadow-lg w-48 z-10 text-sm">
            <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
              <FaShareAlt /> Share
            </button>
            <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
              <FaPrint /> Print
            </button>
            <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
              <FaEnvelope /> Email
            </button>
            <button className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 w-full">
              <FaTrash /> Delete
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function TabSection({
  activeTab,
  onChange,
}: {
  activeTab: string;
  onChange: (t: string) => void;
}) {
  return (
    <div className="flex gap-6 border-b border-gray-200 px-8 pt-8">
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

function ItemSearchHeader() {
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

export default function QuoteMainView() {
  const [activeTab, setActiveTab] = useState("Items");

  return (
    <main className="bg-[#F9FAFB] w-[80%] py-6">
      <StepHeader currentStep={1} />
      <QuoteHeaderBar />
      <TabSection activeTab={activeTab} onChange={setActiveTab} />
      {activeTab === "Items" && (
        <>
          <ItemSearchHeader />
          <QuotationTable />
        </>
      )}
    </main>
  );
}
