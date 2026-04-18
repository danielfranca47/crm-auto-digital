import { cn } from "@/lib/utils";

interface WizardProgressProps {
  steps: string[];
  currentStep: number;
}

export function WizardProgress({ steps, currentStep }: WizardProgressProps) {
  return (
    <div className="flex items-center gap-0 w-full mb-8">
      {steps.map((label, i) => {
        const done = i < currentStep;
        const active = i === currentStep;
        return (
          <div key={i} className="flex items-center flex-1 min-w-0">
            <div className="flex flex-col items-center gap-1 shrink-0">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-colors",
                  done && "bg-primary border-primary text-primary-foreground",
                  active && "border-primary text-primary bg-background",
                  !done && !active && "border-muted-foreground/40 text-muted-foreground/50 bg-background"
                )}
              >
                {done ? "✓" : i + 1}
              </div>
              <span
                className={cn(
                  "text-[10px] font-medium text-center leading-tight max-w-[60px]",
                  active ? "text-primary" : done ? "text-foreground" : "text-muted-foreground/50"
                )}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-0.5 mx-1 mt-[-12px] transition-colors",
                  done ? "bg-primary" : "bg-muted-foreground/20"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
