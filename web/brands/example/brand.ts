// Sample brand showing what can change. Build with: BRAND=example npm run build
import type { Brand } from "@/lib/brand";
import icon from "./icon.svg";
import logo from "./logo.svg";
import logoDark from "./logo-dark.svg";

export const brand: Brand = {
  name: "Example Racquet Club",
  shortName: "Example Club",
  description: "League nights at Example Racquet Club: fixtures, courts and results.",
  logo,
  logoHeight: 32,
  logoDark,
  // On phones, show just the mark.
  logoCompact: icon,
  // The logo is a wordmark, so don't repeat the name beside it.
  showNameInHeader: false,
  icon,
  footer: { text: "Example Racquet Club · League software", href: "https://example.com" },
};
