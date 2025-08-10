import { useState } from "react";
import { FaChevronDown, FaChevronRight, FaSearch } from "react-icons/fa";

type QuoteItem = {
  category: string;
  product: string;
  leadTime: string;
  unitPrice: number;
  quantity: number;
};

const sampleData: QuoteItem[] = [
  {
    category: "Hardware Wireless",
    product: "AIR-AP2802E-S-K9 802.11ac W2 AP",
    leadTime: "7 days",
    unitPrice: 1716.0,
    quantity: 1,
  },
  {
    category: "Hardware Wireless",
    product: "CAB-SS-RJ45 RJ45 Cable to Smart Serial, 10 Feet",
    leadTime: "5 days",
    unitPrice: 55.0,
    quantity: 2,
  },
  {
    category: "Software Wireless",
    product: "WIC-1B-S/T-V3 1-Port ISDN WAN Interface Card",
    leadTime: "N/A",
    unitPrice: 600.0,
    quantity: 1,
  },
  {
    category: "Software Wireless",
    product: "EDU-DNA-A-3Y DNA Advantage Term License - 3Y",
    leadTime: "Instant",
    unitPrice: 540.0,
    quantity: 3,
  },
  {
    category: "Hardware Wireless",
    product: "PS-SWITCH-AC-3P Power Supply Switch",
    leadTime: "10 days",
    unitPrice: 50.0,
    quantity: 5,
  },
  {
    category: "Software Wireless",
    product: "EDU-DNA-E-7Y DNA Essential Term License - 7Y",
    leadTime: "Instant",
    unitPrice: 473.0,
    quantity: 2,
  },
];

export default function QuotationTable() {
  const [showMenu, setShowMenu] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<
    Record<string, boolean>
  >({});
  const [search, setSearch] = useState("");

  const grouped = sampleData.reduce(
    (acc, item) => {
      if (!acc[item.category]) acc[item.category] = [];
      acc[item.category].push(item);
      return acc;
    },
    {} as Record<string, QuoteItem[]>,
  );

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [category]: !prev[category],
    }));
  };

  const filteredGrouped = Object.entries(grouped)
    .map(([category, items]) => {
      const filteredItems = items.filter((item) =>
        item.product.toLowerCase().includes(search.toLowerCase()),
      );
      return [category, filteredItems] as [string, QuoteItem[]];
    })
    .filter(([, items]) => items.length > 0);

  const total = filteredGrouped
    .flatMap(([, items]) => items)
    .reduce((acc, item) => acc + item.unitPrice * item.quantity, 0);

  return (
    <div className="bg-white mx-8 mt-4 rounded-xl shadow border border-gray-200">
      {/* Top Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <FaSearch className="text-gray-400 w-4 h-4" />
          <input
            className="text-sm focus:outline-none placeholder:text-gray-400"
            placeholder="Search Quote Line Items"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-6 text-sm text-blue-600">
          <button>Apply Success Track</button>
          <button>Validate</button>
          <div className="relative">
            <button
              onClick={() => setShowMenu((prev) => !prev)}
              className="flex items-center gap-1"
            >
              More Action <FaChevronDown className="w-3 h-3" />
            </button>
            {showMenu && (
              <div className="absolute right-0 mt-2 bg-white shadow border border-gray-200 rounded-md text-sm z-10 w-44">
                <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
                  Action A
                </div>
                <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
                  Action B
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="px-4 py-2">
        {filteredGrouped.map(([category, items]) => (
          <div
            key={category}
            className="mb-4 border rounded-md border-gray-200"
          >
            <button
              onClick={() => toggleCategory(category)}
              className="w-full flex justify-between items-center bg-gray-50 px-4 py-2 text-left font-medium text-gray-700 hover:bg-gray-100"
            >
              <span>{category}</span>
              {expandedCategories[category] ? (
                <FaChevronDown />
              ) : (
                <FaChevronRight />
              )}
            </button>
            {expandedCategories[category] && (
              <table className="w-full text-sm text-left border-t border-gray-100">
                <thead className="text-gray-500 bg-white">
                  <tr>
                    <th className="px-4 py-2 font-medium">Product</th>
                    <th className="px-4 py-2 font-medium">
                      Estimated Lead Time
                    </th>
                    <th className="px-4 py-2 font-medium">
                      Unit List Price (USD)
                    </th>
                    <th className="px-4 py-2 font-medium">Quantity</th>
                    <th className="px-4 py-2 font-medium">
                      Extended List Price
                    </th>
                  </tr>
                </thead>
                <tbody className="text-gray-700">
                  {items.map((item, idx) => (
                    <tr key={idx} className="border-t border-gray-100">
                      <td className="px-4 py-2">{item.product}</td>
                      <td className="px-4 py-2">{item.leadTime}</td>
                      <td className="px-4 py-2">
                        ${item.unitPrice.toFixed(2)}
                      </td>
                      <td className="px-4 py-2">{item.quantity}</td>
                      <td className="px-4 py-2">
                        ${(item.unitPrice * item.quantity).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      {/* Total */}
      <div className="flex justify-end px-4 py-4 border-t border-gray-100 bg-gray-50 rounded-b-xl">
        <div className="text-right">
          <div className="text-gray-500 text-sm">Total</div>
          <div className="text-blue-700 text-2xl font-bold">
            ${total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>
    </div>
  );
}
