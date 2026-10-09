# evaluator.py
from __future__ import annotations

import gradio as gr
import pandas as pd
from litellm.exceptions import RateLimitError as LiteLLMRateLimitError
from openai import RateLimitError as OpenAIRateLimitError

from src.eval.eval import (
    DATASET_PATH,
    DB_PATH,
    LocalVectorStore,
    TestQuestion,
    evaluate_test_case,
    load_tests,
)

vector_store = LocalVectorStore(DB_PATH)


def run_single_evaluation(test_index: int):
    tests = load_tests(DATASET_PATH)
    if not (0 <= test_index < len(tests)):
        return "Invalid Test Index", "", "", "", "", "", 0, 0, 0, 0, 0, 0

    test: TestQuestion = tests[test_index]

    ret_eval, ans_eval, generated_answer, retrieved_docs = evaluate_test_case(
        test, vector_store
    )

    formatted_docs = "\n\n---\n\n".join(
        [
            f"**[Chunk {idx+1}] (Article {doc.get('article_number', 'N/A')})**\n{doc.get('text', '')}"
            for idx, doc in enumerate(retrieved_docs)
        ]
    )

    return (
        test.query,
        ", ".join(test.keywords),
        test.ground_truth_answer,
        generated_answer,
        formatted_docs,
        ans_eval.feedback,
        round(ret_eval.mrr, 4),
        round(ret_eval.ndcg, 4),
        round(ret_eval.keyword_coverage, 1),
        round(ans_eval.accuracy, 2),
        round(ans_eval.completeness, 2),
        round(ans_eval.relevance, 2),
    )


def run_batch_evaluation():
    tests = load_tests(DATASET_PATH)
    records = []
    for test in tests:
        try:
            ret_eval, ans_eval, _, _ = evaluate_test_case(test, vector_store)
        except (OpenAIRateLimitError, LiteLLMRateLimitError) as exc:
            records.append(
                {
                    "ID": test.id,
                    "Query": test.query,
                    "MRR": None,
                    "nDCG": None,
                    "Coverage (%)": None,
                    "Accuracy": None,
                    "Completeness": None,
                    "Relevance": None,
                    "Feedback": f"Groq rate limit reached: {exc}",
                }
            )
            continue
        records.append(
            {
                "ID": test.id,
                "Query": test.query,
                "MRR": round(ret_eval.mrr, 4),
                "nDCG": round(ret_eval.ndcg, 4),
                "Coverage (%)": round(ret_eval.keyword_coverage, 1),
                "Accuracy": ans_eval.accuracy,
                "Completeness": ans_eval.completeness,
                "Relevance": ans_eval.relevance,
                "Feedback": ans_eval.feedback,
            }
        )

    results = pd.DataFrame(records)
    if results.empty:
        return results

    numeric_columns = [
        "MRR",
        "nDCG",
        "Coverage (%)",
        "Accuracy",
        "Completeness",
        "Relevance",
    ]
    overall = {
        "ID": "OVERALL",
        "Query": (
            f"Macro average across {results[numeric_columns].dropna().shape[0]} "
            "successful test cases"
        ),
        "Feedback": "Dataset-level macro average; rate-limited cases are excluded.",
    }
    overall.update(
        {
            column: round(float(results[column].mean()), 4 if column in {"MRR", "nDCG"} else 2)
            for column in numeric_columns
        }
    )
    overall["Coverage (%)"] = round(float(results["Coverage (%)"].mean()), 1)

    return pd.concat([pd.DataFrame([overall]), results], ignore_index=True)


with gr.Blocks(title="Ghana Law Companion - Evaluation Dashboard") as app:
    gr.Markdown("# 🏛️ Ghana Law RAG Evaluator")

    with gr.Tabs():
        with gr.Tab("Single Case Evaluator"):
            with gr.Row():
                test_idx = gr.Number(value=0, label="Test Case Index", precision=0)
                eval_btn = gr.Button("Evaluate Case", variant="primary")

            with gr.Row():
                with gr.Column():
                    q_box = gr.Textbox(label="Query", interactive=False)
                    kw_box = gr.Textbox(label="Keywords", interactive=False)
                    gt_box = gr.Textbox(label="Ground Truth Answer", interactive=False, lines=4)
                    gen_box = gr.Textbox(label="Generated Answer", interactive=False, lines=5)

                with gr.Column():
                    with gr.Row():
                        mrr_out = gr.Number(label="MRR")
                        ndcg_out = gr.Number(label="nDCG")
                        cov_out = gr.Number(label="Keyword Coverage (%)")
                    with gr.Row():
                        acc_out = gr.Number(label="Accuracy (1-5)")
                        comp_out = gr.Number(label="Completeness (1-5)")
                        rel_out = gr.Number(label="Relevance (1-5)")

                    fb_box = gr.Textbox(label="Judge Feedback", interactive=False, lines=3)

            with gr.Accordion("Retrieved Context Chunks", open=False):
                ctx_box = gr.Markdown()

            eval_btn.click(
                fn=run_single_evaluation,
                inputs=[test_idx],
                outputs=[
                    q_box, kw_box, gt_box, gen_box, ctx_box, fb_box,
                    mrr_out, ndcg_out, cov_out, acc_out, comp_out, rel_out
                ],
            )

        with gr.Tab("Batch Benchmark"):
            batch_btn = gr.Button("Run Benchmark Dataset", variant="primary")
            summary_table = gr.Dataframe(label="Evaluation Metrics Summary")
            batch_btn.click(fn=run_batch_evaluation, outputs=[summary_table])

if __name__ == "__main__":
    app.launch()