import { describe, expect, it } from "vitest";
import { chordStarts, comboFromEvent, conflictWith, normChord } from "../build/keymap";

describe("keymap", () => {
  it("normalises combos and chords", () => {
    expect(normChord("Ctrl+Shift+K  ⌘+S")).toEqual(["cmd+shift+k", "cmd+s"]);
    expect(comboFromEvent({ metaKey: true, ctrlKey: false, shiftKey: false, altKey: false, key: "k", code: "KeyK" })).toBe("cmd+k");
  });
  it("detects conflicts incl. chord prefixes", () => {
    expect(conflictWith("studio.bp", "Cmd+S", {})).toBe("studio.save");
    expect(conflictWith("studio.bp", "Cmd+K", {})).toBe("studio.formatSelection");
    expect(conflictWith("studio.bp", "Cmd+K Cmd+S", { "studio.step": "Cmd+K Cmd+S" })).toBe("studio.step");
    expect(conflictWith("studio.bp", "F9", {})).toBeNull();
  });
  it("lists chord starts", () => { expect(chordStarts({ "studio.step": "Cmd+J Cmd+S" })).toEqual(new Set(["cmd+k", "cmd+j"])); });
});
