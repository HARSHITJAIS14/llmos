from lsfg.safety.redact import mask, scrub


def test_scrub_emails_unless_in_task():
    assert scrub("Account: a.b@example.com") == "Account: <email>"
    assert scrub("to a.b@example.com", keep="email a.b@example.com the doc") == "to a.b@example.com"
    assert scrub("no at sign") == "no at sign"
    assert scrub('combobox "Account: X (someone@gmail."') == 'combobox "Account: X (<email>"'   # cut by a label limit
    assert scrub("@e12 button") == "@e12 button"                                                   # aliases are not emails


def test_mask_keeps_inputs():
    assert mask("Priya Sharma", ["priya"]) == "Priya Sharma"
    assert mask("Mom 2", []) == "Www 9"
