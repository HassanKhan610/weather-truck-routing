export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

export function formatMiles(miles: number): string {
  return `${miles.toLocaleString("en-US", { maximumFractionDigits: miles < 10 ? 1 : 0 })} mi`;
}

export function formatPounds(lb: number): string {
  return `${lb.toLocaleString("en-US")} lb`;
}

const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** Value for <input type="datetime-local"> in the browser's timezone. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** Next quarter hour from ``now``, a sensible default departure. */
export function nextQuarterHour(now = new Date()): Date {
  const date = new Date(now);
  date.setSeconds(0, 0);
  date.setMinutes(Math.ceil((date.getMinutes() + 1) / 15) * 15);
  return date;
}
