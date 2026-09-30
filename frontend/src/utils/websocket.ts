type WebSocketEventHandler = (data: any) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<WebSocketEventHandler>> = new Map();
  private reconnectTimer: number | null = null;
  private url: string = '';

  connect(token: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Using host instead of hardcoding localhost to work dynamically
    this.url = `${protocol}//${window.location.host}/ws/chat/?token=${token}`;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      if (this.reconnectTimer) {
        window.clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    };

    this.ws.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      const handlers = this.handlers.get(parsed.type);
      if (handlers) {
        handlers.forEach((handler) => handler(parsed.data));
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.ws = null;
      this.reconnectTimer = window.setTimeout(() => this.connect(token), 3000);
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  subscribe(eventType: string, handler: WebSocketEventHandler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);
  }

  unsubscribe(eventType: string, handler: WebSocketEventHandler) {
    const handlers = this.handlers.get(eventType);
    if (handlers) {
      handlers.delete(handler);
    }
  }
}

export const wsManager = new WebSocketManager();
