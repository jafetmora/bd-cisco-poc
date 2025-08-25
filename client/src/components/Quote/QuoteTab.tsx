import { useState } from "react";
import type { Scenario } from "../../types/Quotes";
import Quote from "./Quote";
import QuoteCompare from "./QuoteCompare";

interface QuoteTabProps {
  scenarios: Scenario[];
  title: string;
}

export default function QuoteTab({ scenarios, title }: QuoteTabProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  if (!scenarios || scenarios.length === 0) return null;

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
            <Quote
              quote={scenarios[activeIndex].quote}
              scenarioLabel={scenarios[activeIndex].label}
              title={title}
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
