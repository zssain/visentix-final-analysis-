import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "./ThemeProvider";

/** Three states, not two: a plain light/dark switch cannot express "follow my
 *  OS", so a reader who has set their system to dark would be overridden on
 *  first load and have no way back.
 *
 *  Rendered as a segmented control rather than a dropdown: all three states
 *  visible at once, current one marked, one click to change — no menu to open. */
const OPTIONS = [
  { value: "light", label: "Light theme", Icon: Sun },
  { value: "system", label: "Follow system theme", Icon: Monitor },
  { value: "dark", label: "Dark theme", Icon: Moon },
] as const;

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-border bg-muted/60 p-0.5",
        className
      )}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              "inline-flex size-6.5 items-center justify-center rounded-full transition-colors",
              active
                ? "bg-background text-foreground ring-1 ring-border"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-3.5" aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
