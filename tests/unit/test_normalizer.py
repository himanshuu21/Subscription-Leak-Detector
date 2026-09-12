from app.core.normalizer import clean_description, group_merchants, compute_merchant_strength, FUZZY_THRESHOLD

def test_clean_strips_transaction_id():
    assert clean_description('NETFLIX.COM 8X4F2') == 'NETFLIX'

def test_clean_strips_store_number():
    assert clean_description('NETFLIX INC #4471') == 'NETFLIX'

def test_clean_strips_payment_prefix():
    assert clean_description('SQ *SPOTIFY AB1234') == 'SPOTIFY'

def test_clean_strips_filler_words():
    assert clean_description('DROPBOX INC') == 'DROPBOX'

def test_clean_strips_dotcom():
    assert clean_description('ICLOUD.COM') == 'ICLOUD'

def test_group_merges_netflix_variants():
    # All three clean to 'NETFLIX' — they should merge into one group.
    # 'NETFLIX.COM 8X4F2': .COM stripped (step 4), 8X4F2 stripped (digit token, step 3) → NETFLIX
    # 'NETFLIX INC #4471': INC stripped (step 5), #4471 stripped (step 2) → NETFLIX
    # 'NETFLIX*COM': .COM stripped (step 4) → NETFLIX  (star handled by whitespace collapse)
    groups = group_merchants(['NETFLIX.COM 8X4F2', 'NETFLIX INC #4471', 'NETFLIX*COM'])
    assert len(groups) == 1
    assert sorted(list(groups.values())[0]) == [0, 1, 2]

def test_group_does_not_merge_amazon_amazon_music():
    groups = group_merchants(['AMAZON', 'AMAZON MUSIC'])
    assert len(groups) == 2

def test_group_singleton():
    groups = group_merchants(['SWIGGY ORDER 8X4F2'])
    assert len(groups) == 1
    assert list(groups.values())[0] == [0]

def test_fuzzy_threshold_is_85():
    assert FUZZY_THRESHOLD == 85

def test_merchant_strength_identical():
    assert compute_merchant_strength(['NETFLIX', 'NETFLIX', 'NETFLIX']) == 1.0

def test_merchant_strength_single():
    assert compute_merchant_strength(['NETFLIX']) == 1.0

def test_group_transitive():
    # A ~ B, B ~ C, but A !~ C
    descriptions = ["NETFLIX PREMIUM", "NETFLIX PREMIU", "NETFLIX PREMIO"]
    groups = group_merchants(descriptions)
    assert len(groups) == 1
