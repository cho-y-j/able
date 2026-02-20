"use client";

import { useState } from "react";
import { StockAutocomplete } from "@/components/StockAutocomplete";

interface FilterBuilderProps {
  customFilters: Record<string, unknown>;
  stockCodes: string[];
  onFiltersChange: (filters: Record<string, unknown>) => void;
  onStockCodesChange: (codes: string[]) => void;
}

export default function FilterBuilder({
  customFilters,
  stockCodes,
  onFiltersChange,
  onStockCodesChange,
}: FilterBuilderProps) {
  const [stockInput, setStockInput] = useState("");
  // Store display names for stock codes
  const [stockNames, setStockNames] = useState<Record<string, string>>({});

  const toggleFilter = (key: string, defaultValue: unknown) => {
    if (key in customFilters) {
      const updated = { ...customFilters };
      delete updated[key];
      onFiltersChange(updated);
    } else {
      onFiltersChange({ ...customFilters, [key]: defaultValue });
    }
  };

  const updateFilter = (key: string, value: unknown) => {
    onFiltersChange({ ...customFilters, [key]: value });
  };

  const addStock = (code: string, name?: string) => {
    if (!stockCodes.includes(code)) {
      onStockCodesChange([...stockCodes, code]);
      setStockNames((prev) => ({ ...prev, [code]: name || code }));
    }
    setStockInput("");
  };

  const removeStockCode = (code: string) => {
    onStockCodesChange(stockCodes.filter((c) => c !== code));
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">커스텀 필터 + 대상 종목</h3>
        <p className="text-gray-400 text-sm">추가 조건과 적용할 종목을 설정하세요</p>
      </div>

      {/* Custom Filters */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-300">추가 필터</h4>

        {/* Volume minimum */}
        <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3 border border-gray-700">
          <input
            type="checkbox"
            checked={"volume_min" in customFilters}
            onChange={() => toggleFilter("volume_min", 1000000)}
            className="w-4 h-4 rounded accent-blue-500"
          />
          <div className="flex-1">
            <label className="text-sm text-gray-300">최소 거래량</label>
            {"volume_min" in customFilters && (
              <input
                type="number"
                value={(customFilters.volume_min as number) || 1000000}
                onChange={(e) => updateFilter("volume_min", Number(e.target.value))}
                className="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm"
                placeholder="1,000,000"
              />
            )}
          </div>
        </div>

        {/* Price range */}
        <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3 border border-gray-700">
          <input
            type="checkbox"
            checked={"price_range" in customFilters}
            onChange={() => toggleFilter("price_range", [10000, 500000])}
            className="w-4 h-4 rounded accent-blue-500"
          />
          <div className="flex-1">
            <label className="text-sm text-gray-300">가격 범위 (원)</label>
            {"price_range" in customFilters && (
              <div className="flex gap-2 mt-1">
                <input
                  type="number"
                  value={((customFilters.price_range as number[]) || [10000])[0]}
                  onChange={(e) => {
                    const range = (customFilters.price_range as number[]) || [10000, 500000];
                    updateFilter("price_range", [Number(e.target.value), range[1]]);
                  }}
                  className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm"
                  placeholder="최소"
                />
                <span className="text-gray-500 self-center">~</span>
                <input
                  type="number"
                  value={((customFilters.price_range as number[]) || [0, 500000])[1]}
                  onChange={(e) => {
                    const range = (customFilters.price_range as number[]) || [10000, 500000];
                    updateFilter("price_range", [range[0], Number(e.target.value)]);
                  }}
                  className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-white text-sm"
                  placeholder="최대"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Target Stocks */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-gray-300">대상 종목</h4>

        <StockAutocomplete
          value={stockInput}
          onChange={setStockInput}
          onSelect={addStock}
          placeholder="종목코드 또는 종목명으로 검색"
          className="!py-2.5"
        />

        {stockCodes.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {stockCodes.map((code) => (
              <span
                key={code}
                className="inline-flex items-center gap-1.5 bg-gray-800 border border-gray-700 rounded-full px-3 py-1.5 text-sm text-gray-300"
              >
                {stockNames[code] ? (
                  <>
                    <span className="text-white">{stockNames[code]}</span>
                    <span className="text-gray-500">{code}</span>
                  </>
                ) : (
                  code
                )}
                <button
                  onClick={() => removeStockCode(code)}
                  className="text-gray-500 hover:text-red-400 transition-colors ml-0.5"
                >
                  x
                </button>
              </span>
            ))}
          </div>
        ) : (
          <div className="bg-gray-800/50 border border-dashed border-gray-700 rounded-lg p-4 text-center">
            <p className="text-gray-400 text-sm">대상 종목이 없습니다</p>
            <p className="text-gray-500 text-xs mt-1">위 검색창에서 종목을 추가하세요. 종목을 추가해야 백테스트와 자동매매를 실행할 수 있습니다.</p>
          </div>
        )}
      </div>
    </div>
  );
}
