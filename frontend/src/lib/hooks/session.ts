import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiGet, apiPost } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

/** Who is logged in (null when nobody). The session cookie is httpOnly, so asking the server is the only way. */
export const useMe = () =>
  useQuery({
    queryKey: ["me"],
    queryFn: async ({ signal }) => {
      try {
        return await apiGet<Me>("/auth/me", undefined, signal);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });

export const useLogin = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) => apiPost<Me>("/auth/login", body),
    onSuccess: (me) => client.setQueryData(["me"], me),
  });
};

export const useSignup = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; name: string; password: string }) => apiPost<Me>("/auth/signup", body),
    onSuccess: (me) => client.setQueryData(["me"], me),
  });
};

export const useLogout = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<void>("/auth/logout", {}),
    onSuccess: () => {
      client.setQueryData(["me"], null);
      client.removeQueries({ queryKey: ["inbox"] });
    },
  });
};

export const ROLE_NAME: Record<string, string> = {
  gov_admin: "Relief officer", vendor: "Vendor", ngo: "NGO", citizen: "Citizen",
};
