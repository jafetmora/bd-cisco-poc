import React, { useState } from "react";

import type { Quote } from "../../types/Quotes";

import type { DisplayMode } from "../../store/DisplayModeContext";

interface QuoteDraftProps {
  quote: Quote;
  scenarioLabel: string;
  setMode?: (mode: DisplayMode) => void;
}

const QuoteDraft: React.FC<QuoteDraftProps> = ({
  quote,
  scenarioLabel,
  setMode,
}) => {
  const [expanded, setExpanded] = useState(true);
  const { header, items, summary } = quote;
  return (
    <div className="w-full flex">
      <div className="flex gap-3 items-start w-full">
        <div className="w-14 h-12 rounded-full flex items-center font-light justify-center text-md text-white bg-gradient-to-br from-[#38BDF8] to-[#0369A1]">
          CC
        </div>
        <div className="bg-white border-2 border-[#38BDF8] rounded-xl shadow-sm px-6 py-5 w-full relative">
          {/* Expand Icon Top Right - OUTSIDE header button */}
          <div className="absolute top-3 right-3 z-10">
            <button
              className="p-2 rounded-full hover:bg-[#E0F2FE] transition-colors"
              title="Expand to detailed view"
              onClick={() => {
                if (setMode) {
                  setMode("detailed");
                }
                setExpanded(true);
              }}
              aria-label="Expand to detailed view"
              type="button"
            >
              {/* Icon: Maximize/Expand (Heroicons style) */}
              <svg
                className="w-5 h-5 text-[#0369A1]"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"
                />
              </svg>
            </button>
          </div>
          {/* Accordion Header */}
          <button
            className="flex items-center gap-3 mb-2 w-full focus:outline-none"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
            aria-controls={`quote-details-${header.quoteNumber}`}
            type="button"
          >
            <div className="flex flex-col flex-1 min-w-0 text-left">
              <span className="font-semibold text-[#0369A1] text-base truncate">
                {header.title}
              </span>
              <span className="text-xs text-gray-400 truncate">
                {scenarioLabel}
              </span>
            </div>
            <span className="px-2 py-1 rounded bg-[#E0F2FE] text-[#0369A1] text-xs font-semibold">
              {header.status}
            </span>
            <svg
              className={`ml-2 w-4 h-4 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
          {/* Accordion Content */}
          {expanded && (
            <div id={`quote-details-${header.quoteNumber}`}>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 mb-4 text-xs text-neutral">
                <div>
                  <span className="font-semibold text-light">Deal ID:</span>{" "}
                  {header.dealId}
                </div>
                <div>
                  <span className="font-semibold text-light">Quote #:</span>{" "}
                  {header.quoteNumber}
                </div>
                <div>
                  <span className="font-semibold text-light">Expiry:</span>{" "}
                  {header.expiryDate}
                </div>
                <div>
                  <span className="font-semibold text-light">Price List:</span>{" "}
                  {header.priceList.name}
                </div>
                {header.priceProtectionExpiry && (
                  <div>
                    <span className="font-semibold text-light">
                      Price Protection:
                    </span>{" "}
                    {header.priceProtectionExpiry}
                  </div>
                )}
              </div>
              <div className="overflow-x-auto mb-2">
                <table className="min-w-[340px] w-full text-xs">
                  <thead>
                    <tr className="text-gray-400 text-xs">
                      <th className="font-normal pb-1 text-left">Product</th>
                      <th className="font-normal pb-1 text-left">Qty</th>
                      <th className="font-normal pb-1 text-right">Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item: (typeof items)[0], i: number) => (
                      <tr key={i}>
                        <td className="py-1 pr-2">{item.product}</td>
                        <td className="py-1 pr-2">{item.quantity}</td>
                        <td className="py-1 text-right">
                          {item.unitPrice.toLocaleString(undefined, {
                            style: "currency",
                            currency: header.priceList.currency,
                          })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-col gap-1 mt-2 border-t border-[#E0F2FE] pt-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Subtotal</span>
                  <span>
                    {summary && summary.subtotal !== undefined
                      ? summary.subtotal.toLocaleString(undefined, {
                          style: "currency",
                          currency: header.priceList.currency,
                        })
                      : ""}
                  </span>
                </div>
                {summary && summary.discount !== undefined && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Discount</span>
                    <span>
                      -
                      {summary.discount.toLocaleString(undefined, {
                        style: "currency",
                        currency: header.priceList.currency,
                      })}
                    </span>
                  </div>
                )}
                {summary && summary.tax !== undefined && (
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Tax</span>
                    <span>
                      {summary.tax.toLocaleString(undefined, {
                        style: "currency",
                        currency: header.priceList.currency,
                      })}
                    </span>
                  </div>
                )}
                <div className="flex justify-between items-center mt-1">
                  <span className="font-medium text-neutral">Total</span>
                  <span className="font-bold text-[#0369A1] text-lg">
                    {summary && summary.total !== undefined
                      ? summary.total.toLocaleString(undefined, {
                          style: "currency",
                          currency: header.priceList.currency,
                        })
                      : ""}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default QuoteDraft;
