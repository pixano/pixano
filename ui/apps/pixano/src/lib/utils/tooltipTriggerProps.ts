/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Props for a bits-ui tooltip trigger rendered through its `child` snippet on an
 * element that is not a control (a row, a label, a wrapper). bits-ui merges
 * `type="button"` and `tabindex="0"` into the snippet props; both are dropped so the
 * element is neither an invalid button nor a keyboard tab stop, while the ids, data
 * attributes and pointer handlers the tooltip needs are kept.
 */
export function passiveTriggerProps<T extends Record<string, unknown>>(
  props: T,
): Omit<T, "type" | "tabindex"> {
  const { type, tabindex, ...rest } = props;
  void type;
  void tabindex;
  return rest;
}
