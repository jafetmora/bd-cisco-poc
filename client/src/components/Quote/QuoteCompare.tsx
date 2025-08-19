import type {
  Scenario,
  Quote,
  QuoteLineItem,
  LeadTime,
} from "../../types/Quotes";
import QuoteHeaderBar from "./QuoteHeaderBar";

type Props = {
  scenarios: Scenario[];
  className?: string;
  title?: string;
};

function formatCurrency(
  value: number,
  currency: Quote["header"]["priceList"]["currency"],
) {
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

function formatLeadTime(leadTime: LeadTime): string {
  if (!leadTime) return "-";
  if (leadTime.kind === "instant") return "Instant";
  if (leadTime.kind === "na") return "N/A";
  if (leadTime.kind === "days") return `${leadTime.value} days`;
  return "-";
}

function ItemRow({
  item,
  currency,
}: {
  item: QuoteLineItem;
  currency: Quote["header"]["priceList"]["currency"];
}) {
  const total = item.unitPrice * item.quantity;
  return (
    <div className="grid grid-cols-[1fr,auto,auto,auto,auto] gap-3 text-sm py-2 items-center">
      <div className="truncate" title={item.product}>
        <div className="font-medium text-gray-800 truncate">{item.product}</div>
        <div className="text-xs text-gray-400">
          {item.productCode || item.category}
        </div>
      </div>
      <div className="text-gray-600 tabular-nums">{item.quantity}</div>
      <div className="text-gray-600 tabular-nums">
        {formatCurrency(item.unitPrice, currency)}
      </div>
      <div className="text-gray-600 tabular-nums">
        {formatLeadTime(item.leadTime)}
      </div>
      <div className="text-gray-900 font-semibold tabular-nums text-right">
        {formatCurrency(total, currency)}
      </div>
    </div>
  );
}

function ScenarioCard({
  scenario,
  isBest,
  isMost,
}: {
  scenario: Scenario;
  isBest?: boolean;
  isMost?: boolean;
}) {
  const quote = scenario.quote;

  if (!quote) {
    return (
      <div className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">{scenario.label}</h3>
          <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
            No quote
          </span>
        </div>
        <p className="text-sm text-gray-500 mt-2">
          This scenario does not have a generated quote yet.
        </p>
      </div>
    );
  }

  const currency = quote.header.priceList.currency;
  const summary = quote.summary;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm min-w-[320px]">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900 leading-6">
            {scenario.label}
          </h3>
          <p className="text-xs text-gray-500">{quote.header.title}</p>
        </div>
        {summary?.total != null && (
          <div
            className={
              "text-right rounded-md px-2 py-1 " +
              (isBest
                ? "bg-green-50 ring-1 ring-green-200"
                : isMost
                  ? "bg-yellow-50 ring-1 ring-yellow-200"
                  : "")
            }
          >
            <div className="flex items-center justify-end gap-2">
              <div className="text-xs text-gray-500">Total</div>
              {isBest && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">
                  Best Value
                </span>
              )}
              {isMost && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 font-medium">
                  Most Profitable
                </span>
              )}
            </div>
            <div className="text-lg font-semibold text-gray-900 tabular-nums">
              {formatCurrency(summary.total, currency)}
            </div>
          </div>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
          <div className={`rounded-md border border-gray-200 p-2 bg-gray-50`}>
            <div className="text-xs text-gray-500">Subtotal</div>
            <div className="font-medium tabular-nums">
              {formatCurrency(summary.subtotal, currency)}
            </div>
          </div>
          <div className={`rounded-md border border-gray-200 p-2 bg-gray-50`}>
            <div className="text-xs text-gray-500">Discount</div>
            <div className="font-medium tabular-nums">
              {formatCurrency(summary.discount ?? 0, currency)}
            </div>
          </div>
          <div className={`rounded-md border border-gray-200 p-2 bg-gray-50`}>
            <div className="text-xs text-gray-500">Tax</div>
            <div className="font-medium tabular-nums">
              {formatCurrency(summary.tax ?? 0, currency)}
            </div>
          </div>
        </div>
      )}

      {/* Items */}
      <div className="mt-4">
        <div className="grid grid-cols-[1fr,auto,auto,auto,auto] gap-3 text-xs text-gray-500 border-b border-gray-200 pb-2">
          <div>Product</div>
          <div>Qty</div>
          <div>Unit</div>
          <div>Lead Time</div>
          <div className="text-right">Line Total</div>
        </div>
        <div className="divide-y divide-gray-100">
          {quote.items.map((it) => (
            <ItemRow key={it.id} item={it} currency={currency} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function QuoteCompare({ scenarios, className, title }: Props) {
  // Compute cheapest (Best Value) and most expensive (Most Profitable) by summary.total
  const totals = scenarios
    .map((s) => ({ id: s.id, total: s.quote?.summary?.total }))
    .filter(
      (x): x is { id: string; total: number } => typeof x.total === "number",
    );
  const minTotal = totals.length
    ? Math.min(...totals.map((t) => t.total))
    : undefined;
  const maxTotal = totals.length
    ? Math.max(...totals.map((t) => t.total))
    : undefined;
  const bestId = totals.find((t) => t.total === minTotal)?.id;
  const mostId = totals.find((t) => t.total === maxTotal)?.id;
  const firstQuote = scenarios.find((s) => s.quote)?.quote || null;

  return (
    <section className={"w-full " + (className ?? "")}>
      {/* Header Bar (uses first available quote) */}
      {firstQuote && (
        <div className="mb-4 -mx-6">
          <QuoteHeaderBar
            data={firstQuote.header}
            title={title}
          />
        </div>
      )}

      {/* Columns */}
      <div className="overflow-x-auto">
        <div className="grid auto-cols-[minmax(320px,1fr)] grid-flow-col gap-4 px-2">
          {scenarios.map((s) => (
            <ScenarioCard
              key={s.id}
              scenario={s}
              isBest={bestId === s.id}
              isMost={mostId === s.id}
            />
          ))}
        </div>
      </div>

      {/* Empty state */}
      {scenarios.length === 0 && (
        <div className="px-2">
          <div className="rounded-xl border border-dashed border-gray-300 p-6 text-center text-gray-500">
            No scenarios to compare yet.
          </div>
        </div>
      )}
    </section>
  );
}
