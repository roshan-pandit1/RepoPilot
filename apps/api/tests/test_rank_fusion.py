from app.modules.ingestion.rank_fusion import reciprocal_rank_fusion


def test_rank_fusion_rewards_agreement_and_deduplicates_each_ranking():
    result = reciprocal_rank_fusion([["first", "shared", "shared"], ["shared", "other"]], k=60)
    assert [item for item, _ in result] == ["shared", "first", "other"]
    assert abs(result[0][1] - (1 / 62 + 1 / 61)) < 1e-12


def test_rank_fusion_ties_have_stable_order():
    assert [key for key, _ in reciprocal_rank_fusion([["z"], ["a"]])] == ["a", "z"]
