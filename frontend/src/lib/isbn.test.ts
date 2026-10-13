import { describe, expect, it } from "vitest";

import { isbnFromBarcode } from "./isbn";

describe("barcodes", () => {
  it("knows a book's barcode from any other", () => {
    expect(isbnFromBarcode("9780064400558")).toBe("9780064400558");
    expect(isbnFromBarcode("978-0-06-440055-8")).toBe("9780064400558");
    expect(isbnFromBarcode("4006381333931")).toBeNull();
    expect(isbnFromBarcode("9780064400559")).toBeNull();
    expect(isbnFromBarcode("")).toBeNull();
  });
});
