/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Types, utils, icons
export * from "$lib/types/dataset";
export * from "$lib/types/inference";
export * from "$lib/types/shapeTypes";
export * from "$lib/utils/domainFactories";
export * from "$lib/utils/coreUtils";
export * as utils from "$lib/utils/coreUtils";
export { effectProbe, getEffectProbeSnapshot } from "$lib/utils/effectProbe";
export * as icons from "./icons";
export { cn } from "$lib/utils/styleUtils";

// bits-ui re-exports (direct, no wrappers)
export { Checkbox, ContextMenu, RadioGroup, Select, Slider, Tabs, Tooltip } from "bits-ui";

// Kept components (no bits-ui equivalent or useful composites)
export { AutoResizeTextarea } from "$components/ui/autoresize-textarea";
export * as Card from "$components/ui/card";
export { Input, type InputEvents } from "$components/ui/input";
export { Skeleton } from "$components/ui/skeleton";
export { default as ThemeToggle } from "$components/ui/theme-toggle/ThemeToggle.svelte";
export { default as Histogram } from "$components/ui/histogram/Histogram.svelte";

// Molecules (kept, internals updated to use bits-ui directly)
export { default as PrimaryButton } from "$components/ui/molecules/PrimaryButton.svelte";
export { default as IconButton } from "$components/ui/molecules/TooltipIconButton.svelte";
export { default as ModelSelectBadge } from "$components/ui/model-select-badge/ModelSelectBadge.svelte";
export { default as AiProcessingBadge } from "$components/ui/ai-processing-badge/AiProcessingBadge.svelte";

// Modals (kept)
export { default as ConfirmModal } from "$components/modals/ConfirmModal.svelte";
export { default as PromptModal } from "$components/modals/PromptModal.svelte";
export { default as SelectModal } from "$components/modals/SelectModal.svelte";
export { default as WarningModal } from "$components/modals/WarningModal.svelte";
