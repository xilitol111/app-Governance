/** Normalize generated and inspected text so comparisons are platform independent. */
export function normalizeLf(value: string): string {
  return value.replace(/\r\n?/g, "\n");
}
