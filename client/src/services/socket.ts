import type { QuoteSession } from "../types/Quotes";

type Handler<T> = (data: T) => void;

const WS_URL = `${import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws"}`;

export type QuoteSocketEvents = {
  QUOTE_UPDATED: QuoteSession;
  QUOTE_UPDATED_CLIENT: QuoteSession;
};

class QuoteSocket<Events extends Record<string, unknown>> {
  private ws: WebSocket;
  private handlers: {
    [K in keyof Events]?: Set<Handler<Events[K]>>;
  } = {};

  constructor(url: string) {
    this.ws = new WebSocket(url);
    this.ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        const { event: evt, data } = parsed;
        if (evt && this.handlers[evt as keyof Events]) {
          this.handlers[evt as keyof Events]!.forEach((cb) => cb(data));
        }
      } catch {
        // TODO: add error handling/logging
      }
    };
  }

  on<K extends keyof Events>(event: K, cb: Handler<Events[K]>) {
    if (!this.handlers[event]) this.handlers[event] = new Set();
    this.handlers[event]!.add(cb);
  }

  off<K extends keyof Events>(event: K, cb: Handler<Events[K]>) {
    this.handlers[event]?.delete(cb);
  }

  emit<K extends keyof Events>(event: K, data: Events[K]) {
    this.ws.send(JSON.stringify({ event, data }));
  }
}

export const socket = new QuoteSocket<QuoteSocketEvents>(WS_URL);
