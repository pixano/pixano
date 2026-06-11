/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { WorkspaceSession } from "../workspaceSession.svelte.js";

describe("WorkspaceSession", () => {
  it("starts with null datasetId and recordId", () => {
    const session = new WorkspaceSession();
    expect(session.datasetId).toBeNull();
    expect(session.recordId).toBeNull();
  });

  it("starts with empty entities and null entitySchemaName", () => {
    const session = new WorkspaceSession();
    expect(session.entities).toEqual([]);
    expect(session.entitySchemaName).toBeNull();
  });

  it("stores assigned datasetId and recordId", () => {
    const session = new WorkspaceSession();
    session.datasetId = "ds-1";
    session.recordId = "rec-42";

    expect(session.datasetId).toBe("ds-1");
    expect(session.recordId).toBe("rec-42");
  });

  it("stores assigned entities and entitySchemaName", () => {
    const session = new WorkspaceSession();
    session.entities = [{ id: "e1", record_id: "rec-1" }];
    session.entitySchemaName = "VOCEntity";

    expect(session.entities).toHaveLength(1);
    expect(session.entities[0].id).toBe("e1");
    expect(session.entitySchemaName).toBe("VOCEntity");
  });

  it("reset() clears all fields back to initial values", () => {
    const session = new WorkspaceSession();
    session.datasetId = "ds-1";
    session.recordId = "rec-42";
    session.entities = [{ id: "e1", record_id: "rec-1" }];
    session.entitySchemaName = "VOCEntity";

    session.reset();

    expect(session.datasetId).toBeNull();
    expect(session.recordId).toBeNull();
    expect(session.entities).toEqual([]);
    expect(session.entitySchemaName).toBeNull();
  });

  it("reset() is idempotent on an already-empty session", () => {
    const session = new WorkspaceSession();
    session.reset();
    expect(session.datasetId).toBeNull();
    expect(session.recordId).toBeNull();
    expect(session.entities).toEqual([]);
    expect(session.entitySchemaName).toBeNull();
  });

  it("multiple sessions are independent", () => {
    const a = new WorkspaceSession();
    const b = new WorkspaceSession();
    a.datasetId = "ds-a";
    a.entities = [{ id: "e1", record_id: "rec-1" }];

    expect(b.datasetId).toBeNull();
    expect(b.entities).toEqual([]);
  });
});
