/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Shared controls for the import wizard's source and annotation sections. */
export const WIZARD_INPUT_CLASS =
  "h-10 w-full rounded-lg border border-border bg-card px-3 text-sm text-foreground " +
  "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

export const WIZARD_LABEL_CLASS = "text-sm font-medium text-foreground";

export const WIZARD_SECTION_HEADING_CLASS = "text-sm font-semibold text-foreground";

export const WIZARD_BUTTON_BASE_CLASS =
  "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-3 font-sans text-sm font-medium transition-colors " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
  "disabled:pointer-events-none disabled:opacity-50";

export const WIZARD_PRIMARY_BUTTON_CLASS =
  WIZARD_BUTTON_BASE_CLASS +
  " border border-primary bg-primary text-primary-foreground hover:bg-primary/90";

export const WIZARD_SECONDARY_BUTTON_CLASS =
  WIZARD_BUTTON_BASE_CLASS + " border border-border bg-card text-foreground hover:bg-accent";

export const WIZARD_GHOST_BUTTON_CLASS =
  WIZARD_BUTTON_BASE_CLASS + " text-muted-foreground hover:bg-accent hover:text-foreground";

export const WIZARD_ICON_BUTTON_CLASS =
  "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-muted-foreground " +
  "transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50";

export const WIZARD_DISCLOSURE_CLASS = "group border-t border-border/60 pt-4";

export const WIZARD_DISCLOSURE_SUMMARY_CLASS =
  "cursor-pointer rounded text-sm font-medium text-foreground focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-ring";

export const WIZARD_CHOICE_CARD_CLASS =
  "relative rounded-xl border text-left " +
  "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-background " +
  "disabled:cursor-not-allowed disabled:opacity-45";
