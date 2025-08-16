import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import { DynamicWalletProvider } from '@/src/config/dynamic'
import '../styles/globals.css'

export const metadata: Metadata = {
  title: 'DaVinci AI Commerce',
  description: 'AI-powered multi-agent e-commerce ecosystem',
  generator: 'DaVinci AI',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning={true}>
        <DynamicWalletProvider>
          {children}
        </DynamicWalletProvider>
      </body>
    </html>
  )
}
