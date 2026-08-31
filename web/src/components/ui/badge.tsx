import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/* Variants are split by JOB, not by colour.
   - standing-*  say how good something is        (traffic light, OD-13)
   - provisional/verified say what KIND it is     (never how good)
   A component may never pass a colour; it picks the job. */
const badgeVariants = cva(
  "inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 gap-1 [&>svg]:size-3 [&>svg]:pointer-events-none transition-[color,box-shadow] overflow-hidden",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-white",
        outline: "text-foreground",

        "standing-good": "border-transparent bg-[var(--standing-good-fill)] text-[var(--standing-good)]",
        "standing-mid":  "border-transparent bg-[var(--standing-mid-fill)] text-[var(--standing-mid)]",
        "standing-bad":  "border-transparent bg-[var(--standing-bad-fill)] text-[var(--standing-bad)]",

        provisional: "border-dashed border-[var(--provisional)] text-[var(--provisional)] bg-transparent",
        verified:    "border-transparent text-[var(--verified)] bg-transparent",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

function Badge({
  className, variant, asChild = false, ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span";
  return <Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
