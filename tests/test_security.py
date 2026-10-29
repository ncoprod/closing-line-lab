import pytest

from closing_line_lab.security import check_values


@pytest.mark.parametrize(
    "prefix,count",
    [("nvapi-", 32), ("sk-", 32), ("ghp_", 36), ("github_pat_", 40), ("AKIA", 16), ("AIza", 35)],
)
def test_value_scanner_rejects_credential_shapes_without_printing_values(prefix, count):
    candidate = prefix + "A" * count
    with pytest.raises(RuntimeError) as error:
        check_values(candidate)
    assert candidate not in str(error.value)


def test_value_scanner_accepts_documentation_member_name():
    check_values('{"' + "key" + '": "h2h"}')
