import { useEffect, useMemo, useRef, useState } from "react";
import { FaChevronDown, FaSearch } from "react-icons/fa";
import "./QuoteTable.css";
import type { QuoteLineItem, QuotePricingSummary } from "../../types/Quotes";

type Props = {
  items: QuoteLineItem[];
  summary?: QuotePricingSummary;
  onDelete: (selectedIds: Set<string>) => void;
  onUpdate: (updatedItems: QuoteLineItem[]) => void;
};

export default function QuotationTable({ items, summary, onDelete, onUpdate }: Props) {
  const [editingQtyId, setEditingQtyId] = useState<string | null>(null);
  const [editingQtyValue, setEditingQtyValue] = useState<string>("");

  function handleQtyEditCommit(item: QuoteLineItem) {
    const newQty = parseInt(editingQtyValue, 10);
    if (!isNaN(newQty) && newQty > 0 && newQty !== item.quantity) {
      const updatedItems = items.map((it) =>
        it.id === item.id ? { ...it, quantity: newQty } : it
      );
      onUpdate(updatedItems);
    }
    setEditingQtyId(null);
    setEditingQtyValue("");
  }

  function cancelQtyEdit() {
    setEditingQtyId(null);
    setEditingQtyValue("");
  }
  const [showMenu, setShowMenu] = useState(false);
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

  // Filter items by search
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) =>
      `${i.product} ${i.productCode ?? ""}`.toLowerCase().includes(q)
    );
  }, [items, search]);

  const currency = summary?.currency ?? items[0]?.currency ?? "USD";
  const computedTotal = filteredItems.reduce((acc, it) => acc + it.unitPrice * it.quantity, 0);

  // Checkbox logic
  const allSelected = filteredItems.length > 0 && filteredItems.every((it) => selectedIds.has(it.id));
  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredItems.map((it) => it.id)));
    }
  };
  const toggleSelectOne = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };


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
        <div className="relative flex items-center">
          <input
            type="checkbox"
            className="mr-4 w-4 h-4 accent-blue-600 cursor-pointer"
            checked={allSelected}
            onChange={toggleSelectAll}
            aria-label="Select all products"
          />
          <span className="absolute left-10 top-1/2 -translate-y-1/2">
            <FaSearch className="text-gray-400 w-4 h-4" />
          </span>
          <input
            className="text-sm focus:outline-none placeholder:text-gray-400 rounded-full border border-gray-300 pl-9 pr-2 py-1 bg-white"
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
                <div
                  className="px-4 py-2 hover:bg-gray-100 cursor-pointer"
                  onClick={() => {
                    onDelete(selectedIds);
                    setShowMenu(false);
                  }}
                >
                  Delete
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="px-4 py-2">
        <table className="w-full text-sm text-left">
          <thead className="text-gray-500 bg-white">
            <tr>
              <th className="px-2 py-2 font-medium w-8"></th>
              <th className="px-4 py-2 font-medium">Hardware, Software and Service</th>
              <th className="px-4 py-2 font-medium">Estimated Lead Time</th>
              <th className="px-4 py-2 font-medium">Unit List Price ({currency})</th>
              <th className="px-4 py-2 font-medium">Quantity</th>
              <th className="px-4 py-2 font-medium">Extended List Price</th>
            </tr>
          </thead>
          <tbody className="text-gray-700">
            {filteredItems.map((it) => {
              const rowChanged = changedRowIds.has(it.id);
              const cell = changedCells[it.id] ?? {};
              return (
                <tr
                  key={it.id}
                  className={`border-t border-gray-100 ${rowChanged ? "flash-once" : ""}`}
                >
                  <td className="px-2 py-2 text-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 accent-blue-600 cursor-pointer"
                      checked={selectedIds.has(it.id)}
                      onChange={() => toggleSelectOne(it.id)}
                      aria-label={`Select product ${it.product}`}
                    />
                  </td>
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
                  <td className={`px-4 py-2 ${cell.price ? "flash-once" : ""}`}>
                    {it.unitPrice.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td
                    className={`px-4 py-2 ${cell.qty ? "flash-once" : ""}`}
                    onClick={() => {
                      setEditingQtyId(it.id);
                      setEditingQtyValue(String(it.quantity));
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {editingQtyId === it.id ? (
                      <input
                        type="number"
                        min={1}
                        className="w-16 px-2 py-1 border rounded focus:outline-none hide-arrows"
                        value={editingQtyValue}
                        autoFocus
                        onChange={e => setEditingQtyValue(e.target.value)}
                        onBlur={() => handleQtyEditCommit(it)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') handleQtyEditCommit(it);
                          if (e.key === 'Escape') cancelQtyEdit();
                        }}
                      />
                    ) : (
                      it.quantity
                    )}
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
