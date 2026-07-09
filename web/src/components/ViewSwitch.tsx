import "./furniture.css";

interface ViewSwitchProps {
  value: "analyst" | "advisor";
  onChange: (v: "analyst" | "advisor") => void;
  variant?: "inline" | "mobile-bar";
}

export function ViewSwitch({ value, onChange, variant = "inline" }: ViewSwitchProps) {
  const cls = variant === "mobile-bar" ? "view-switch-mobile-bar" : undefined;

  const inner = (
    <div className="view-switch" role="group" aria-label="Select view">
      <button
        className={value === "analyst" ? "active" : ""}
        onClick={() => onChange("analyst")}
        aria-pressed={value === "analyst"}
        id="view-switch-analyst"
      >
        Analyst
      </button>
      <button
        className={value === "advisor" ? "active" : ""}
        onClick={() => onChange("advisor")}
        aria-pressed={value === "advisor"}
        id="view-switch-advisor"
      >
        Advisor
      </button>
    </div>
  );

  if (variant === "mobile-bar") {
    return (
      <div className={cls} role="toolbar" aria-label="View controls">
        {inner}
      </div>
    );
  }

  return inner;
}
