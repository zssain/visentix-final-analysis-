/**
 * MultiSelectDropdown — a compact dropdown whose menu is a list of checkboxes.
 * Used by the intake filters for both INDUSTRY and STATE PRIVACY LAWS so the two
 * controls look and behave identically (ARCH-001A).
 *
 * Outside-click, Escape, focus management, typeahead and roving focus are
 * Radix's job — the hand-rolled version wired only mousedown + Escape.
 */
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

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
  options, selected, onChange,
  placeholder = "Select…",
  disabled = false,
  ariaLabel, testId,
}: MultiSelectDropdownProps) {
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value]);

  const summary =
    selected.length === 0 ? placeholder
    : selected.length === 1 ? (options.find(o => o.value === selected[0])?.label ?? selected[0])
    : `${selected.length} selected`;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          disabled={disabled}
          data-testid={testId}
          aria-label={ariaLabel}
          className="w-full justify-between font-normal"
        >
          <span className={cn("truncate", selected.length === 0 && "text-muted-foreground")}>
            {summary}
          </span>
          <ChevronDown className="opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-72 w-(--radix-dropdown-menu-trigger-width) overflow-y-auto">
        {options.map(o => (
          <DropdownMenuCheckboxItem
            key={o.value}
            checked={selected.includes(o.value)}
            onCheckedChange={() => toggle(o.value)}
            onSelect={(e) => e.preventDefault() /* keep the menu open for multi-select */}
          >
            {o.label}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
