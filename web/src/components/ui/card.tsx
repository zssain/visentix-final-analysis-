import * as React from "react"

import { cn } from "@/lib/utils"

/* DENSITY AND ELEVATION (2026-09-01).
 *
 * A card carried THREE separation cues at once: a border, a shadow, and — once
 * the page ground stopped being the same white as the card — a lightness step.
 * Any one of them separates a card from the page; all three together read as
 * chrome competing with the content inside it, which is what made a screen of
 * cards feel busy.
 *
 * The shadow is the one to lose. It is the only cue that does not survive
 * print, does not survive forced-colors, and does not carry meaning — the
 * border and the ground do the work. Elevation is now reserved for things that
 * genuinely float ABOVE the page: dialogs, popovers, the sidebar and the sticky
 * headers.
 *
 * Padding came down with it (py-6/px-6 -> py-4/px-4). At the old spacing a card
 * holding one figure was mostly air, so a dashboard of small facts read as a
 * page of large boxes.
 */

function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex flex-col gap-4 rounded-lg border bg-card py-4 text-card-foreground",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-4 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-4",
        className
      )}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      /* The UI sans, like every heading in the APPLICATION.
         The display serif is the report's voice, not the app's — see
         design-system §1. A card title briefly wore it, which put an editorial
         serif on a dashboard tile. */
      className={cn("font-sans text-[0.95rem] leading-tight font-semibold tracking-[-0.01em]", className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-[0.82rem] text-muted-foreground", className)}
      {...props}
    />
  )
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        "col-start-2 row-span-2 row-start-1 self-start justify-self-end",
        className
      )}
      {...props}
    />
  )
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-content"
      className={cn("px-4", className)}
      {...props}
    />
  )
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center px-4 [.border-t]:pt-4", className)}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
}
