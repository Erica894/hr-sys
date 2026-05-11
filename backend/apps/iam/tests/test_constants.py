from apps.iam import constants


def test_rsu_field_group_stable():
    """RSU_FIELD_GROUP is a contract with frontend RSU column hide rule.
    Adding/removing fields requires deliberate review."""
    assert constants.RSU_FIELD_GROUP == [
        "rsu_grant_amount",
        "rsu_vesting_schedule",
        "rsu_unvested_value",
        "rsu_strike_price",
        "rsu_grant_date",
    ]


def test_cash_and_rsu_groups_disjoint():
    """No field can simultaneously be cash + RSU."""
    cash = set(constants.CASH_FIELD_GROUP)
    rsu = set(constants.RSU_FIELD_GROUP)
    assert cash.isdisjoint(rsu)
