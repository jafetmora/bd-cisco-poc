import type { QuotePayload } from "../types/Quotes";
import { mockSocket } from "./mockSocket";

export async function getMockQuote(): Promise<QuotePayload> {
  await new Promise((r) => setTimeout(r, 300));
  return {
    header: {
      title: "Acme Quote for DUO",
      dealId: "98432547",
      quoteNumber: "4751837672",
      status: "NOT_SUBMITTED",
      expiryDate: "2025-08-26",
      priceProtectionExpiry: "2025-06-22",
      priceList: { name: "Global Price List", region: "US", currency: "USD" },
    },
    items: [
      {
        id: "L1",
        category: "Hardware Wireless",
        product: "AIR-AP2802E-S-K9 802.11ac W2 AP",
        productCode: "AIR-AP2802E-S-K9",
        leadTime: { kind: "days", value: 7 },
        unitPrice: 1716.0,
        quantity: 1,
        currency: "USD",
      },
      {
        id: "L2",
        category: "Hardware Wireless",
        product: "CAB-SS-RJ45 RJ45 Cable to Smart Serial, 10 Feet",
        productCode: "CAB-SS-RJ45",
        leadTime: { kind: "days", value: 5 },
        unitPrice: 55.0,
        quantity: 2,
        currency: "USD",
      },
      {
        id: "L3",
        category: "Software Wireless",
        product: "WIC-1B-S/T-V3 1-Port ISDN WAN Interface Card",
        productCode: "WIC-1B-S/T-V3",
        leadTime: { kind: "na" },
        unitPrice: 600.0,
        quantity: 1,
        currency: "USD",
      },
      {
        id: "L4",
        category: "Software Wireless",
        product: "EDU-DNA-A-3Y DNA Advantage Term License - 3Y",
        productCode: "EDU-DNA-A-3Y",
        leadTime: { kind: "instant" },
        unitPrice: 540.0,
        quantity: 3,
        currency: "USD",
      },
    ],
    summary: {
      currency: "USD",
      subtotal: 1716 + 55 * 2 + 600 + 540 * 3,
      tax: 0,
      discount: 0,
      total: 1716 + 55 * 2 + 600 + 540 * 3,
    },
  };
}

export async function sendNlpMessage(
  text: string,
): Promise<{ chatReply: string; traceId: string }> {
  await new Promise((r) => setTimeout(r, 250));
  const traceId = crypto?.randomUUID?.() ?? `${Date.now()}`;

  setTimeout(async () => {
    const current = await getMockQuote();
    const updated: QuotePayload = {
      ...current,
      items: current.items.map((i) =>
        i.id === "L1" && /add\s+1\s+ap/i.test(text)
          ? { ...i, quantity: i.quantity + 1 }
          : i,
      ),
    };
    updated.summary = {
      currency: "USD",
      subtotal: updated.items.reduce(
        (acc, it) => acc + it.unitPrice * it.quantity,
        0,
      ),
      total: updated.items.reduce(
        (acc, it) => acc + it.unitPrice * it.quantity,
        0,
      ),
      tax: 0,
      discount: 0,
    };

    mockSocket.emit("QUOTE_UPDATED", updated);
  }, 700);

  return {
    chatReply: "Processed: updated quote based on your request.",
    traceId,
  };
}
