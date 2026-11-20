export type NextFn = () => Promise<void>;
export type EventMiddleware<T = unknown> = (
  topic: string,
  payload: T,
  next: NextFn,
) => Promise<void> | void;

/**
 * Composes async middlewares into a single execution pipeline.
 */
export async function runPipeline<T = unknown>(
  topic: string,
  payload: T,
  middlewares: EventMiddleware<T>[],
  terminal: () => Promise<void> | void,
): Promise<void> {
  let index = -1;

  async function dispatch(i: number): Promise<void> {
    if (i <= index) {
      throw new Error("next() called multiple times");
    }
    index = i;
    if (i === middlewares.length) {
      await terminal();
      return;
    }
    const mw = middlewares[i];
    await mw(topic, payload, () => dispatch(i + 1));
  }

  await dispatch(0);
}
