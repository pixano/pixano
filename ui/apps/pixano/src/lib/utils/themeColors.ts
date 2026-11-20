/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * A color of the theme, from the triplet its token holds — `--primary: 330 65% 50%` —, at an opacity.
 *
 * Written with commas: the parser chart.js derives its hover colors with reads no opacity written
 * after a slash. A token that holds no triplet gives its value as it is.
 */
export function tokenColor(triplet: string, alpha = 1): string {
  const parts = triplet.trim().split(/\s+/);
  if (parts.length !== 3) return triplet;
  const [hue, saturation, lightness] = parts;
  return `hsla(${hue}, ${saturation}, ${lightness}, ${alpha})`;
}

/** The value of each of these tokens on the page, as the theme in force defines them. */
export function readTokens(names: readonly string[]): string[] {
  if (typeof document === "undefined") return names.map(() => "");
  const style = getComputedStyle(document.documentElement);
  return names.map((name) => style.getPropertyValue(name).trim());
}
