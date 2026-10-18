export function staticListKey(
  section: string,
  item: string,
  index: number,
): string {
  return `${section}:${index}:${item}`;
}
