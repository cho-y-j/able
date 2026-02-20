const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/api/v1/ws';

type MessageHandler = (data: unknown) => void;

const MAX_RETRIES = 10;
const BASE_DELAY = 1000;
const MAX_DELAY = 30000;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;
  private retryCount = 0;

  constructor(path: string) {
    this.url = `${WS_URL}/${path}`;
  }

  connect(token: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(`${this.url}?token=${token}`);

    this.ws.onopen = () => {
      this.retryCount = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const type = data.type || 'message';
        this.handlers.get(type)?.forEach((handler) => handler(data));
        this.handlers.get('*')?.forEach((handler) => handler(data));
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      if (this.retryCount >= MAX_RETRIES) return;
      const delay = Math.min(BASE_DELAY * Math.pow(2, this.retryCount), MAX_DELAY);
      this.retryCount++;
      this.reconnectTimer = setTimeout(() => this.connect(token), delay);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);
    return () => this.handlers.get(type)?.delete(handler);
  }

  disconnect(): void {
    this.retryCount = MAX_RETRIES; // prevent reconnect on intentional disconnect
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}

export function createWSConnection(path: string): WebSocketManager {
  return new WebSocketManager(path);
}
