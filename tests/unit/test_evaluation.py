from app.core.evaluation import evaluate


def test_sample_evaluation_has_no_false_classifications():
    metrics = evaluate("sample.csv", "sample_truth.json")
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["false_positives"] == []
    assert metrics["false_negatives"] == []
    assert metrics["insufficient_evidence"] == ["DROPBOX", "HOTSTAR"]
