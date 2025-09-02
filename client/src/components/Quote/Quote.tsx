import { useEffect, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import ItemSearchHeader from "./ItemSearchHeader";
import QuoteHeaderBar from "./QuoteHeaderBar";
import StepHeader from "./StepHeader";
import TabSection from "./TabSection";
import QuotationTable from "./QuoteTable";
import type { DisplayMode } from "../../store/DisplayModeContext";
import type {
  Quote as QuoteType,
  QuotePricingSummary,
} from "../../types/Quotes";
import type { Product } from "../../types/Product";
import type { QuoteLineItem } from "../../types/Quotes";

interface QuoteProps {
  quote?: QuoteType | null;
  scenarioLabel?: string;
  title?: string;
  loading?: boolean;
  error?: string | null;
  mode?: DisplayMode;
  onUpdateQuote?: (quote: QuoteType) => void;
}
export default function Quote({
  quote,
  scenarioLabel,
  title,
  loading = false,
  error = null,
  mode,
  onUpdateQuote,
}: QuoteProps) {
  const [activeTab, setActiveTab] = useState("Items");
  const [items, setItems] = useState<QuoteLineItem[]>(quote?.items ?? []);

  // Sync items state with quote prop whenever quote changes (e.g. tab switch)
  useEffect(() => {
    setItems(quote?.items ?? []);
  }, [quote]);

  function recalculateSummary(items: QuoteLineItem[]): QuotePricingSummary {
    const subtotal = items.reduce(
      (acc, it) => acc + it.unitPrice * it.quantity,
      0,
    );
    return {
      currency: (items[0]?.currency ??
        "USD") as import("../../types/Quotes").CurrencyCode,
      subtotal,
      total: subtotal,
    };
  }

  function addProductToQuote(product: Product) {
    if (!quote || !onUpdateQuote) return;
    const prev = quote.items ?? [];
    const productCode = product.sku ?? `ID-${product.id}`;
    const existingIdx = prev.findIndex(
      (item) => item.productCode === productCode,
    );
    let updatedItems;
    if (existingIdx !== -1) {
      // Increment quantity if SKU exists
      updatedItems = prev.map((item, idx) =>
        idx === existingIdx ? { ...item, quantity: item.quantity + 1 } : item,
      );
    } else {
      // Add new item
      const newItem: QuoteLineItem = {
        id: uuidv4(),
        category: product.category ?? "Unknown",
        productCode: productCode,
        product: product.description ?? product.name ?? "",
        leadTime: { kind: "na" },
        unitPrice: product.price,
        quantity: 1,
        currency: "USD",
      };
      updatedItems = [...prev, newItem];
    }
    const summary = recalculateSummary(updatedItems);
    onUpdateQuote({ ...quote, items: updatedItems, summary });
  }

  function updateProductsFromQuote(updatedItems: QuoteLineItem[]) {
    if (!quote || !onUpdateQuote) return;
    const summary = recalculateSummary(updatedItems);
    onUpdateQuote({ ...quote, items: updatedItems, summary });
  }

  function deleteProductsFromQuote(selectedIds: Set<string>) {
    if (!quote || !onUpdateQuote) return;
    const prev = quote.items ?? [];
    const updatedItems = prev.filter((item) => !selectedIds.has(item.id));
    const summary = recalculateSummary(updatedItems);
    onUpdateQuote({ ...quote, items: updatedItems, summary });
  }

  if (quote !== undefined) {
    if (!quote)
      return (
        <div className="text-gray-400 text-center">
          No quote for this scenario.
        </div>
      );
    return (
      <section className="w-full">
        {quote.header && (
          <div className="mb-4 -mx-6">
            <QuoteHeaderBar data={quote.header} title={title} />
          </div>
        )}
        <div className="-mx-6">
          <TabSection activeTab={activeTab} onChange={setActiveTab} />
          {activeTab === "Items" && (
            <>
              <ItemSearchHeader onProductSelect={addProductToQuote} />
              <QuotationTable
                items={items}
                summary={quote?.summary}
                onDelete={deleteProductsFromQuote}
                onUpdate={updateProductsFromQuote}
              />
            </>
          )}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <main className="bg-[#F9FAFB] w-full py-0">
        <StepHeader currentStep={1} />
        <div className="mx-8 mt-6 text-red-600">Error: {error}</div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="bg-[#F9FAFB] w-full py-0">
        <StepHeader currentStep={1} />
        <div className="mx-8 mt-6 text-gray-500">Loading quote…</div>
      </main>
    );
  }

  if (!quote)
    return (
      <div className="text-gray-400 text-center">
        No quote for this scenario.
      </div>
    );

  // From here on, `quote` is definitely a QuoteType
  const q: QuoteType = quote as QuoteType;

  return (
    <main className="bg-[#F9FAFB] w-full py-0">
      {/* Display mode for demonstration */}
      <div className="text-xs text-gray-400 text-right pb-1">Mode: {mode}</div>
      <StepHeader currentStep={1} />
      {scenarioLabel && (
        <div className="text-lg font-semibold mb-2 text-primary">
          {scenarioLabel}
        </div>
      )}
      {q.header && <QuoteHeaderBar data={q.header} noMargins />}
      <TabSection activeTab={activeTab} onChange={setActiveTab} />
      {activeTab === "Items" && (
        <>
          <ItemSearchHeader onProductSelect={addProductToQuote} />
          <QuotationTable
            items={items}
            summary={q.summary}
            onDelete={deleteProductsFromQuote}
            onUpdate={updateProductsFromQuote}
          />
        </>
      )}
    </main>
  );
}
