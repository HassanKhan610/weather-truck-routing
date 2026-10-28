import { useEffect, useId, useState } from "react";

import { api } from "../api/client";
import type { Place } from "../api/types";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 250;

export type PlaceValue = Place | string;

interface Props {
  label: string;
  value: PlaceValue;
  onChange: (value: PlaceValue) => void;
  placeholder?: string;
  search?: (query: string, signal: AbortSignal) => Promise<Place[]>;
}

/**
 * Free-text location with autocomplete. Picking a suggestion stores its coordinates, so the
 * backend can skip geocoding; typing again turns the value back into plain text.
 */
export function PlaceInput({ label, value, onChange, placeholder, search = api.geocode }: Props) {
  const id = useId();
  const listId = `${id}-list`;
  const text = typeof value === "string" ? value : value.label;
  const [suggestions, setSuggestions] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const query = useDebouncedValue(typeof value === "string" ? value.trim() : "", DEBOUNCE_MS);

  useEffect(() => {
    if (query.length < MIN_QUERY_LENGTH) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    search(query, controller.signal)
      .then((results) => {
        setSuggestions(results);
        setActive(-1);
      })
      .catch(() => setSuggestions([])); // suggestions are optional; free text still works
    return () => controller.abort();
  }, [query, search]);

  const choose = (place: Place) => {
    onChange(place);
    setOpen(false);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || !suggestions.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const delta = event.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + delta + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      choose(suggestions[active]!);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  const showList = open && suggestions.length > 0;
  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
        required
        value={text}
        placeholder={placeholder}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul id={listId} role="listbox" className="suggestions">
          {suggestions.map((place, i) => (
            <li
              key={`${place.label}-${i}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(event) => {
                event.preventDefault(); // keep focus so blur doesn't close the list first
                choose(place);
              }}
            >
              {place.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
