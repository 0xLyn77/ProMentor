export type EventHandler<T = unknown> = (payload: T, topic: string) => void | Promise<void>;

/**
 * Matches a dot-delimited topic against a pattern supporting single-segment "*".
 */
export function matchTopic(pattern: string, topic: string): boolean {
  throw new Error("not implemented: matchTopic");
}

/**
 * Asynchronous topic-based EventBus.
 */
export class EventBus {
  on<T = unknown>(pattern: string, handler: EventHandler<T>): () => void {
    throw new Error("not implemented: EventBus.on");
  }

  async emit<T = unknown>(topic: string, payload: T): Promise<number> {
    throw new Error("not implemented: EventBus.emit");
  }
}
