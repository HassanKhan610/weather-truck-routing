import { formatDuration, formatMiles, nextQuarterHour, toLocalInputValue } from "./format";

describe("format", () => {
  it.each([
    [59 * 60, "59m"],
    [3600, "1h 00m"],
    [5 * 3600 + 7 * 60 + 20, "5h 07m"],
  ])("formats %i seconds as %s", (seconds, text) => {
    expect(formatDuration(seconds)).toBe(text);
  });

  it("formats miles", () => {
    expect(formatMiles(1234.4)).toBe("1,234 mi");
    expect(formatMiles(2.25)).toBe("2.3 mi");
  });

  it("rounds up to the next quarter hour", () => {
    expect(toLocalInputValue(nextQuarterHour(new Date(2026, 10, 2, 9, 7)))).toBe(
      "2026-11-02T09:15",
    );
    expect(toLocalInputValue(nextQuarterHour(new Date(2026, 10, 2, 9, 15)))).toBe(
      "2026-11-02T09:30",
    );
    expect(toLocalInputValue(nextQuarterHour(new Date(2026, 10, 2, 23, 50)))).toBe(
      "2026-11-03T00:00",
    );
  });
});
