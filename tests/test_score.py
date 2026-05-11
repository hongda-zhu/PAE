from ikusa.models import Finding, MasvsCategory, Severity
from ikusa.score import compute_cra_score


def _finding(sev: Severity, cat: MasvsCategory = MasvsCategory.STORAGE) -> Finding:
    return Finding(
        id="x",
        title="x",
        severity=sev,
        masvs_category=cat,
        description="x",
    )


def test_no_findings_with_full_coverage_returns_100():
    assert compute_cra_score([], categories_covered=8) == 100


def test_no_findings_with_partial_coverage_caps_below_100():
    # Coverage 3/8 means we should NOT score 100 even with zero findings.
    score = compute_cra_score([], categories_covered=3)
    assert score < 100


def test_no_findings_with_zero_coverage_returns_at_most_50():
    # Floor at 50% when nothing is covered at all (still 100 base, halved).
    score = compute_cra_score([], categories_covered=0)
    assert score <= 50


def test_high_penalty_is_larger_than_medium():
    s_high = compute_cra_score([_finding(Severity.HIGH)], categories_covered=3)
    s_med = compute_cra_score([_finding(Severity.MEDIUM)], categories_covered=3)
    s_low = compute_cra_score([_finding(Severity.LOW)], categories_covered=3)
    assert s_high < s_med < s_low


def test_score_floors_at_zero():
    many_high = [_finding(Severity.HIGH) for _ in range(50)]
    assert compute_cra_score(many_high, categories_covered=3) == 0


def test_score_is_integer_in_range():
    score = compute_cra_score(
        [_finding(Severity.HIGH), _finding(Severity.MEDIUM)],
        categories_covered=3,
    )
    assert isinstance(score, int)
    assert 0 <= score <= 100


def test_score_drops_with_more_high_findings():
    s_one = compute_cra_score([_finding(Severity.HIGH)], categories_covered=3)
    s_two = compute_cra_score(
        [_finding(Severity.HIGH), _finding(Severity.HIGH)],
        categories_covered=3,
    )
    assert s_two < s_one


def test_score_independent_of_finding_category():
    # Two findings in different categories, same severity, must produce same score.
    s_storage = compute_cra_score(
        [_finding(Severity.HIGH, MasvsCategory.STORAGE)], categories_covered=3,
    )
    s_crypto = compute_cra_score(
        [_finding(Severity.HIGH, MasvsCategory.CRYPTO)], categories_covered=3,
    )
    assert s_storage == s_crypto
