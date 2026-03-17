export interface NavItem {
  title: string;
  href?: string;
  children?: NavItem[];
  external?: boolean;
  icon?: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const topNav: NavItem[] = [
  { title: "Getting Started", href: "/getting_started/" },
  { title: "Tutorials", href: "/tutorials/" },
  { title: "API Reference", href: "/api_reference/" },
];

export const sidebarNav: Record<string, NavSection[]> = {
  getting_started: [
    {
      title: "Getting Started",
      items: [
        { title: "Overview", href: "/getting_started/" },
        { title: "Quickstart", href: "/getting_started/quickstart/" },
        {
          title: "Installing Pixano",
          href: "/getting_started/installing_pixano/",
        },
        { title: "Key Concepts", href: "/getting_started/key_concepts/" },
        {
          title: "Launching the App",
          href: "/getting_started/launching_the_app/",
        },
        { title: "Using the App", href: "/getting_started/using_the_app/" },
      ],
    },
  ],
  tutorials: [
    {
      title: "Tutorials",
      items: [
        { title: "Overview", href: "/tutorials/" },
        { title: "Build a Dataset", href: "/tutorials/dataset/" },
        { title: "Semantic Search", href: "/tutorials/semantic_search/" },
        {
          title: "Interactive Segmentation",
          href: "/tutorials/interactive_segmentation/",
        },
        { title: "Pre-annotation", href: "/tutorials/pre_annotation/" },
      ],
    },
  ],
  api_reference: [
    {
      title: "API Reference",
      items: [
        { title: "Overview", href: "/api_reference/" },
      ],
    },
    {
      title: "pixano.api",
      items: [
        { title: "display", href: "/api_reference/module/api/display/" },
        { title: "main", href: "/api_reference/module/api/main/" },
        { title: "media", href: "/api_reference/module/api/media/" },
        { title: "models", href: "/api_reference/module/api/models/" },
        { title: "resources", href: "/api_reference/module/api/resources/" },
        { title: "serve", href: "/api_reference/module/api/serve/" },
        { title: "service", href: "/api_reference/module/api/service/" },
        { title: "settings", href: "/api_reference/module/api/settings/" },
        {
          title: "routers",
          href: "/api_reference/module/api/routers/",
          children: [
            { title: "datasets", href: "/api_reference/module/api/routers/datasets/" },
            { title: "records", href: "/api_reference/module/api/routers/records/" },
            { title: "views", href: "/api_reference/module/api/routers/views/" },
            { title: "conversations", href: "/api_reference/module/api/routers/conversations/" },
          ],
        },
      ],
    },
    {
      title: "pixano.cli",
      items: [
        { title: "data", href: "/api_reference/module/cli/data/" },
        { title: "init", href: "/api_reference/module/cli/init/" },
        { title: "server", href: "/api_reference/module/cli/server/" },
      ],
    },
    {
      title: "pixano.datasets",
      items: [
        { title: "dataset", href: "/api_reference/module/datasets/dataset/" },
        { title: "dataset_info", href: "/api_reference/module/datasets/dataset_info/" },
        { title: "dataset_schema", href: "/api_reference/module/datasets/dataset_schema/" },
        { title: "dataset_stat", href: "/api_reference/module/datasets/dataset_stat/" },
        {
          title: "builders",
          children: [
            { title: "dataset_builder", href: "/api_reference/module/datasets/builders/dataset_builder/" },
            { title: "image", href: "/api_reference/module/datasets/builders/folders/image/" },
            { title: "video", href: "/api_reference/module/datasets/builders/folders/video/" },
            { title: "vqa", href: "/api_reference/module/datasets/builders/folders/vqa/" },
          ],
        },
        {
          title: "workspaces",
          href: "/api_reference/module/datasets/workspaces/",
        },
      ],
    },
    {
      title: "pixano.schemas",
      items: [
        { title: "records", href: "/api_reference/module/schemas/records/" },
        { title: "schema_group", href: "/api_reference/module/schemas/schema_group/" },
        {
          title: "annotations",
          children: [
            { title: "bbox", href: "/api_reference/module/schemas/annotations/bbox/" },
            { title: "compressed_rle", href: "/api_reference/module/schemas/annotations/compressed_rle/" },
            { title: "keypoints", href: "/api_reference/module/schemas/annotations/keypoints/" },
            { title: "message", href: "/api_reference/module/schemas/annotations/message/" },
            { title: "tracklet", href: "/api_reference/module/schemas/annotations/tracklet/" },
          ],
        },
        {
          title: "entities",
          children: [
            { title: "entity", href: "/api_reference/module/schemas/entities/entity/" },
          ],
        },
        {
          title: "views",
          children: [
            { title: "image", href: "/api_reference/module/schemas/views/image/" },
            { title: "video", href: "/api_reference/module/schemas/views/video/" },
            { title: "view", href: "/api_reference/module/schemas/views/view/" },
          ],
        },
        {
          title: "embeddings",
          children: [
            { title: "embedding", href: "/api_reference/module/schemas/embeddings/embedding/" },
          ],
        },
      ],
    },
    {
      title: "pixano.inference",
      items: [
        { title: "provider", href: "/api_reference/module/inference/provider/" },
        { title: "registry", href: "/api_reference/module/inference/registry/" },
        { title: "types", href: "/api_reference/module/inference/types/" },
        { title: "mask_generation", href: "/api_reference/module/inference/mask_generation/" },
      ],
    },
    {
      title: "pixano.features",
      items: [
        {
          title: "utils",
          children: [
            { title: "boxes", href: "/api_reference/module/features/utils/boxes/" },
            { title: "image", href: "/api_reference/module/features/utils/image/" },
            { title: "creators", href: "/api_reference/module/features/utils/creators/" },
          ],
        },
      ],
    },
    {
      title: "pixano.utils",
      items: [
        { title: "python", href: "/api_reference/module/utils/python/" },
        { title: "validation", href: "/api_reference/module/utils/validation/" },
      ],
    },
  ],
};

/**
 * Determine which sidebar section to show based on the current path.
 */
export function getSidebarSection(path: string): string {
  if (path.includes("/tutorials")) return "tutorials";
  if (path.includes("/api_reference")) return "api_reference";
  return "getting_started";
}
