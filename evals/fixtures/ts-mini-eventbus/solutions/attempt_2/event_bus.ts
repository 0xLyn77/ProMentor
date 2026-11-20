export type EventHandler<T = unknown> = (payload: T, topic: string) => void | Promise<void>;

interface Subscription {
  pattern: string;
  segments: string[];
  handler: EventHandler<any>;
}

export function matchTopic(pattern: string, topic: string): boolean {
  const pParts = pattern.split(".");
  const tParts = topic.split(".");
  return pParts.length === tParts.length && pParts.every((part, idx) => part === "*" || part === tParts[idx]);
}

export class EventBus {
  private readonly subscriptions: Subscription[] = [];

  on<T = unknown>(pattern: string, handler: EventHandler<T>): () => void {
    if (!pattern) {
      throw new Error("pattern must not be empty");
    }
    const sub: Subscription = { pattern, segments: pattern.split("."), handler };
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
    const topicSegs = topic.split(".");
    const matched = this.subscriptions.filter(
      (sub) =>
        sub.segments.length === topicSegs.length &&
        sub.segments.every((seg, idx) => seg === "*" || seg === topicSegs[idx]),
    );
    for (const sub of matched) {
      await sub.handler(payload, topic);
    }
    return matched.length;
  }
}
