export interface Product {
  id: number;
  name?: string | null;
  sku?: string | null;
  product_type?: string | null; // corresponds to DB column "type"
  category?: string | null;
  price: number;
  description?: string | null;
  partner_discount?: number | null;
}
