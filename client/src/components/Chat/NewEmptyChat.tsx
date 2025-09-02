import React, { useState, useRef } from "react";
import { getProducts } from "../../services/api";
import type { Product } from "../../types/Product";
import { FiSend } from "react-icons/fi";

interface NewEmptyChatProps {
  onSendText: (text: string) => void | Promise<void>;
}

export default function NewEmptyChat({ onSendText }: NewEmptyChatProps) {
  const [text, setText] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownItems, setDropdownItems] = useState<Product[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [mentionQuery, setMentionQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestions: string[] = [
    "Build a quote with access switch for...",
    "Create a quote with Hypershield subscription with high speed core switch",
    "Show me all renewals coming up in 30 days",
  ];

  const handleClick = async (text: string) => {
    await onSendText(text);
  };

  const handleSend = async () => {
    const value = text.trim();
    if (!value) return;
    setText("");
    setShowDropdown(false);
    await onSendText(value);
  };

  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setText(e.target.value);
    const value = e.target.value;
    const cursorPos = inputRef.current?.selectionStart || 0;
    const textBeforeCursor = value.slice(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");
    if (lastAtIndex !== -1) {
      const textAfterAt = textBeforeCursor.slice(lastAtIndex + 1);
      setMentionQuery(textAfterAt);
      if (!textAfterAt.includes(" ") && textAfterAt.length >= 0) {
        setShowDropdown(true);
        if (textAfterAt.length > 0) {
          try {
            const products = await getProducts(textAfterAt);
            setDropdownItems(products.slice(0, 5));
            setSelectedIndex(-1);
          } catch {
            setDropdownItems([]);
          }
        } else {
          setDropdownItems([]);
        }
      } else {
        setShowDropdown(false);
      }
    } else {
      setShowDropdown(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showDropdown && dropdownItems.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < dropdownItems.length - 1 ? prev + 1 : 0,
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev > 0 ? prev - 1 : dropdownItems.length - 1,
        );
      } else if (e.key === "Enter" && selectedIndex >= 0) {
        e.preventDefault();
        handleSelect(dropdownItems[selectedIndex]);
      } else if (e.key === "Escape") {
        setShowDropdown(false);
        setSelectedIndex(-1);
      }
    }
    if (e.key === "Enter" && !showDropdown) {
      handleSend();
    }
  };

  const handleSelect = (product: Product) => {
    const productText = `${product.sku || `ID-${product.id}`} - ${product.description || product.name || ""}`;
    const beforeMention = text.slice(0, text.lastIndexOf("@"));
    const afterMention = text.slice(
      text.lastIndexOf("@") + mentionQuery.length + 1,
    );
    const newText = `${beforeMention}@${productText} ${afterMention}`;
    setText(newText);
    setShowDropdown(false);
    setSelectedIndex(-1);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 0);
  };

  return (
    <div className="w-full h-full flex flex-col items-center justify-center text-center gap-8 py-10">
      <div className="max-w-2xl px-4">
        <h1 className="text-2xl font-semibold text-slate-800">
          <img src="/image.png" alt="Hero" className="mx-auto block" />
        </h1>
      </div>

      {/* Inline input similar to ChatInputBar, centered and larger */}
      <div className="w-full px-6">
        <div className="max-w-3xl mx-auto bg-white rounded-full shadow flex items-center px-6 py-3">
          <input
            ref={inputRef}
            className="flex-1 min-w-0 w-full bg-transparent text-base placeholder-gray-400 focus:outline-none"
            placeholder="Type..."
            value={text}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
          />
          <button
            onClick={handleSend}
            className="bg-blue-500 hover:bg-blue-600 text-white p-3 rounded-full ml-3"
          >
            <FiSend className="w-6 h-6" />
          </button>
        </div>
        {/* Dropdown de sugestões */}
        {showDropdown && (
          <div className="relative left-1/4 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto z-[9999] w-1/2">
            {dropdownItems.length > 0 ? (
              dropdownItems.map((product, idx) => (
                <div
                  key={product.id}
                  className={`px-4 py-2 cursor-pointer border-b border-gray-100 last:border-b-0 hover:bg-blue-50 ${
                    idx === selectedIndex ? "bg-blue-100" : ""
                  }`}
                  onClick={() => handleSelect(product)}
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
            ) : (
              <div className="px-4 py-2 text-gray-500 text-center text-sm">
                Nenhum produto encontrado
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3 justify-center px-4">
        {suggestions.map((s, i) => (
          <button
            key={i}
            className="bg-white border border-[#BAE6FD] text-[#0369A1] rounded-full px-4 py-2 text-sm shadow-sm hover:bg-[#F0F9FF] transition"
            onClick={() => handleClick(s)}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
