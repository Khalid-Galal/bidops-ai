from app.services.versioning.versioning_service import parse_version


def test_rev_letter():
    base, rank, label = parse_version("Mechanical_Spec_RevB.pdf")
    assert rank == 2
    assert label == "rev B"
    base_a, rank_a, _ = parse_version("Mechanical_Spec_RevA.pdf")
    assert base == base_a
    assert rank > rank_a


def test_rev_number_and_v_number():
    assert parse_version("BOQ rev 2.xlsx")[1] == 2
    assert parse_version("BOQ_v3.xlsx")[1] == 3
    assert parse_version("Contract issue 2.docx")[1] == 2


def test_same_base_across_styles():
    b1, _, _ = parse_version("Spec_Rev A.pdf")
    b2, _, _ = parse_version("Spec rev.B.pdf")
    assert b1 == b2


def test_no_token_rank_zero():
    base, rank, label = parse_version("Specifications.pdf")
    assert rank == 0
    assert label is None
    # base of un-versioned file groups with versioned siblings
    vb, _, _ = parse_version("Specifications Rev A.pdf")
    assert base == vb


def test_unrelated_names_do_not_collide():
    assert parse_version("BOQ_v2.xlsx")[0] != parse_version("Drawings_v2.pdf")[0]
