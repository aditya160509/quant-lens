import { IBM_Plex_Mono, DM_Sans, Syne, Outfit, JetBrains_Mono, Inter } from "next/font/google";
import NextTopLoader from "nextjs-toploader";
import "./globals.css";
import GlobalLayout from "../components/GlobalLayout";
import { Providers } from "../components/Providers.js";
import RouteTransition from "../components/RouteTransition";

const ibmPlexMono = IBM_Plex_Mono({
  weight: ['400', '500', '600', '700'],
  subsets: ['latin'],
  variable: '--font-ibm-plex-mono',
  display: 'swap',
});

const dmSans = DM_Sans({
  subsets: ['latin'],
  variable: '--font-dm-sans',
  display: 'swap',
});

const syne = Syne({
  subsets: ['latin'],
  variable: '--font-syne',
  display: 'swap',
});

const outfit = Outfit({
  subsets: ['latin'],
  variable: '--font-outfit',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata = {
  title: "ATLAS Research",
  description: "Quantitative research, backtesting, and portfolio analytics.",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon-16x16.png",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "ATLAS Research",
    description: "Quantitative research, backtesting, and portfolio analytics.",
    type: "website",
  },
};

export const viewport = {
  themeColor: "#080C10",
  colorScheme: "dark",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${ibmPlexMono.variable} ${dmSans.variable} ${syne.variable} ${outfit.variable} ${jetbrainsMono.variable} antialiased`}>
        <NextTopLoader color="#2F81F7" height={2} showSpinner={false} />
        <Providers>
          <GlobalLayout>
            <RouteTransition>{children}</RouteTransition>
          </GlobalLayout>
        </Providers>
      </body>
    </html>
  );
}
