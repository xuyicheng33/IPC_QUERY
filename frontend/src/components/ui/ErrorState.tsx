import React from "react";
import { TriangleAlert } from "lucide-react";

type ErrorStateProps = {
  message: string;
};

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className="flex min-h-[120px] flex-col items-center justify-center rounded-lg border border-[#e6b8b8] bg-[#fff8f8] px-6 py-8 text-center">
      <TriangleAlert className="mb-3 h-5 w-5 text-danger" aria-hidden="true" />
      <p className="text-sm text-danger">{message}</p>
    </div>
  );
}
