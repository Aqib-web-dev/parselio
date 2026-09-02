import json
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parselio.settings.dev")
django.setup()

from documents.models import Document
from documents.services import retrieve, rerank, generate_answer
from tenants.models import Membership

from ragas import EvaluationDataset, evaluate
from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithReference, LLMContextRecall
from ragas.run_config import RunConfig

from eval.judge_llm import get_judge_llm, get_judge_embeddings


GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"


def build_evaluation_rows(tenant, user):
    with open(GOLDEN_DATASET_PATH) as f:
        golden_rows = json.load(f)

    rows = []
    for golden in golden_rows:
        query = golden["user_input"]

        candidates = retrieve(tenant, user, query)
        top_chunks = rerank(query, candidates)
        answer = generate_answer(query, top_chunks)

        rows.append({
            "user_input": query,
            "retrieved_contexts": [c.text for c in top_chunks],
            "response": answer,
            "reference": golden["reference"],
        })
        print(f"  ran: {golden['id']}")

    return rows

def run_evaluation():
    tenant = Document.objects.get(title="Leave Policy").tenant
    user = Membership.objects.filter(tenant=tenant, role=Membership.Role.OWNER).first().user

    print("Running pipeline on golden dataset...")
    rows = build_evaluation_rows(tenant, user)

    dataset = EvaluationDataset.from_list(rows)

    print("Scoring with RAGAS...")
    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ResponseRelevancy(), LLMContextPrecisionWithReference(), LLMContextRecall()],
        llm=get_judge_llm(),
        embeddings=get_judge_embeddings(),
        run_config=RunConfig(max_retries=3, max_wait=15, timeout=60, max_workers=8),
    )

    return result

if __name__ == "__main__":
    result = run_evaluation()
    print(result)

    output_path = Path(__file__).parent.parent / "eval_baseline.json"
    with open(output_path, "w") as f:
        json.dump(result.to_pandas().to_dict(orient="records"), f, indent=2, default=str)

    print(f"Saved baseline to {output_path}")
