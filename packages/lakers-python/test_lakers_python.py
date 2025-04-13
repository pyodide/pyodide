from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["lakers-python"])
def test_lakers_python(selenium_standalone):
    import lakers

    # Running an exchange needs some keys and credentials; those are from the EDHOC test vectors.
    R = bytes.fromhex(
        "72cc4761dbd4c78f758931aa589d348d1ef874a7e303ede2f140dcf3e6aa4aac"
    )
    CRED_R = bytes.fromhex(
        "A2026008A101A5010202410A2001215820BBC34960526EA4D32E940CAD2A234148DDC21791A12AFBCBAC93622046DD44F02258204519E257236B2A0CE2023F0931F1F386CA7AFDA64FCDE0108C224C51EABF6072"
    )

    initiator = lakers.EdhocInitiator()
    responder = lakers.EdhocResponder(R, CRED_R)

    message_1 = initiator.prepare_message_1()
    responder.process_message_1(message_1)
    _message_2 = responder.prepare_message_2(
        lakers.CredentialTransfer.ByReference, None, None
    )

    # There's a lot more that can be tested, but if this runs through, we've covered the most critical kinds of operations.
