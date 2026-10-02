// The browser entry only needs this public lifecycle contract.
// Feature controllers remain JavaScript; this does not claim their internals are type-checked.
export interface Application {
  start(): void;
}
export function createApplication(): Application;
