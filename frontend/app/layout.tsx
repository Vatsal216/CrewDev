import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CrewDev — AI Development Platform',
  description: 'Multi-agent AI platform for software development',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
