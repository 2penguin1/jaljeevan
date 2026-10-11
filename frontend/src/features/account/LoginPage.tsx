import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { BUTTON, Field, INPUT, PRIMARY } from "@/features/tenders/ui";
import { ApiError } from "@/lib/api/client";
import { useLogin } from "@/lib/hooks/session";

export function LoginPage() {
  const login = useLogin();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const me = await login.mutateAsync({ email, password });
      const next = params.get("next");
      // only same-site paths: "//evil.com" would leave the site
      navigate(next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") ? next : me.role === "vendor" ? "/inbox" : "/tenders");
    } catch {
      // shown below
    }
  };

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-5 px-4 py-10">
      <h1 className="font-display text-[34px] text-text">Log in</h1>
      <p className="text-[13px] text-text-2">
        Relief officers, tanker vendors and NGOs use the accounts given to them. Anyone else can make a citizen account.
      </p>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field label="Email">
          <input type="email" autoComplete="username" required className={INPUT} value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password">
          <input type="password" autoComplete="current-password" required className={INPUT} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {login.error && (
          <p role="alert" className="text-[12px] text-heat">{login.error instanceof ApiError ? login.error.detail : "Could not log in."}</p>
        )}
        <button type="submit" className={PRIMARY} disabled={login.isPending}>Log in</button>
      </form>
      <Link to="/signup" className={BUTTON}>Make a citizen account</Link>
    </div>
  );
}
