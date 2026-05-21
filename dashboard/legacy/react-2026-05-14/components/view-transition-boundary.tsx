"use client";

import * as React from "react";

type ViewTransitionProps = {
  children: React.ReactNode;
  className?: string;
  default?: "none" | "auto" | string;
  enter?: "none" | "auto" | string;
  exit?: "none" | "auto" | string;
  name?: string;
  share?: "none" | "auto" | string;
};

type ReactWithViewTransition = typeof React & {
  ViewTransition?: React.ComponentType<ViewTransitionProps>;
};

export function ViewTransitionBoundary(props: ViewTransitionProps) {
  const ViewTransition = (React as ReactWithViewTransition).ViewTransition;

  if (!ViewTransition) {
    return <>{props.children}</>;
  }

  return <ViewTransition {...props} />;
}
