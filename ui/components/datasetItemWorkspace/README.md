# datasetItemWorkspace

Svelte component library for the Pixano dataset item workspace. This is the main editing interface displayed when opening a dataset item.

## Architecture

```
DatasetItemWorkspace.svelte
├── components/
│   ├── DatasetItemViewer/    — Image/video/point-cloud rendering
│   ├── Features/             — Feature editing inputs
│   │   ├── AutoCompleteFeatureInput.svelte
│   │   ├── TextFeatureInput.svelte
│   │   ├── CreateFeatureInputs.svelte
│   │   ├── UpdateFeatureInputs.svelte
│   │   └── SelectFeatureInput.svelte
│   ├── Inspector/            — Object/entity inspector panels
│   ├── SaveShape/            — Shape creation confirmation form
│   ├── Toolbar.svelte        — Annotation tools toolbar
│   ├── Toolbar/              — Toolbar sub-components
│   ├── VideoPlayer/          — Video timeline and playback
│   ├── LoadModelModal.svelte — Smart model selection modal
│   └── PreAnnotation/        — Pre-annotation workflow
└── lib/
    ├── api/                  — API functions
    │   ├── featuresApi.ts    — Feature CRUD + localStorage persistence
    │   ├── modelsApi.ts      — Model inference API
    │   ├── objectsApi/       — Object annotation API
    │   └── videoApi.ts       — Video-specific operations
    ├── stores/               — Svelte stores for workspace state
    ├── settings/             — Validation schemas, tool configs
    ├── types/                — TypeScript type definitions
    ├── constants.ts          — Shared constants
    └── utils/                — Utility functions
```

## Feature inputs

### AutoCompleteFeatureInput

Autocomplete dropdown built on [cmdk](https://cmdk.paco.me). Supports keyboard navigation and filtered search. The Enter key always saves the current input value (intercepted via `Command.Root` `onKeydown`). Empty values are filtered from the dropdown.

### TextFeatureInput

Simple text input wrapper that delegates to `AutoCompleteFeatureInput` for datasets with defined feature values. Passes `datasetId` to `addNewInput` for localStorage persistence.

### Autocomplete persistence

Feature suggestions (e.g. object names, categories) are persisted in the browser's `localStorage`, keyed by dataset ID. The flow:

1. **`addNewInput(store, featureClass, feature, value, datasetId?)`** — adds a new value to the in-memory `FeaturesValues` store and saves to localStorage.
2. **`saveFeaturesToStorage(datasetId, features)`** — serializes `FeaturesValues` to `localStorage` under key `pixano_features_{datasetId}`.
3. **`loadFeaturesFromStorage(datasetId)`** — reads and deserializes from localStorage.
4. **`mergeFeaturesList(backend, stored)`** — merges backend and stored feature values using a union strategy (all unique values are kept).

On item load, `DatasetItemWorkspace.svelte` calls `loadFeaturesFromStorage` and merges with backend values via `mergeFeaturesList`, ensuring suggestions persist across items, page reloads, and reconnections.

## Types

### ItemsMeta

```ts
type ItemsMeta = {
  featuresList: FeaturesValues;  // Available feature values (main + objects)
  item: Item;                     // Current dataset item
  type: WorkspaceType;            // IMAGE, VIDEO, VQA, etc.
  datasetId?: string;             // Used as localStorage key for persistence
  format?: "1bit" | "8bit" | "16bit";
  color?: "grayscale" | "rgb" | "rgba";
};
```

### Feature

Union type for feature inputs: `CheckboxFeature | TextFeature | NumberFeature | ListFeature`.

## Development

```bash
cd ui/
pnpm i
pnpm --parallel run dev
```
