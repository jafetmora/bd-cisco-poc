import { useState } from "react";
import ItemSearchHeader from "./ItemSearchHeader";
import QuoteHeaderBar from "./QuoteHeaderBar";
import StepHeader from "./StepHeader";
import TabSection from "./TabSection";
import QuotationTable from "./QuoteTable";
import type { DisplayMode } from "../../store/DisplayModeContext";
import type { Quote as QuoteType } from "../../types/Quotes";

interface QuoteProps {
  quote?: QuoteType | null;
  scenarioLabel?: string;
  title?: string;
  loading?: boolean;
  error?: string | null;
  mode?: DisplayMode;
}

function formatCurrency(value: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency} ${value.toFixed(2)}`;
  }
}

export default function Quote({
  quote,
  title,
  loading = false,
  error = null,
}: QuoteProps) {
  const [activeTab, setActiveTab] = useState("Items");

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
              <ItemSearchHeader />
              <QuotationTable
                items={quote?.items ?? []}
                summary={quote?.summary}
              />
            </>
          )}
          {activeTab === "Discounts & Credits" && (
            <div className="relative bg-white mx-8 mt-4 rounded-xl shadow border border-gray-200">
              <div className="p-4">
                {quote?.summary?.discount !== undefined &&
                quote.header?.priceList?.currency ? (
                  <div className="flex justify-start">
                    <div className="w-full max-w-md">
                      <div className="border-t border-gray-100 bg-gray-50 rounded-b-xl px-4 py-4">
                        <div className="flex flex-col items-start">
                          <div className="text-gray-500 text-sm">
                            Total Discount
                          </div>
                          <div className="text-blue-700 text-2xl font-bold tabular-nums">
                            {formatCurrency(
                              quote.summary.discount ?? 0,
                              quote.header.priceList.currency,
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-gray-400">No discounts available.</div>
                )}
              </div>
            </div>
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
}
