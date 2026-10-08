import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  followRun,
  fetchSteps,
  startReset,
  startStep,
  type DemoStep,
  type RunEvent,
} from "../../api/demo";
import { useMe } from "../../api/queries";
import { PageIntro } from "../../components/admin/PageIntro";
import { ConfirmDialog } from "../../components/common/ConfirmDialog";
import { ErrorState, Skeleton } from "../../components/common/States";

type RunStatus = "idle" | "running" | "succeeded" | "failed";

const LIGHT: Record<DemoStep["preconditions"], { dot: string; label: string }> =
  {
    met: { dot: "bg-emerald-500", label: "Ready" },
    unmet: { dot: "bg-amber-500", label: "Not available" },
    unknown: { dot: "bg-slate-400", label: "Unknown" },
  };
const RESET_MESSAGE =
  "This clears bookmarks, overrides, status logs, proposals and the audit log, regenerates the source data and runs the pipeline again. It takes about a minute.";

/** `unmet` steps cannot run; `unknown` stays enabled so a failed check never blocks a fallback (OQ-154). */
const blocked = (step: DemoStep) => step.preconditions === "unmet";

/** The steps under their group headings, in the order the scenario file lists them (F14-FR-13). */
const groupSteps = (
  steps: DemoStep[],
): { name: string; steps: DemoStep[] }[] => {
  const groups: { name: string; steps: DemoStep[] }[] = [];
  for (const step of steps) {
    const found = groups.find((group) => group.name === step.group);
    if (found) found.steps.push(step);
    else groups.push({ name: step.group, steps: [step] });
  }
  return groups;
};

const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

