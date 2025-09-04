import React, { useState, useEffect, useRef } from "react";
import { FiSend, FiPaperclip } from "react-icons/fi";
import { getProducts } from "../../services/api";
import type { Product } from "../../types/Product";

interface ChatInputBarProps {
  onSendText: (text: string) => void | Promise<void>;
}

export default function ChatInputBar({ onSendText }: ChatInputBarProps) {
  const [text, setText] = useState("");
  const [showProductDropdown, setShowProductDropdown] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductIndex, setSelectedProductIndex] = useState(-1);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionStartPos, setMentionStartPos] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  // Detect @ mentions and fetch products
  useEffect(() => {
    const detectMention = () => {
      const cursorPos = inputRef.current?.selectionStart || 0;
      const textBeforeCursor = text.slice(0, cursorPos);
      const lastAtIndex = textBeforeCursor.lastIndexOf("@");

      if (lastAtIndex !== -1) {
        const textAfterAt = textBeforeCursor.slice(lastAtIndex + 1);
        // Check if there's no space after @ (still typing the mention)
        if (!textAfterAt.includes(" ") && textAfterAt.length >= 0) {
          setMentionStartPos(lastAtIndex);
          setMentionQuery(textAfterAt);
          setShowProductDropdown(true);

          // Fetch products if query has at least 1 character
          if (textAfterAt.length > 0) {
            fetchProducts(textAfterAt);
          } else {
            setProducts([]);
          }
        } else {
          setShowProductDropdown(false);
        }
      } else {
        setShowProductDropdown(false);
      }
    };

    detectMention();
  }, [text]);

  const fetchProducts = async (query: string) => {
    try {
      const results = await getProducts(query);
      setProducts(results.slice(0, 5)); // Limit to 5 results
      setSelectedProductIndex(-1);
    } catch (error) {
      console.error("Error fetching products:", error);
      setProducts([]);
    }
  };

  const handleProductSelect = (product: Product) => {
    const productText = `${product.sku || `ID-${product.id}`} - ${product.description || product.name || ""}`;
    const beforeMention = text.slice(0, mentionStartPos);
    const afterMention = text.slice(mentionStartPos + mentionQuery.length + 1);
    const newText = `${beforeMention}@${productText} ${afterMention}`;

    setText(newText);
    setShowProductDropdown(false);
    setSelectedProductIndex(-1);

    // Focus back to input
    setTimeout(() => {
      inputRef.current?.focus();
      const newCursorPos = beforeMention.length + productText.length + 2;
      inputRef.current?.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showProductDropdown && products.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedProductIndex((prev: number) =>
          prev < products.length - 1 ? prev + 1 : 0,
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedProductIndex((prev: number) =>
          prev > 0 ? prev - 1 : products.length - 1,
        );
      } else if (e.key === "Enter" && selectedProductIndex >= 0) {
        e.preventDefault();
        handleProductSelect(products[selectedProductIndex]);
        return;
      } else if (e.key === "Escape") {
        setShowProductDropdown(false);
        setSelectedProductIndex(-1);
      }
    }

    if (e.key === "Enter" && !showProductDropdown) {
      handleSend();
    }
  };

  const handleSend = async () => {
    const value = text.trim();
    if (!value) return;
    setText("");
    setShowProductDropdown(false);
    await onSendText(value);
  };

  return (
    <div className="bg-[#E0F2FE] pt-5 px-5 pb-5 relative">
      <div className="bg-white rounded-full shadow flex justify-center items-center px-4 py-2">
        <input
          ref={inputRef}
          className="flex-1 min-w-0 w-full bg-transparent text-sm placeholder-gray-400 focus:outline-none"
          placeholder="Type... (use @ to mention products)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <label className="text-blue-600 text-md cursor-pointer flex items-center gap-2 whitespace-nowrap">
          <FiPaperclip className="w-5 h-5 text-gray-500 mx-2 cursor-pointer" />
          <input type="file" className="hidden" />
        </label>
        <button
          onClick={handleSend}
          className="bg-blue-500 hover:bg-blue-600 text-white p-2 rounded-full ml-2"
        >
          <FiSend className="w-5 h-5" />
        </button>
      </div>

      {/* Product dropdown */}
      {showProductDropdown && (
        <div
          className="absolute bottom-12 left-1/2 transform -translate-x-1/2 mb-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto z-[9999]"
          style={{ width: "80%" }}
        >
          {products.length > 0 ? (
            products.map((product, index) => (
              <div
                key={product.id}
                className={`px-4 py-2 cursor-pointer border-b border-gray-100 last:border-b-0 hover:bg-blue-50 ${
                  index === selectedProductIndex ? "bg-blue-100" : ""
                }`}
                onClick={() => handleProductSelect(product)}
              >
                <div className="text-xs text-gray-500 mb-1">
                  {product.category && (
                    <span className="text-blue-600 font-medium mr-2">
                      {product.category}
                    </span>
                  )}
                  {product.sku || `ID-${product.id}`}
                </div>
                <div className="text-sm text-gray-800 font-medium">
                  {product.description || product.name || "No description"}
                </div>
              </div>
            ))
          ) : mentionQuery.length > 0 ? (
            <div className="px-4 py-2 text-gray-500 text-center text-sm">
              No products found for "{mentionQuery}"
            </div>
          ) : (
            <div className="px-4 py-2 text-gray-500 text-center text-sm">
              Type to search products...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
