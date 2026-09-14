import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { ReduxProvider } from "@/components/redux-provider";
import { TopNav } from "@/components/top-nav";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ReduxProvider>
          <ThemeProvider>
            <TopNav />
            {children}
          </ThemeProvider>
        </ReduxProvider>
      </body>
    </html>
  );
}
