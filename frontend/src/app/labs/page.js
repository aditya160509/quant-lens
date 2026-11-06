import Link from 'next/link';

const MODULES = [
  ['Screener', '/labs/screener-v2'],
  ['Factors', '/labs/factors-v2'],
  ['PCA', '/labs/pca-v2'],
  ['Volatility', '/labs/volatility-v2'],
  ['Portfolio', '/labs/portfolio-v2'],
];

export default function LabsPage() {
  return (
    <main className="mx-auto grid max-w-3xl gap-2 p-8">
      {MODULES.map(([name, href]) => (
        <Link key={href} href={href} className="rounded border border-terminal-gray p-4 font-mono text-sm hover:text-terminal-yellow">
          {name}
        </Link>
      ))}
    </main>
  );
}
