// Polish plural forms: one, few (2-4 but not 12-14), many.
export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  const last = n % 10;
  const lastTwo = n % 100;
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many;
}

export const NO_FIRM_LABEL = 'bez dopasowanej firmy';
