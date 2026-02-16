"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: "default" | "glass" | "gradient";
}

export function Card({ children, className, variant = "default" }: CardProps) {
  const variants = {
    default: "rounded-2xl bg-white/80 backdrop-blur-xl shadow-xl shadow-gray-200/50 ring-1 ring-gray-100 p-6",
    glass: "rounded-2xl bg-white/60 backdrop-blur-xl shadow-xl ring-1 ring-white/20 p-6",
    gradient: "rounded-2xl bg-gradient-to-br from-white to-gray-50/80 backdrop-blur-xl shadow-xl shadow-gray-200/50 ring-1 ring-gray-100 p-6",
  };

  return (
    <div className={cn(variants[variant], className)}>
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return (
    <div className={cn("mb-6 flex items-center justify-between", className)}>
      {children}
    </div>
  );
}

interface CardTitleProps {
  children: ReactNode;
  className?: string;
}

export function CardTitle({ children, className }: CardTitleProps) {
  return (
    <h3 className={cn("text-lg font-bold text-gray-900", className)}>
      {children}
    </h3>
  );
}

interface CardDescriptionProps {
  children: ReactNode;
  className?: string;
}

export function CardDescription({ children, className }: CardDescriptionProps) {
  return (
    <p className={cn("mt-1 text-sm text-gray-500", className)}>
      {children}
    </p>
  );
}

interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export function CardContent({ children, className }: CardContentProps) {
  return (
    <div className={cn("", className)}>
      {children}
    </div>
  );
}
