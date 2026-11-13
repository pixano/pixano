/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Digits a decimal value keeps past one, and the significant digits of one below: enough to
 * compare records, few enough to read a column at a glance. */
const DECIMALS_FROM_ONE = 2;
const SIGNIFICANT_DIGITS_BELOW_ONE = 3;
/** What stands for a value a record does not have: no box, no mean box area. */
export const NO_VALUE = "—";

/** A statistic's value as a column shows it. */
export function formatStatisticValue(value: unknown): string {
  if (typeof value !== "number" || Number.isNaN(value)) return NO_VALUE;
  if (Number.isInteger(value)) return value.toLocaleString();
  if (Math.abs(value) >= 1)
    return value.toLocaleString(undefined, { maximumFractionDigits: DECIMALS_FROM_ONE });
  return value.toLocaleString(undefined, {
    maximumSignificantDigits: SIGNIFICANT_DIGITS_BELOW_ONE,
  });
}
