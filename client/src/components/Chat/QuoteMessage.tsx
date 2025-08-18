interface QuoteMessageProps {
  avatar: string;
  name: string;
  time: string;
  quoteId: string;
  items: { description: string; quantity: number; price: string }[];
  total: string;
  dealId: string;
  quoteStatus: string;
  expiryDate: string;
  priceProtectionExpiry: string;
  priceList: string;
  accent?: boolean;
  align?: "left" | "right";
}

export default function QuoteMessage({
  avatar,
  name,
  time,
  quoteId,
  items,
  total,
  dealId,
  quoteStatus,
  expiryDate,
  priceProtectionExpiry,
  priceList,
  accent = false,
  align = "right",
}: QuoteMessageProps) {
  const isRight = align === "right";
  return (
    <div
      className={`flex gap-3 items-start w-full ${isRight ? "justify-end flex-row-reverse" : ""}`}
    >
      <div
        className={`w-10 h-10 ${accent ? "bg-accent text-white" : "bg-secondary text-accent"} rounded-full flex items-center justify-center border-2 border-accent font-segoe text-lg font-bold`}
      >
        {avatar}
      </div>
      <div className={`flex-1 ${isRight ? "text-right" : ""}`}>
        <div
          className={`bg-white border border-accent rounded-xl px-6 py-4 mb-1 inline-block max-w-[90%] shadow-sm`}
        >
          {/* Header */}
          <div className="flex flex-col gap-1 mb-4">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-accent text-base">
                {name}
              </span>
              <span className="text-xs text-light">
                • {items.reduce((sum, i) => sum + i.quantity, 0)} items
              </span>
              <span className="font-bold text-accent ml-auto text-lg">
                {total}
              </span>
            </div>
          </div>
          {/* Quote details */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1 mb-4 text-xs text-neutral">
            <div>
              <span className="font-semibold text-light">Deal ID:</span>{" "}
              {dealId}
            </div>
            <div>
              <span className="font-semibold text-light">Quote Number:</span>{" "}
              {quoteId}
            </div>
            <div>
              <span className="font-semibold text-light">Quote Status:</span>{" "}
              {quoteStatus}
            </div>
            <div>
              <span className="font-semibold text-light">Expiry Date:</span>{" "}
              {expiryDate}
            </div>
            <div>
              <span className="font-semibold text-light">
                Price Protection Expiry:
              </span>{" "}
              {priceProtectionExpiry}
            </div>
            <div>
              <span className="font-semibold text-light">Price List:</span>{" "}
              {priceList}
            </div>
          </div>
          {/* Items table */}
          <div className="mb-2">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-light">
                  <th className="font-normal pb-1">Description</th>
                  <th className="font-normal pb-1">Qty</th>
                  <th className="font-normal pb-1 text-right">Price</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i}>
                    <td className="py-1 pr-2">{item.description}</td>
                    <td className="py-1 pr-2">{item.quantity}</td>
                    <td className="py-1 text-right">{item.price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between items-center mt-2 border-t border-border pt-2">
            <span className="font-medium text-neutral">Total</span>
            <span className="font-bold text-accent text-lg">{total}</span>
          </div>
        </div>
        <div className={`text-xs text-light ${isRight ? "text-right" : ""}`}>
          {time}
        </div>
      </div>
    </div>
  );
}
