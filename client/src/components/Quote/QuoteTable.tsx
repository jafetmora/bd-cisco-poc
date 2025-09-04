import { useEffect, useMemo, useRef, useState } from "react";
import { FaChevronDown, FaChevronRight, FaSearch } from "react-icons/fa";
import type { QuoteLineItem, QuotePricingSummary } from "../../types/Quotes";

type Props = {
  items: QuoteLineItem[];
  summary?: QuotePricingSummary;
};

export default function QuotationTable({ items, summary }: Props) {
  const [showMenu, setShowMenu] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState<
    Record<string, boolean>
  >({});
  const [search, setSearch] = useState("");
  const [showSweep, setShowSweep] = useState(false);
  const prevItemsRef = useRef<QuoteLineItem[] | null>(null);
  const prevSummaryRef = useRef<QuotePricingSummary | null>(null);
  const [changedRowIds, setChangedRowIds] = useState<Set<string>>(new Set());
  const [changedCells, setChangedCells] = useState<
    Record<string, { price?: boolean; qty?: boolean }>
  >({});
  const [totalFlash, setTotalFlash] = useState(false);

  useEffect(() => {
    const prev = prevItemsRef.current;
    if (prev) {
      const byIdPrev = new Map(prev.map((i) => [i.id, i]));
      const changedRows = new Set<string>();
      const cellChanges: Record<string, { price?: boolean; qty?: boolean }> =
        {};

      for (const it of items) {
        const p = byIdPrev.get(it.id);
        if (!p) {
          changedRows.add(it.id);
          cellChanges[it.id] = { price: true, qty: true };
          continue;
        }
        const priceChanged =
          p.unitPrice !== it.unitPrice || p.currency !== it.currency;
        const qtyChanged = p.quantity !== it.quantity;
        if (priceChanged || qtyChanged) {
          changedRows.add(it.id);
          cellChanges[it.id] = {
            price: priceChanged || undefined,
            qty: qtyChanged || undefined,
          };
        }
      }
      setChangedRowIds(changedRows);
      setChangedCells(cellChanges);

      if (changedRows.size > 0) {
        setShowSweep(true);
        const t = setTimeout(() => setShowSweep(false), 850);
        return () => clearTimeout(t);
      }
    }
    prevItemsRef.current = items;
  }, [items]);

  useEffect(() => {
    prevItemsRef.current = items;
  }, [showSweep, items]);

  useEffect(() => {
    const prev = prevSummaryRef.current;
    const totalNow = summary?.total;
    const totalPrev = prev?.total;
    if (
      typeof totalNow === "number" &&
      typeof totalPrev === "number" &&
      totalNow !== totalPrev
    ) {
      setTotalFlash(true);
      const t = setTimeout(() => setTotalFlash(false), 1200);
      return () => clearTimeout(t);
    }
    prevSummaryRef.current = summary ?? null;
  }, [summary]);

  const grouped = useMemo(() => {
    const g: Record<string, QuoteLineItem[]> = {};
    for (const it of items) {
      if (!g[it.category]) g[it.category] = [];
      g[it.category].push(it);
    }
    return g;
  }, [items]);

  const toggleCategory = (c: string) =>
    setExpandedCategories((prev) => ({ ...prev, [c]: !prev[c] }));

  const filteredGrouped = Object.entries(grouped)
    .map(([category, its]) => {
      const q = search.trim().toLowerCase();
      const filtered = q
        ? its.filter((i) =>
            `${i.product} ${i.productCode ?? ""}`.toLowerCase().includes(q),
          )
        : its;
      return [category, filtered] as [string, QuoteLineItem[]];
    })
    .filter(([, its]) => its.length > 0);

  const currency = summary?.currency ?? items[0]?.currency ?? "USD";
  const computedTotal = filteredGrouped
    .flatMap(([, its]) => its)
    .reduce((acc, it) => acc + it.unitPrice * it.quantity, 0);

  const displayLead = (lt: QuoteLineItem["leadTime"]) =>
    lt.kind === "instant"
      ? "Instant"
      : lt.kind === "na"
        ? "N/A"
        : `${lt.value} days`;

  return (
    <div className="relative bg-white mx-8 mt-4 rounded-xl shadow border border-gray-200">
      {showSweep && <div className="sweep-overlay" />}

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
              onClick={() => setShowMenu((p) => !p)}
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
        {filteredGrouped.map(([category, its]) => (
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
                      Unit List Price ({currency})
                    </th>
                    <th className="px-4 py-2 font-medium">Quantity</th>
                    <th className="px-4 py-2 font-medium">
                      Extended List Price
                    </th>
                  </tr>
                </thead>
                <tbody className="text-gray-700">
                  {its.map((it) => {
                    const rowChanged = changedRowIds.has(it.id);
                    const cell = changedCells[it.id] ?? {};
                    return (
                      <tr
                        key={it.id}
                        className={`border-t border-gray-100 ${rowChanged ? "flash-once" : ""}`}
                      >
                        <td className="px-4 py-2">
                          {it.product}
                          {it.productCode ? (
                            <span className="text-gray-400 ml-1">
                              ({it.productCode})
                            </span>
                          ) : null}
                        </td>
                        <td className="px-4 py-2">
                          {displayLead(it.leadTime)}
                        </td>
                        <td
                          className={`px-4 py-2 ${cell.price ? "flash-once" : ""}`}
                        >
                          {it.unitPrice.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })}
                        </td>
                        <td
                          className={`px-4 py-2 ${cell.qty ? "flash-once" : ""}`}
                        >
                          {it.quantity}
                        </td>
                        <td className="px-4 py-2">
                          {(it.unitPrice * it.quantity).toLocaleString(
                            undefined,
                            { minimumFractionDigits: 2 },
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      {/* Total */}
      <div className="flex justify-end px-4 py-4 border-t border-gray-100 bg-gray-50 rounded-b-xl">
        <div className={`text-right ${totalFlash ? "flash-once" : ""}`}>
          <div className="text-gray-500 text-sm">Total</div>
          <div className="text-blue-700 text-2xl font-bold">
            {(summary?.total ?? computedTotal).toLocaleString(undefined, {
              minimumFractionDigits: 2,
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
