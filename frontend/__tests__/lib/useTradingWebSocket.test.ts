import { renderHook, act } from "@testing-library/react";
import { useTradingWebSocket } from "@/lib/useTradingWebSocket";

// Mock localStorage
const mockGetItem = jest.fn();
Object.defineProperty(window, "localStorage", {
  value: { getItem: mockGetItem, setItem: jest.fn(), removeItem: jest.fn() },
  writable: true,
});

// Mock ws module
const mockConnect = jest.fn();
const mockOn = jest.fn(() => jest.fn()); // returns unsub fn
const mockDisconnect = jest.fn();

jest.mock("@/lib/ws", () => ({
  createWSConnection: jest.fn(() => ({
    connect: mockConnect,
    on: mockOn,
    disconnect: mockDisconnect,
  })),
}));

describe("useTradingWebSocket", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetItem.mockReturnValue("test-token");
  });

  it("connects to trading WS on mount with token", () => {
    renderHook(() =>
      useTradingWebSocket({
        onOrderUpdate: jest.fn(),
      })
    );

    const { createWSConnection } = require("@/lib/ws");
    expect(createWSConnection).toHaveBeenCalledWith("trading");
    expect(mockConnect).toHaveBeenCalledWith("test-token");
  });

  it("does not connect when no token", () => {
    mockGetItem.mockReturnValue(null);

    renderHook(() => useTradingWebSocket({}));

    expect(mockConnect).not.toHaveBeenCalled();
  });

  it("subscribes to order_update, price_update, recipe_signal events", () => {
    renderHook(() =>
      useTradingWebSocket({
        onOrderUpdate: jest.fn(),
        onPriceUpdate: jest.fn(),
        onRecipeSignal: jest.fn(),
      })
    );

    // Should register 3 event handlers
    expect(mockOn).toHaveBeenCalledTimes(3);
    const eventTypes = mockOn.mock.calls.map(
      (call: unknown[]) => call[0]
    );
    expect(eventTypes).toContain("order_update");
    expect(eventTypes).toContain("price_update");
    expect(eventTypes).toContain("recipe_signal");
  });

  it("disconnects on unmount", () => {
    const { unmount } = renderHook(() => useTradingWebSocket({}));

    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
  });
});
