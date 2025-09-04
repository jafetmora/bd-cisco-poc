import { useState /*type ChangeEvent*/ } from "react";
//import { getProducts } from "../../services/api";
import type { Product } from "../../types/Product";
import { FaChevronDown, FaFileImport, FaSearch } from "react-icons/fa";

type ItemSearchHeaderProps = {
  onProductSelect?: (product: Product) => void;
};

export default function ItemSearchHeader({
  onProductSelect,
}: ItemSearchHeaderProps) {
  const [showPreferences, setShowPreferences] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);

  /*
  async function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setQuery(val);
    if (val.trim().length > 1) {
      const products = await getProducts(val);
      setResults(products);
    } else {
      setResults([]);
    }
  }
  */

  function handleProductSelect(product: Product) {
    if (onProductSelect) onProductSelect(product);
    setQuery("");
    setResults([]);
  }

  return (
    <div className="bg-gray-100 mt-3 mx-8 rounded-md p-4 flex flex-wrap md:flex-nowrap items-center justify-between gap-8">
      <div className="relative flex-1">
        <div
          className={`relative bg-white rounded-full border border-gray-300 transition-all duration-300 ${isFocused ? "ring-2 ring-blue-300 shadow-md" : ""}`}
        >
          <FaSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 w-4 h-4 pointer-events-none" />
          <input
            type="text"
            placeholder="Add items by SKU, Description, or Category"
            className="bg-transparent w-full text-xl placeholder-gray-400 focus:outline-none rounded-full pl-10 pr-4 py-2"
            onFocus={() => setIsFocused(true)}
            onBlur={() => setTimeout(() => setIsFocused(false), 200)}
            value={query}
            //onChange={handleInputChange}
          />
          {isFocused && results.length > 0 && (
            <ul className="absolute z-10 left-0 right-0 top-full bg-white border border-gray-200 rounded shadow mt-1 max-h-60 overflow-y-auto">
              {results.map((product: Product, idx: number) => (
                <li
                  key={`${product.id ?? product.sku ?? product.description ?? idx}`}
                  className="px-4 py-2 hover:bg-blue-100 cursor-pointer"
                  onClick={() => handleProductSelect(product)}
                >
                  <span className="font-semibold">
                    {product.sku ?? `ID-${product.id}`}
                  </span>{" "}
                  - {product.description ?? product.name ?? ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <label className="text-blue-600 text-md cursor-pointer flex items-center gap-2 whitespace-nowrap">
        <FaFileImport className="w-4 h-4" />
        <input type="file" className="hidden" />
        Import Quote
      </label>
      <div className="relative">
        <button
          className="text-md text-blue-600 flex items-center gap-2 whitespace-nowrap"
          onClick={() => setShowPreferences((prev: boolean) => !prev)}
        >
          Quote Preferences <FaChevronDown className="w-3 h-3" />
        </button>
        {showPreferences && (
          <div className="absolute right-0 mt-2 w-52 bg-white shadow border border-gray-200 rounded-md z-10 text-md">
            <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
              Preference A
            </div>
            <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
              Preference B
            </div>
            <div className="px-4 py-2 hover:bg-gray-100 cursor-pointer">
              Preference C
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
