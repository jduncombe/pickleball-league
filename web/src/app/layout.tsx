import type { Metadata } from "next";
import { brand } from "@brand/brand";
import { Nav } from "@/components/Nav";
import "@brand/theme.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: brand.name, template: `%s · ${brand.name}` },
  description: brand.description,
  applicationName: brand.name,
  icons: { icon: brand.icon.src },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main>{children}</main>
        {brand.footer && (
          <footer className="site-footer muted">
            {brand.footer.href ? <a href={brand.footer.href}>{brand.footer.text}</a> : brand.footer.text}
          </footer>
        )}
      </body>
    </html>
  );
}
