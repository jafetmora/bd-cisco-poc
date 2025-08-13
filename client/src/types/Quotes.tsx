export type CurrencyCode = "USD" | "EUR" | "CRC";

export type QuoteStatus =
  | "NOT_SUBMITTED"
  | "DRAFT"
  | "SUBMITTED"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED";

export type LeadTime =
  | { kind: "instant" }
  | { kind: "na" }
  | { kind: "days"; value: number };

export interface QuoteHeaderData {
  title: string;
  dealId: string;
  quoteNumber: string;
  status: QuoteStatus;
  expiryDate: string;
  priceProtectionExpiry?: string | null;

  priceList: {
    name: string;
    region: string;
    currency: CurrencyCode;
  };
}

export interface QuoteLineItem {
  id: string;
  category: string;
  productCode?: string;
  product: string;
  leadTime: LeadTime;
  unitPrice: number;
  quantity: number;
  currency: CurrencyCode;
}

export interface QuotePricingSummary {
  currency: CurrencyCode;
  subtotal: number;
  tax?: number;
  discount?: number;
  total: number;
}

export interface QuotePayload {
  header: QuoteHeaderData;
  items: QuoteLineItem[];
  summary?: QuotePricingSummary;
  traceId?: string;
}
