import assert from "node:assert/strict";
import test from "node:test";

import { EventBus, matchTopic } from "./event_bus.ts";

// Part A: 基础行为
test("Part A: exact and single-segment wildcard topic matching", () => {
  assert.equal(matchTopic("order.created", "order.created"), true);
  assert.equal(matchTopic("order.*", "order.created"), true);
  assert.equal(matchTopic("*.created", "order.created"), true);
  assert.equal(matchTopic("order.*", "order.item.created"), false);
});

test("Part A: emit invokes matching async handlers in order", async () => {
  const bus = new EventBus();
  const seen: string[] = [];
  bus.on("order.*", async (payload: { id: number }, topic) => {
    seen.push(`wild:${topic}:${payload.id}`);
  });
  bus.on("order.created", (payload: { id: number }) => {
    seen.push(`exact:${payload.id}`);
  });

  const count = await bus.emit("order.created", { id: 7 });
  assert.equal(count, 2);
  assert.deepEqual(seen, ["wild:order.created:7", "exact:7"]);
});

// Part B: 边界与异常
test("Part B: empty pattern or topic throws error", async () => {
  const bus = new EventBus();
  assert.throws(() => bus.on("", () => {}));
  await assert.rejects(() => bus.emit("", {}));
});

// Part C: 派发期安全退订
test("Part C: unsubscribing inside handler does not skip sibling subscribers", async () => {
  const bus = new EventBus();
  const calls: string[] = [];

  let unsubFirst: () => void = () => {};
  unsubFirst = bus.on("job.done", () => {
    calls.push("first");
    unsubFirst();
  });
  bus.on("job.done", () => {
    calls.push("second");
  });

  const firstCount = await bus.emit("job.done", null);
  assert.equal(firstCount, 2);
  assert.deepEqual(calls, ["first", "second"]);

  const secondCount = await bus.emit("job.done", null);
  assert.equal(secondCount, 1);
  assert.deepEqual(calls, ["first", "second", "second"]);
});
