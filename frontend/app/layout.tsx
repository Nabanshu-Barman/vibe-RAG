import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'VibeRAG — AI Video Comparison Chatbot',
  description:
    'Paste any YouTube and Instagram Reel URL. VibeRAG fetches metadata, computes engagement, and lets you chat with an AI that knows both videos inside-out.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
