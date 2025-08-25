import type { QuoteSession } from "../types/Quotes";

type Handler<T> = (data: T) => void;

const WS_BASE_URL = import.meta.env.VITE_WS_URL as string;

export type QuoteSocketEvents = {
  QUOTE_UPDATED: QuoteSession;
  QUOTE_UPDATED_CLIENT: QuoteSession;
  ERROR?: string;
  UNKNOWN_EVENT?: string;
};

type PendingEvent<Events> = {
  [K in keyof Events]: { event: K; data: Events[K] };
}[keyof Events];

export class QuoteSocket<Events extends Record<string, unknown>> {
  private ws: WebSocket | null = null;
  private handlers: { [K in keyof Events]?: Set<Handler<Events[K]>> } = {};
  private pendingQueue: PendingEvent<Events>[] = [];
  private urlBase: string;

  constructor(urlBase: string) {
    this.urlBase = urlBase;
  }

  connect(token: string) {
    if (!token) throw new Error("WS connect called without token");
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }
    const urlWithToken = this.urlBase.includes("?")
      ? `${this.urlBase}&token=${encodeURIComponent(token)}`
      : `${this.urlBase}?token=${encodeURIComponent(token)}`;

    this.ws = new WebSocket(urlWithToken);

    this.ws.onopen = () => {
      const queued = [...this.pendingQueue];
      this.pendingQueue = [];
      queued.forEach(({ event, data }) => this._send(event, data));
    };

    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as {
          event?: keyof Events;
          data: unknown;
        };
        const evt = parsed.event;
        if (evt && this.handlers[evt]) {
          // type cast seguro porque sabemos que evt es keyof Events
          this.handlers[evt]!.forEach((cb) =>
            cb(parsed.data as Events[typeof evt]),
          );
        }
      } catch (error) {
        console.error(error);
      }
    };

    this.ws.onclose = (e) => {
      console.error(e);
      this.ws = null;
    };

    this.ws.onerror = () => {
      // noop
    };
  }

  disconnect() {
    if (this.ws) {
      try {
        this.ws.close(1000, "Client closing");
      } catch (error) {
        console.error(error);
      }
      this.ws = null;
    }
    this.pendingQueue = [];
  }

  on<K extends keyof Events>(event: K, cb: Handler<Events[K]>) {
    if (!this.handlers[event]) this.handlers[event] = new Set();
    this.handlers[event]!.add(cb);
  }

  off<K extends keyof Events>(event: K, cb: Handler<Events[K]>) {
    this.handlers[event]?.delete(cb);
  }

  emit<K extends keyof Events>(event: K, data: Events[K]) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this._send(event, data);
      return;
    }
    this.pendingQueue.push({ event, data } as PendingEvent<Events>);
  }

  private _send<K extends keyof Events>(event: K, data: Events[K]) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.pendingQueue.push({ event, data } as PendingEvent<Events>);
      return;
    }
    this.ws.send(JSON.stringify({ event, data }));
  }
}

export const socket = new QuoteSocket<QuoteSocketEvents>(WS_BASE_URL);
