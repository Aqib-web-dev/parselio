export function AmbientBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
      <div className="absolute left-[15%] top-[15%] h-96 w-96 animate-[drift-a_18s_ease-in-out_infinite] rounded-full bg-primary/40 blur-3xl dark:bg-primary/30" />
      <div className="absolute bottom-[15%] right-[15%] h-[26rem] w-[26rem] animate-[drift-b_22s_ease-in-out_infinite] rounded-full bg-primary/25 blur-3xl dark:bg-primary/20" />
    </div>
  );
}
