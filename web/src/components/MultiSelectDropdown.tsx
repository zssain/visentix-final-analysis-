/**
 * MultiSelectDropdown — a compact dropdown whose menu is a list of checkboxes.
 * Used by the intake filters for both INDUSTRY and STATE PRIVACY LAWS so the two
 * controls look and behave identically (ARCH-001A).
 *
 * - Closed by default; the trigger summarises the current selection.
 * - Each option is a checkbox row (role="option", aria-selected) — click toggles.
 * - Closes on outside-click or Escape. Fully keyboard-reachable via the trigger.
 */
import { useCallback, useEffect, useId, useRef, useState } from "react";
import "./multiselect.css";

export interface MSDOption {
  value: string;
  label: string;
}

interface MultiSelectDropdownProps {
  options: MSDOption[];
  selected: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Accessible label for the menu (e.g. "State privacy laws"). */
  ariaLabel?: string;
  /** data-testid applied to the root so tests can target the control. */
  testId?: string;
}

export function MultiSelectDropdown({
  options,
  selected,
  onChange,
  placeholder = "Select…",
  disabled = false,
  ariaLabel,
  testId,
}: MultiSelectDropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  // Close on outside-click so the compact control never traps focus.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = useCallback((value: string) => {
    onChange(
      selected.includes(value)
        ? selected.filter(v => v !== value)
        : [...selected, value],
    );
  }, [selected, onChange]);

  // Summary: named picks up to two, then "+N" so the trigger stays compact.
  const labelFor = (v: string) => options.find(o => o.value === v)?.label ?? v;
  const chosen = selected.filter(v => options.some(o => o.value === v));
  let summary = placeholder;
  if (chosen.length === 1) summary = labelFor(chosen[0]);
  else if (chosen.length === 2) summary = chosen.map(labelFor).join(", ");
  else if (chosen.length > 2) summary = `${labelFor(chosen[0])} +${chosen.length - 1} more`;

  return (
    <div className="msd" ref={rootRef} data-testid={testId}>
      <button
        type="button"
        className={`msd-trigger ${open ? "open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={menuId}
        disabled={disabled}
        onClick={() => setOpen(o => !o)}
      >
        <span className={chosen.length ? "msd-summary" : "msd-summary msd-placeholder"}>
          {summary}
        </span>
        <span className="msd-caret" aria-hidden="true">▾</span>
      </button>

      {open && (
        <ul
          id={menuId}
          className="msd-menu"
          role="listbox"
          aria-multiselectable="true"
          aria-label={ariaLabel}
        >
          {options.map(o => {
            const on = selected.includes(o.value);
            return (
              <li
                key={o.value}
                role="option"
                aria-selected={on}
                className={`msd-option ${on ? "on" : ""}`}
                onClick={() => toggle(o.value)}
              >
                <input
                  type="checkbox"
                  className="msd-check"
                  checked={on}
                  readOnly
                  tabIndex={-1}
                />
                <span>{o.label}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
