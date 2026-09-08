import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function date(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not available";
}
export function cost(value: string | null) {
  return value === null ? "Not available" : `$${value}`;
}
export function shortId(value: string) {
  return value.slice(0, 8);
}
