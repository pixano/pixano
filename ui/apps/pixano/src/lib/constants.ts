/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Database, House } from "phosphor-svelte";

// --- Dataset table defaults ---

export const DEFAULT_DATASET_TABLE_SIZE = 20;
export const DEFAULT_DATASET_TABLE_PAGE = 1;

export const COUNTS_COLUMNS_PREFIX = "#";

// --- Header navigation ---

export const navItems = [
  {
    name: "Dashboard",
    Icon: House,
  },
  {
    name: "Dataset",
    Icon: Database,
  },
];

// --- Dashboard ---

export const dashboardTabs = [
  "source feature",
  "derived source feature",
  "cloud vision",
  "image content metadata",
] as const;
