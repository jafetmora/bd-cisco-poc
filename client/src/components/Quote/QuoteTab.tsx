import { useState } from "react";
import { useQuote } from "../../store/useQuote";
import type { Scenario } from "../../types/Quotes";
import QuoteComponent from "./Quote";
import QuoteCompare from "./QuoteCompare";
import type { Quote } from "../../types/Quotes";

interface QuoteTabProps {
  scenarios: Scenario[];
  title: string;
}

export default function QuoteTab({ scenarios: propScenarios, title }: QuoteTabProps) {
  const { applyQuoteUpdate, quoteSession } = useQuote();
  const scenarios = quoteSession?.scenarios ?? propScenarios;
  const [activeIndex, setActiveIndex] = useState(0);
  if (!scenarios || scenarios.length === 0) return null;

  function updateQuote(updatedQuote: Quote, idx: number) {
    if (!quoteSession) return;
    // Update the quote for the correct scenario
    const updatedScenarios = quoteSession.scenarios.map((scenario, i) =>
      i === idx ? { ...scenario, quote: updatedQuote } : scenario
    );
    applyQuoteUpdate({ ...quoteSession, scenarios: updatedScenarios, unsavedChanges: true });
  }

  return (
    <div className="w-full">
      {/* Tab Headers */}
      <div className="flex border-b border-gray-200 mb-4">
        {scenarios.map((scenario, idx) => (
          <button
            key={scenario.id}
            className={`px-5 py-2 -mb-px border-b-2 font-medium transition-colors duration-200 focus:outline-none ${
              idx === activeIndex
                ? "border-primary text-primary bg-white"
                : "border-transparent text-gray-500 hover:text-primary hover:border-primary"
            }`}
            onClick={() => setActiveIndex(idx)}
            type="button"
          >
            {scenario.label}
          </button>
        ))}
        {/* Trade-offs Tab */}
        <button
          className={`px-5 py-2 -mb-px border-b-2 font-medium transition-colors duration-200 focus:outline-none ${
            activeIndex === scenarios.length
              ? "border-primary text-primary bg-white"
              : "border-transparent text-gray-500 hover:text-primary hover:border-primary"
          }`}
          onClick={() => setActiveIndex(scenarios.length)}
          type="button"
        >
          Trade-offs
        </button>
      </div>
      {/* Tab Content */}
      {activeIndex === scenarios.length ? (
        <div>
          <QuoteCompare scenarios={scenarios} title={title} />
        </div>
      ) : (
        <div>
          {scenarios[activeIndex].quote ? (
            <QuoteComponent
              quote={scenarios[activeIndex].quote}
              scenarioLabel={scenarios[activeIndex].label}
              title={title}
              onUpdateQuote={(quote) => updateQuote(quote, activeIndex)}
            />
          ) : (
            <div className="text-gray-400 text-center">
              No quote for this scenario.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
