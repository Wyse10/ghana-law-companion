from __future__ import annotations

import pandas as pd
import gradio as gr

# Project Imports from src.eval.eval
from src.eval.eval import (
    load_tests,
    evaluate_retrieval,
    evaluate_answer,
    TestQuestion,
    LocalVectorStore,
    DB_PATH,
)

# Initialize vector store instance once globally
vector_store = LocalVectorStore(DB_PATH)


def run_single_evaluation(test_index: int):
    """Run evaluation for a single selected test case index."""
    try:
        tests = load_tests()
    except Exception as e:
        return (
            f"Error loading dataset: {str(e)}",
            "",
            "",
            "",
            "",
            "",
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    if test_index < 0 or test_index >= len(tests):
        return (
            "Error: Invalid Test Index",
            "",
            "",
            "",
            "",
            "",
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

    test: TestQuestion = tests[test_index]

    # 1. Run Retrieval Evaluation
    retrieval_res = evaluate_retrieval(test, vector_store)

    # 2. Run Answer Quality Evaluation (LLM-as-a-Judge)
    answer_res, generated_answer, retrieved_docs = evaluate_answer(
        test, vector_store
    )

    # Format Retrieved Context Text for Display
    formatted_docs = "\n\n---\n\n".join(
        [
            f"**[Chunk {i+1}]**\n{doc.get('text', 'N/A')}"
            for i, doc in enumerate(retrieved_docs)
        ]
    )

    return (
        test.query,
        ", ".join(test.keywords),
        test.ground_truth_answer,
        generated_answer,
        formatted_docs,
        answer_res.feedback,
        round(retrieval_res.mrr, 4),
        round(retrieval_res.ndcg, 4),
        round(retrieval_res.keyword_coverage, 1),
        round(answer_res.accuracy, 2),
        round(answer_res.completeness, 2),
        round(answer_res.relevance, 2),
    )


def run_batch_evaluation():
    """Run evaluation across all test cases in golden_dataset.json and return a summary dataframe."""
    try:
        tests = load_tests()
    except Exception as e:
        return pd.DataFrame([{"Error": f"Dataset failure: {str(e)}"}])

    results = []

    for idx, test in enumerate(tests):
        ret_res = evaluate_retrieval(test, vector_store)
        ans_res, gen_ans, _ = evaluate_answer(test, vector_store)

        results.append(
            {
                "ID": test.id,
                "Query": test.query,
                "MRR": round(ret_res.mrr, 4),
                "nDCG": round(ret_res.ndcg, 4),
                "Coverage (%)": round(ret_res.keyword_coverage, 1),
                "Accuracy (1-5)": ans_res.accuracy,
                "Completeness (1-5)": ans_res.completeness,
                "Relevance (1-5)": ans_res.relevance,
            }
        )

    df = pd.DataFrame(results)
    return df


# --- Gradio UI Layout ---
with gr.Blocks(title="Ghana Law Companion - RAG Evaluator") as app:
    gr.Markdown("# 🏛️ Ghana Law RAG Evaluation Dashboard")
    gr.Markdown(
        "Evaluate retrieval metrics (**MRR**, **nDCG**) and generation metrics "
        "(**Accuracy**, **Completeness**, **Relevance**) using LLM-as-a-Judge."
    )

    with gr.Tabs():
        # TAB 1: Individual Test Case Inspector
        with gr.Tab("Single Test Case Evaluator"):
            with gr.Row():
                test_idx_input = gr.Number(
                    value=0,
                    label="Test Case Index",
                    precision=0,
                    minimum=0,
                    step=1,
                )
                run_btn = gr.Button("Evaluate Single Case", variant="primary")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Input & Outputs")
                    query_box = gr.Textbox(label="User Query", interactive=False)
                    keywords_box = gr.Textbox(
                        label="Target Keywords / Articles", interactive=False
                    )
                    gt_box = gr.Textbox(
                        label="Ground Truth Answer", interactive=False, lines=3
                    )
                    gen_box = gr.Textbox(
                        label="RAG Generated Answer", interactive=False, lines=4
                    )

                with gr.Column():
                    gr.Markdown("### Evaluation Scores")
                    with gr.Row():
                        mrr_num = gr.Number(label="MRR Score")
                        ndcg_num = gr.Number(label="nDCG Score")
                        cov_num = gr.Number(label="Keyword Coverage (%)")
                    with gr.Row():
                        acc_num = gr.Number(label="Accuracy (1-5)")
                        comp_num = gr.Number(label="Completeness (1-5)")
                        rel_num = gr.Number(label="Relevance (1-5)")

                    feedback_box = gr.Textbox(
                        label="LLM Judge Feedback", interactive=False, lines=3
                    )

            with gr.Accordion("Retrieved Context Chunks", open=False):
                context_box = gr.Markdown()

            run_btn.click(
                fn=run_single_evaluation,
                inputs=[test_idx_input],
                outputs=[
                    query_box,
                    keywords_box,
                    gt_box,
                    gen_box,
                    context_box,
                    feedback_box,
                    mrr_num,
                    ndcg_num,
                    cov_num,
                    acc_num,
                    comp_num,
                    rel_num,
                ],
            )

        # TAB 2: Full Dataset Batch Evaluation
        with gr.Tab("Full Dataset Batch Benchmark"):
            batch_btn = gr.Button("Run Benchmark on Golden Dataset", variant="primary")
            results_table = gr.Dataframe(
                headers=[
                    "ID",
                    "Query",
                    "MRR",
                    "nDCG",
                    "Coverage (%)",
                    "Accuracy (1-5)",
                    "Completeness (1-5)",
                    "Relevance (1-5)",
                ],
                label="Benchmark Results Summary",
            )

            batch_btn.click(
                fn=run_batch_evaluation,
                outputs=[results_table],
            )

if __name__ == "__main__":
    app.launch()