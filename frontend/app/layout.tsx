import React from 'react';
import './globals.css';

export const metadata = {
  title: 'Vulcan | Automation Control Plane',
  description: 'Enterprise automation OS — StackStorm-inspired operator console',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-canvas-void text-slate-200 min-h-screen font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
