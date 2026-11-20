export type EventHandler<T = unknown> = (payload: T, topic: string) => void | Promise<void>;

interface Entry {
  pattern: string;
  handler: EventHandler<any>;
}

export function matchTopic(pattern: string, topic: string): boolean {
  const p = pattern.split(".");
  const t = topic.split(".");
  if (p.length !== t.length) {
    return false;
  }
  for (let i = 0; i < p.length; i += 1) {
    if (p[i] !== "*" && p[i] !== t[i]) {
      return false;
    }
  }
  return true;
}

export class EventBus {
  private entries: Entry[] = [];

  on<T = unknown>(pattern: string, handler: EventHandler<T>): () => void {
    if (!pattern) {
      throw new Error("pattern must not be empty");
    }
    const entry: Entry = { pattern, handler };
    this.entries.push(entry);
    return () => {
      this.entries = this.entries.filter((item) => item !== entry);
    };
  }

  async emit<T = unknown>(topic: string, payload: T): Promise<number> {
    if (!topic) {
      throw new Error("topic must not be empty");
    }
    const snapshot = [...this.entries];
    let count = 0;
    for (const entry of snapshot) {
      if (matchTopic(entry.pattern, topic)) {
        count += 1;
        await entry.handler(payload, topic);
      }
    }
    return count;
  }
}
