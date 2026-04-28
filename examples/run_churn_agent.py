from __future__ import annotations

import argparse
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from agents.deepagent_factory import create_cloud_sandbox_deep_agent


DEFAULT_TASK = """
Build a churn prediction scoring prototype using BigQuery table `metricsamp.1.Telco_CC`.

Work like a careful ML engineer:
1. Use injected Python through the `run_injected_python` tool to inspect the table schema and sample rows.
2. Identify the likely churn target column and explain your assumption.
3. Check row count, missing values, target distribution, and obvious leakage columns.
4. Pull a reasonable sample into pandas from BigQuery.
5. Train a simple baseline churn classifier.
6. Report validation metrics such as ROC AUC, accuracy, precision, recall, and confusion matrix.
7. Create a scored output sample with customer identifiers if available and churn probability.
8. Write useful metadata/results to Firestore if the connector is available.
9. Upload useful artifacts to GCS if the connector is available.
10. If something fails, inspect stderr/stdout, fix the issue, and retry.

Do not assume the schema. Inspect first. Keep the first run lightweight and reproducible.
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Deep Agents churn smoke test against cloud-sandbox.")
    parser.add_argument("--sandbox-url", default=os.getenv("SANDBOX_URL"), help="Cloud sandbox base URL.")
    parser.add_argument("--thread-id", default="metricsamp-telco-churn-smoke", help="Stable Deep Agents thread id.")
    parser.add_argument("--gcp-project", default="metricsamp", help="GCP project containing the BigQuery table.")
    parser.add_argument("--gcs-bucket", default=os.getenv("SANDBOX_GCS_BUCKET"), help="Optional GCS bucket for artifacts.")
    parser.add_argument(
        "--firestore-collection",
        default=os.getenv("SANDBOX_FIRESTORE_COLLECTION", "sandbox_runs"),
        help="Firestore collection for run metadata.",
    )
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"), help="Gemini model name.")
    parser.add_argument("--task", default=DEFAULT_TASK, help="Task prompt for the agent.")
    args = parser.parse_args()

    if not args.sandbox_url:
        raise SystemExit("Set SANDBOX_URL or pass --sandbox-url.")
    if not os.getenv("GOOGLE_API_KEY"):
        raise SystemExit("Set GOOGLE_API_KEY for langchain-google-genai.")

    gcp_connector = {
        "project_id": args.gcp_project,
        "firestore_collection": args.firestore_collection,
    }
    if args.gcs_bucket:
        gcp_connector["gcs_bucket"] = args.gcs_bucket

    model = ChatGoogleGenerativeAI(
        model=args.model,
        temperature=0.2,
    )
    agent = create_cloud_sandbox_deep_agent(
        sandbox_url=args.sandbox_url,
        thread_id=args.thread_id,
        model=model,
        connectors={"gcp": gcp_connector},
        ttl_seconds=7200,
    )

    response = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": args.task,
                }
            ]
        }
    )
    print(response)


if __name__ == "__main__":
    main()
