import { useState } from "react";
import ItemSearchHeader from "./ItemSearchHeader";
import QuoteHeaderBar from "./QuoteHeaderBar";
import StepHeader from "./StepHeader";
import TabSection from "./TabSection";
import QuotationTable from "./QuoteTable";
import { useQuote } from "../../../store/useQuote";

export default function QuoteMainView() {
  const [activeTab, setActiveTab] = useState("Items");
  const { quoteSession, loading, error } = useQuote();

  if (error) {
    return (
      <main className="bg-[#F9FAFB] w-[80%] py-6">
        <StepHeader currentStep={1} />
        <div className="mx-8 mt-6 text-red-600">Error: {error}</div>
      </main>
    );
  }

  if (loading || !quoteSession) {
    return (
      <main className="bg-[#F9FAFB] w-[80%] py-6">
        <StepHeader currentStep={1} />
        <div className="mx-8 mt-6 text-gray-500">Loading quote…</div>
      </main>
    );
  }

  const quote = quoteSession.scenarios[0].quote;
  return (
    <main className="bg-[#F9FAFB] w-[80%] py-6">
      <StepHeader currentStep={1} />
      {quote?.header && <QuoteHeaderBar data={quote.header} />}
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
