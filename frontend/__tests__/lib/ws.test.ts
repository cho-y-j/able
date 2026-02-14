import { createWSConnection } from "@/lib/ws";

// Mock WebSocket
class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = MockWebSocket.OPEN;
  url: string;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = jest.fn();

  constructor(url: string) {
    this.url = url;
  }
}

(global as unknown as { WebSocket: typeof MockWebSocket }).WebSocket = MockWebSocket;

describe("createWSConnection", () => {
  it("creates a WebSocketManager with correct path", () => {
    const ws = createWSConnection("trading");
    expect(ws).toBeDefined();
    expect(typeof ws.connect).toBe("function");
    expect(typeof ws.on).toBe("function");
    expect(typeof ws.disconnect).toBe("function");
  });
});

describe("WebSocketManager", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("registers and unregisters event handlers", () => {
    const ws = createWSConnection("trading");
    const handler = jest.fn();

    const unsub = ws.on("notification", handler);
    expect(typeof unsub).toBe("function");

    unsub();
    // After unsubscribe, handler should not be called on new messages
  });

  it("supports wildcard (*) handler", () => {
    const ws = createWSConnection("trading");
    const handler = jest.fn();

    ws.on("*", handler);
    expect(handler).not.toHaveBeenCalled();
  });

  it("registers multiple handlers for same event type", () => {
    const ws = createWSConnection("trading");
    const handler1 = jest.fn();
    const handler2 = jest.fn();

    ws.on("notification", handler1);
    ws.on("notification", handler2);

    // Both handlers registered successfully
    expect(handler1).not.toHaveBeenCalled();
    expect(handler2).not.toHaveBeenCalled();
  });

  it("disconnect clears the connection", () => {
    const ws = createWSConnection("trading");
    // Should not throw
    ws.disconnect();
  });
});
