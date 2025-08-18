import { useState } from "react";
import ItemSearchHeader from "./ItemSearchHeader";
import QuoteHeaderBar from "./QuoteHeaderBar";
import StepHeader from "./StepHeader";
import TabSection from "./TabSection";
import QuotationTable from "./QuoteTable";
import type { DisplayMode } from "../../store/DisplayModeContext";

interface QuoteProps {
  quote?: any;
  scenarioLabel?: string;
  title?: string;
  loading?: boolean;
  error?: string | null;
  mode?: DisplayMode;
}

export default function Quote({ quote, scenarioLabel, title, loading = false, error = null, mode }: QuoteProps) {
  const [activeTab, setActiveTab] = useState("Items");

  if (quote !== undefined) {
    if (!quote) return <div className="text-gray-400 text-center">No quote for this scenario.</div>;
    return (
      <main className="bg-[#F9FAFB] w-full py-0">
        {quote.header && <QuoteHeaderBar data={quote.header} title={title} noMargins />}
        <TabSection activeTab={activeTab} onChange={setActiveTab} />
        {activeTab === "Items" && (
          <>
            <ItemSearchHeader />
            <QuotationTable items={quote?.items ?? []} summary={quote?.summary} />
          </>
        )}
      </main>
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

  if (!quote) return <div className="text-gray-400 text-center">No quote for this scenario.</div>;

  return (
    <main className="bg-[#F9FAFB] w-full py-0">
      {/* Display mode for demonstration */}
      <div className="text-xs text-gray-400 text-right pb-1">Mode: {mode}</div>
      <StepHeader currentStep={1} />
      {scenarioLabel && (
        <div className="text-lg font-semibold mb-2 text-primary">{scenarioLabel}</div>
      )}
      {quote.header && <QuoteHeaderBar data={quote.header} noMargins />}
      <TabSection activeTab={activeTab} onChange={setActiveTab} />
      {activeTab === "Items" && (
        <>
          <ItemSearchHeader />
          <QuotationTable items={quote?.items ?? []} summary={quote?.summary} />
        </>
      )}
    </main>
  );
}
