from app.domain.states import StateCodes


def test_state_code_handles_aliases():
    assert StateCodes.code("Rajasthan") == "RJ"
    assert StateCodes.code("Orissa") == "OR"
    assert StateCodes.code("NCT of Delhi") == "DL"
    assert StateCodes.code("Jammu & Kashmir") == "JK"
    assert StateCodes.code("Atlantis") is None


def test_name_lookup():
    assert StateCodes.name("KA") == "Karnataka"
