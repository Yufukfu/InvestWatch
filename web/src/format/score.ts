// Scores in the Polish UI: two places after a decimal comma (`0,87`). The value is a number from the API.
export function formatScore(value: number): string {
  return value.toFixed(2).replace('.', ',');
}
