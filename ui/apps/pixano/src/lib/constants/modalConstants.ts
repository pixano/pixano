/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const BLOCKING_ALERT_OVERLAY_CLASS = "fixed inset-0 z-[200] bg-black/48 backdrop-blur-sm";

export const BLOCKING_ALERT_VIEWPORT_CLASS = "fixed inset-0 z-[201] overflow-y-auto p-4 sm:p-6";

export const BLOCKING_ALERT_CONTENT_CLASS =
  "glass-heavy relative my-8 w-full max-w-md overflow-hidden rounded-2xl border border-primary/10 text-left text-foreground shadow-glass-lg";

export const BLOCKING_ALERT_HEADER_CLASS = "relative px-6 pb-4 pt-6 sm:px-7 sm:pt-7";

export const BLOCKING_ALERT_TITLE_CLASS =
  "text-[1.05rem] font-semibold tracking-[-0.025em] text-foreground sm:text-[1.15rem]";

export const BLOCKING_ALERT_SUPPORTING_TEXT_CLASS =
  "mt-2 space-y-2 text-sm leading-6 text-muted-foreground";

export const BLOCKING_ALERT_STATUS_CLASS =
  "mt-4 flex items-center gap-2 rounded-xl border px-3 py-2 text-sm";

export const BLOCKING_ALERT_STATUS_NEUTRAL_CLASS =
  "border-border/50 bg-background/55 text-muted-foreground";

export const BLOCKING_ALERT_STATUS_DANGER_CLASS =
  "border-destructive/20 bg-destructive/8 text-destructive";

export const BLOCKING_ALERT_ACTIONS_CLASS =
  "flex flex-col-reverse gap-2.5 border-t border-border/40 bg-background/18 px-6 py-4 sm:flex-row sm:items-center sm:justify-end";

export const BLOCKING_ALERT_SECONDARY_BUTTON_CLASS =
  "inline-flex h-10 w-full items-center justify-center rounded-xl border border-border/60 bg-background/75 px-4 py-2 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-foreground transition-all duration-200 hover:border-primary/30 hover:bg-accent/65 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 active:scale-95 disabled:pointer-events-none disabled:opacity-50 sm:w-auto";
