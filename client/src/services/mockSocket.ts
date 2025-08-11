type Handler<T> = (data: T) => void;

class MockSocket<Events extends Record<string, unknown>> {
  private handlers: {
    [K in keyof Events]?: Set<Handler<Events[K]>>;
  } = {};

  on<K extends keyof Events>(event: K, cb: Handler<Events[K]>) {
    if (!this.handlers[event]) this.handlers[event] = new Set();
    this.handlers[event]!.add(cb);
  }

  off<K extends keyof Events>(event: K, cb: Handler<Events[K]>) {
    this.handlers[event]?.delete(cb);
  }

  emit<K extends keyof Events>(event: K, data: Events[K]) {
    this.handlers[event]?.forEach((cb) => cb(data));
  }
}

type QuoteSocketEvents = {
  QUOTE_UPDATED: import("../types/Quotes").QuotePayload;
};

export const mockSocket = new MockSocket<QuoteSocketEvents>();
