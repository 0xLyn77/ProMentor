export type EventHandler<T = unknown> = (payload: T, topic: string) => void | Promise<void>;

interface Subscription {
  pattern: string;
  handler: EventHandler<any>;
}

/**
 * Asynchronous topic-based EventBus with single-segment wildcard ("*") matching.
 */
export class EventBus {
  private readonly subscriptions: Subscription[] = [];

  on<T = unknown>(pattern: string, handler: EventHandler<T>): () => void {
    if (!pattern) {
      throw new Error("pattern must not be empty");
    }
    const sub: Subscription = { pattern, handler };
    this.subscriptions.push(sub);
    return () => {
      const idx = this.subscriptions.indexOf(sub);
      if (idx >= 0) {
        this.subscriptions.splice(idx, 1);
      }
    };
  }

  async emit<T = unknown>(topic: string, payload: T): Promise<number> {
    if (!topic) {
      throw new Error("topic must not be empty");
    }
    // Snapshot matching subscriptions so unsubscribing inside a handler is safe.
    const matched = this.subscriptions.filter((sub) => matchTopic(sub.pattern, topic));
    for (const sub of matched) {
      await sub.handler(payload, topic);
    }
    return matched.length;
  }
}

export function matchTopic(pattern: string, topic: string): boolean {
  const pParts = pattern.split(".");
  const tParts = topic.split(".");
  if (pParts.length !== tParts.length) {
    return false;
  }
  return pParts.every((part, i) => part === "*" || part === tParts[i]);
}
