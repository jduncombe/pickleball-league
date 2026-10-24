// The white-label brand: product name, copy, logo and favicon. Each brand is
// a folder in web/brands/<name>/ (brand.ts + theme.css + images), chosen at
// build time with BRAND=<name> (see next.config.ts and docs/white-labelling.md).
// Import the active brand as `import { brand } from "@brand/brand"`.

import type { StaticImageData } from "next/image";

export interface Brand {
  /** Full product name: page titles, header, empty states. */
  name: string;
  /** Short name where space is tight (e.g. mobile header). */
  shortName: string;
  /** One sentence used for the page description meta tag. */
  description: string;
  /** Header logo (any size; shown at `logoHeight` px tall). */
  logo: StaticImageData;
  logoHeight?: number;
  /** Optional logo for dark mode, if `logo` lacks contrast on a dark background. */
  logoDark?: StaticImageData;
  /** Optional narrower logo for small screens (e.g. just the mark of a wide wordmark). */
  logoCompact?: StaticImageData;
  /** Show `name` beside the logo (turn off if the logo already contains it). */
  showNameInHeader: boolean;
  /** Browser tab icon (SVG or PNG). */
  icon: StaticImageData;
  /** Optional footer line, e.g. operator name and a link. */
  footer?: { text: string; href?: string };
}
