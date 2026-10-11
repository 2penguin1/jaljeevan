import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Field, INPUT, PRIMARY } from "@/features/tenders/ui";
import { ApiError } from "@/lib/api/client";
import { useSignup } from "@/lib/hooks/session";

/** Citizen accounts only: government, vendor and NGO accounts are given out, never self-made. */
export function SignupPage() {
  const signup = useSignup();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await signup.mutateAsync(form);
      navigate("/map");
    } catch {
      // shown below
    }
  };

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-5 px-4 py-10">
      <h1 className="font-display text-[34px] text-text">Make a citizen account</h1>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field label="Your name"><input required autoComplete="name" className={INPUT} value={form.name} onChange={set("name")} /></Field>
        <Field label="Email"><input type="email" required autoComplete="email" className={INPUT} value={form.email} onChange={set("email")} /></Field>
        <Field label="Password (at least 8 characters)">
          <input type="password" required minLength={8} autoComplete="new-password" className={INPUT} value={form.password} onChange={set("password")} />
        </Field>
        {signup.error && (
          <p role="alert" className="text-[12px] text-heat">{signup.error instanceof ApiError ? signup.error.detail : "Could not sign up."}</p>
        )}
        <button type="submit" className={PRIMARY} disabled={signup.isPending}>Make account</button>
      </form>
      <p className="text-[13px] text-text-2">
        Already have one? <Link to="/login" className="underline hover:text-text">Log in</Link>
      </p>
    </div>
  );
}
