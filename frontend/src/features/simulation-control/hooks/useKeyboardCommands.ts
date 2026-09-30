"use client";

import { useEffect } from "react";

import type { Direction } from "@/types/connectome";

const KEY_MAP: Record<string, Direction> = {
  ArrowUp: "forward",
  ArrowDown: "reverse",
  ArrowLeft: "left",
  ArrowRight: "right",
  " ": "stop",
  z: "feed",
  x: "defecate",
  c: "reproduce",
};

export function useKeyboardCommands(onCommand: (direction: Direction) => void) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const direction = KEY_MAP[event.key];
      if (!direction) return;
      event.preventDefault();
      onCommand(direction);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onCommand]);
}
