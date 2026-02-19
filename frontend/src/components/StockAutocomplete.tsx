"use client";

import { useState, useRef, useEffect } from "react";
import { useStockSearch, StockResult } from "@/lib/useStockSearch";

interface StockAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onSelect: (stock: StockResult) => void;
  placeholder?: string;
  market?: string;
  className?: string;
}

export function StockAutocomplete({
  value,
  onChange,
  onSelect,
  placeholder = "종목코드 또는 종목명",
  market = "kr",
  className = "",
}: StockAutocompleteProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const { results, loading } = useStockSearch(searchText, market);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (results.length > 0 && searchText.trim().length > 0) {
      setIsOpen(true);
    }
  }, [results, searchText]);

  const handleInputChange = (val: string) => {
    setSearchText(val);
    onChange(val);
  };

  const handleSelect = (stock: StockResult) => {
    onChange(stock.code);
    setSearchText(`${stock.name} (${stock.code})`);
    onSelect(stock);
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text"
        value={searchText || value}
        onChange={(e) => handleInputChange(e.target.value)}
        onFocus={() => results.length > 0 && setIsOpen(true)}
        placeholder={placeholder}
        className={`w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500 ${className}`}
      />
      {loading && (
        <div className="absolute right-3 top-3.5">
          <div className="w-4 h-4 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin" />
        </div>
      )}

      {isOpen && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-64 overflow-y-auto">
          {results.map((stock) => (
            <button
              key={stock.code}
              onClick={() => handleSelect(stock)}
              type="button"
              className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-gray-700 transition-colors text-left first:rounded-t-lg last:rounded-b-lg"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">
                  {stock.name}
                </span>
                <span className="text-xs text-gray-500">{stock.code}</span>
              </div>
              <div className="flex items-center gap-2">
                {stock.sector && (
                  <span className="text-xs text-gray-600">{stock.sector}</span>
                )}
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${
                    stock.market === "KOSPI"
                      ? "bg-blue-500/20 text-blue-300"
                      : stock.market === "KOSDAQ"
                        ? "bg-purple-500/20 text-purple-300"
                        : "bg-gray-700 text-gray-400"
                  }`}
                >
                  {stock.market}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
