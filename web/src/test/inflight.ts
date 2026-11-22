// Requests a test left running, awaited by the shared afterEach before it resets the MSW handlers.
// Unmounting does not cancel a request RTK Query has started. One left in flight can reach MSW only
// after the next test has installed its own handlers, and is then counted or answered there (issue
// #94). Awaiting them first means a test's requests are always served by that test's handlers.
// No imports on purpose: setup.ts loads this before each test file, and pulling the api client in
// here would load it before a test file's vi.mock of it applies.
type Running = () => PromiseLike<unknown>[];

const sources = new Set<Running>();

// makeStore registers each store's running queries and mutations here.
export function trackRunning(source: Running): void {
  sources.add(source);
}

export async function settleInFlight(): Promise<void> {
  const running = [...sources].flatMap((source) => source());
  sources.clear();
  await Promise.allSettled(running);
}
