import type { StaticImageData } from "next/image";
import Link from "next/link";
import { brand } from "@brand/brand";

function Logo({
  image,
  dark,
  className,
}: {
  image: StaticImageData;
  dark?: StaticImageData;
  className: string;
}) {
  const height = brand.logoHeight ?? 28;
  const width = Math.round((image.width / image.height) * height);
  // Plain <img>: the static export has no image optimiser.
  const img = <img className={className} src={image.src} alt="" width={width} height={height} />;
  if (!dark) return img;
  return (
    <picture className={className}>
      <source media="(prefers-color-scheme: dark)" srcSet={dark.src} />
      {img}
    </picture>
  );
}

export function Nav() {
  return (
    <header className="nav">
      <Link href="/" className="brand" aria-label={`${brand.name} home`}>
        <Logo image={brand.logo} dark={brand.logoDark} className={brand.logoCompact ? "logo-full" : "logo"} />
        {brand.logoCompact && <Logo image={brand.logoCompact} className="logo-compact" />}
        {brand.showNameInHeader && (
          <>
            <span className="brand-name">{brand.name}</span>
            <span className="brand-short">{brand.shortName}</span>
          </>
        )}
      </Link>
      <nav>
        <Link href="/">Dashboard</Link>
        <Link href="/leagues">Leagues</Link>
        <Link href="/leagues/new" className="button small">
          New league
        </Link>
      </nav>
    </header>
  );
}
