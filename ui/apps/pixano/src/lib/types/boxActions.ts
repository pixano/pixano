/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Actions offered by the action chip of a box on the canvas ("…" menu). */
export type BoxActionId =
  | "add-keyframe"
  | "remove-keyframe"
  | "split-track"
  | "delete-track"
  | "delete-box";

export interface BoxAction {
  id: BoxActionId;
  label: string;
  /** Destroys data: the menu asks for a second click, showing `confirmLabel`. */
  destructive?: boolean;
  confirmLabel?: string;
  disabled?: boolean;
  disabledReason?: string;
  run: () => void;
}
