"use client";

import type { SolutionStep } from "../lib/api";
import { MathText } from "./mathtext";

/** Lời giải từng bước: số thứ tự, việc cần làm, công thức, phép tính, kết quả. */
export function Steps({ steps, hideLastResult = false }: { steps: SolutionStep[]; hideLastResult?: boolean }) {
  return (
    <ol className="steps">
      {steps.map((step, index) => {
        const last = index === steps.length - 1;
        return (
          <li key={index} className="step-row">
            <span className="step-no" aria-hidden="true">{index + 1}</span>
            <div className="step-body">
              <div className="step-action"><MathText text={step.action} /></div>
              {step.formula && <div className="step-formula"><MathText text={step.formula} /></div>}
              {step.work && <div className="step-work"><MathText text={step.work} /></div>}
              {step.result && !(hideLastResult && last) && (
                <div className="step-result"><span aria-hidden="true">⇒</span> <MathText text={step.result} /></div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

type Block =
  | { kind: "text"; text: string }
  | { kind: "step"; step: SolutionStep };

/**
 * Gợi ý từ server là chữ nhiều dòng ("Bước 1: …", "   Công thức: …", "   ⇒ …").
 * Dựng lại thành các bước có cấu trúc để hiện như lời giải, không như một khối chữ.
 */
export function HintText({ text }: { text: string }) {
  const blocks: Block[] = [];
  let current: SolutionStep | null = null;
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const step = line.match(/^Bước\s*\d+\s*:\s*(.*)$/);
    if (step) {
      const parsed: SolutionStep = { action: "", formula: "", work: "", result: "" };
      const [action, formula] = step[1].split(" — dùng ");
      parsed.action = action;
      parsed.formula = formula ?? "";
      current = parsed;
      blocks.push({ kind: "step", step: current });
      continue;
    }
    if (current && /^\s+/.test(raw)) {
      const body = line.trim();
      if (body.startsWith("Công thức:")) current.formula = body.slice("Công thức:".length).trim();
      else if (body.startsWith("⇒")) current.result = body.slice(1).trim();
      else current.work = current.work ? `${current.work}\n${body}` : body;
      continue;
    }
    current = null;
    if (line.trim()) blocks.push({ kind: "text", text: line.trim() });
  }

  const out: React.ReactNode[] = [];
  let run: SolutionStep[] = [];
  const flush = () => {
    if (run.length) out.push(<Steps key={`s${out.length}`} steps={run} />);
    run = [];
  };
  for (const block of blocks) {
    if (block.kind === "step") {
      run.push(block.step);
    } else {
      flush();
      out.push(<p key={`t${out.length}`} className="hint-line"><MathText text={block.text} /></p>);
    }
  }
  flush();
  return <>{out}</>;
}
