import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
export function Button({ children, className = "", variant = "secondary", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  return <button className={("ui-button ui-button--" + variant + " " + className).trim()} {...props}>{children}</button>;
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) { return <input {...props} />; }
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger" | "info" }) { return <span className={"badge badge--" + tone}>{children}</span>; }
export function Card({ children }: { children: ReactNode }) { return <section className="card">{children}</section>; }