/** Demo Controls (F13-FR-06): run a scripted step, watch its progress, reset the demo. Admin only, DEMO_MODE only. */
export function DemoControls() {
  const me = useMe();
  const queryClient = useQueryClient();
  const isAdmin = me.data?.role === "admin";
  const steps = useQuery({
    queryKey: ["demo-steps"],
    queryFn: fetchSteps,
    enabled: isAdmin,
    retry: false,
  });
  const [log, setLog] = useState<RunEvent[]>([]);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<RunStatus>("idle");
  const [refusal, setRefusal] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const running = status === "running";

  const follow = async (runId: string) => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setLog([]);
    setStatus("running");
    try {
      await followRun(
        runId,
        (event) => {
          setLog((current) => [...current, event]);
          if (event.kind === "done") setStatus("succeeded");
          if (event.kind === "failed") setStatus("failed");
        },
        controller.signal,
      );
    } catch (error) {
      setLog((current) => [
        ...current,
        {
          seq: current.length,
          kind: "failed",
          message: `Lost the progress stream: ${(error as Error).message}`,
          elapsed_ms: 0,
        },
      ]);
      setStatus("failed");
    }
    await queryClient.invalidateQueries({ queryKey: ["demo-steps"] });
    await queryClient.invalidateQueries({
      predicate: (query) => query.queryKey[0] !== "demo-steps",
    });
  };

  const begin = async (
    name: string,
    start: () => Promise<{ run_id: string }>,
  ) => {
    setRefusal(null);
    setTitle(name);
    try {
      const { run_id } = await start();
      await follow(run_id);
    } catch (error) {
      setLog([]);
      setStatus("failed");
      setRefusal((error as Error).message);
    }
  };

  if (me.isLoading) return <Skeleton label="Loading Demo Controls" />;
  if (!isAdmin) {
    return (
      <main className="flex-1 p-6" data-testid="demo-forbidden">
        <PageIntro subtitle="Demo Controls are for admins. Switch the persona to Admin to use them." />
      </main>
    );
  }

  return (
    <main
      className="flex-1 space-y-3 overflow-auto p-6 pb-20"
      data-testid="demo-controls-page"
    >
      <div className="flex items-start justify-between gap-4">
        <PageIntro subtitle="Run a scripted step through the real source systems, the pipeline and the sync. One step at a time." />
        <button
          type="button"
          disabled={running}
          className="rounded-chip border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 enabled:hover:bg-red-50 disabled:opacity-50"
          onClick={() => setConfirmReset(true)}
        >
          Reset demo
        </button>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-3">
          {steps.isLoading && <Skeleton label="Loading the steps" />}
          {steps.isError && (
            <ErrorState
              what="the steps"
              error={steps.error}
              onRetry={() => void steps.refetch()}
            />
          )}
          {groupSteps(steps.data ?? []).map((group) => (
            <section
              key={group.name}
              data-testid="demo-group"
              data-group={group.name}
              aria-label={group.name}
            >
              <h2 className="mb-1.5 text-xs font-semibold tracking-wide text-ink-2 uppercase">
                {group.name}
              </h2>
              <ul
                className="divide-y divide-hairline rounded-card border border-hairline bg-white"
                aria-label={`Scenario steps: ${group.name}`}
              >
                {group.steps.map((step) => (
                  <li
                    key={step.id}
                    data-testid="demo-step"
                    data-step={step.id}
                    className="flex items-start gap-4 p-4"
                  >
                    <span
                      role="img"
                      aria-label={`${LIGHT[step.preconditions].label}${step.messages[0] ? `: ${step.messages[0]}` : ""}`}
                      title={
                        step.messages[0] ?? LIGHT[step.preconditions].label
                      }
                      data-testid="precondition-light"
                      data-state={step.preconditions}
                      className={`mt-1.5 h-3 w-3 shrink-0 rounded-full ${LIGHT[step.preconditions].dot}`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-ink">{step.title}</div>
                      <div className="text-sm italic text-ink-2">
                        {step.talk_track}
                      </div>
                      {step.preconditions !== "met" && step.messages[0] && (
                        <div className="mt-1 text-xs text-amber-700">
                          {step.messages[0]}
                        </div>
                      )}
                    </div>
                    {/* A disabled button gets no hover, so the reason sits on a wrapper (F14-FR-09). */}
                    <span
                      data-testid="run-reason"
                      title={blocked(step) ? step.messages[0] : undefined}
                    >
                      <button
                        type="button"
                        disabled={running || blocked(step)}
                        aria-label={`Run ${step.title}`}
                        className="rounded-chip bg-accent px-3 py-1.5 text-sm font-medium text-white enabled:hover:opacity-90 disabled:opacity-50"
                        onClick={() =>
                          void begin(step.title, () => startStep(step.id))
                        }
                      >
                        Run
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <section aria-label="Progress" className="space-y-2 lg:sticky lg:top-0">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-ink">
              Progress{title ? `: ${title}` : ""}
            </h2>
            <span
              data-testid="run-status"
              data-status={status}
              className={`rounded-pill px-2 py-0.5 text-xs ${status === "succeeded" ? "bg-emerald-50 text-emerald-700" : status === "failed" ? "bg-red-50 text-red-700" : status === "running" ? "bg-sky-50 text-sky-700" : "bg-slate-100 text-slate-600"}`}
            >
              {status === "idle" ? "Nothing run yet" : status}
            </span>
          </div>
          {refusal && (
            <p
              role="alert"
              data-testid="step-refused"
              className="rounded-card border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
            >
              {refusal}
            </p>
          )}
          <ol
            aria-label="Progress log"
            data-testid="progress-log"
            aria-live="polite"
            className="max-h-[32rem] min-h-48 overflow-auto rounded-card border border-hairline bg-slate-50 p-3 font-mono text-xs"
          >
            {log.length === 0 && (
              <li className="text-ink-2">
                Run a step to see its progress here.
              </li>
            )}
            {log.map((event) => (
              <li
                key={event.seq}
                data-testid="progress-line"
                data-kind={event.kind}
                className={
                  event.kind === "failed"
                    ? "text-red-700"
                    : event.kind === "done"
                      ? "text-emerald-700"
                      : "text-ink"
                }
              >
                <span className="mr-2 text-ink-2">
                  {seconds(event.elapsed_ms)}
                </span>
                {event.message}
              </li>
            ))}
          </ol>
        </section>
      </div>

      {confirmReset && (
        <ConfirmDialog
          title="Reset the demo?"
          message={RESET_MESSAGE}
          confirmLabel="Reset demo"
          onCancel={() => setConfirmReset(false)}
          onConfirm={() => {
            setConfirmReset(false);
            void begin("Reset demo", startReset);
          }}
        />
      )}
    </main>
  );
}
