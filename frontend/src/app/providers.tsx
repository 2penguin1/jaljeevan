import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
  });
}

export function AppProviders({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? makeQueryClient());
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
