/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { UploadProgress } from "$lib/api/uploadClient";

/** Kept by the wizard so editing a reviewed import retains its source and upload summary. */
export interface WizardSourceState {
  mode: "upload" | "hub";
  status: "idle" | "uploading" | "done" | "error";
  error: string;
  uploadId: string;
  summary: { folderName: string; fileCount: number; totalBytes: number } | null;
  progress: UploadProgress | null;
}

export function createWizardSourceState(): WizardSourceState {
  return { mode: "upload", status: "idle", error: "", uploadId: "", summary: null, progress: null };
}
