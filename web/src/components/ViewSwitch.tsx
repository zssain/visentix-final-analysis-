import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ViewSwitchProps {
  value: "analyst" | "advisor";
  onChange: (v: "analyst" | "advisor") => void;
  variant?: "inline" | "mobile-bar";
}

export function ViewSwitch({ value, onChange, variant = "inline" }: ViewSwitchProps) {
  const inner = (
    <Tabs value={value} onValueChange={(v) => onChange(v as "analyst" | "advisor")}>
      <TabsList aria-label="Select view">
        <TabsTrigger value="analyst" id="view-switch-analyst">Analyst</TabsTrigger>
        <TabsTrigger value="advisor" id="view-switch-advisor">Advisor</TabsTrigger>
      </TabsList>
    </Tabs>
  );

  if (variant === "mobile-bar") {
    return (
      <div
        className="fixed bottom-0 inset-x-0 z-40 flex justify-center border-t bg-background/95 p-2 backdrop-blur md:hidden"
        role="toolbar"
        aria-label="View controls"
      >
        {inner}
      </div>
    );
  }
  return inner;
}
